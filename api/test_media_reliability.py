import asyncio
from unittest.mock import AsyncMock, Mock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from .core import fetch_media_links, fetch_tmdb_endpoint, rank_candidates
from .middleware import demo_token
from .provider_cache import cache_key
from .utils import fetch_json


SEARCH = {'results': [{'id': 27205, 'title': 'Inception', 'vote_count': 100, 'popularity': 10}]}
DETAIL = {
    'id': 27205, 'title': 'Inception', 'release_date': '2010-07-15',
    'genres': [{'name': 'Science Fiction'}], 'credits': {'cast': [{'name': 'Actor'}]},
    'external_ids': {'imdb_id': 'tt1375666'},
}
CACHE = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'media-reliability-tests'}}


@override_settings(TMDB_API_KEY='test-key', CACHES=CACHE)
class MediaReliabilityTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    async def test_normalized_repeated_search_needs_only_two_provider_calls(self):
        with patch('api.core.fetch_json', AsyncMock(side_effect=[SEARCH, DETAIL])) as fetch:
            first = await fetch_media_links(' Inception ', 'movie', 'us')
            second = await fetch_media_links('INCEPTION', 'film', 'us')
        self.assertEqual(first, second)
        self.assertEqual(fetch.await_count, 2)
        self.assertEqual(first['IMDb Link'], 'https://www.imdb.com/title/tt1375666/')
        self.assertIn('append_to_response', fetch.await_args_list[1].args[2])

    async def test_provider_outage_returns_503_code_not_false_not_found(self):
        with patch('api.core.fetch_json', AsyncMock(return_value=None)) as fetch:
            response = await fetch_media_links('Inception', 'movie')
        self.assertEqual(response['code'], 'provider_unavailable')
        self.assertEqual(fetch.await_count, 1)

    async def test_expired_result_survives_provider_outage_without_refreshing_fresh_cache(self):
        with patch('api.core.fetch_json', AsyncMock(side_effect=[SEARCH, DETAIL])):
            original = await fetch_media_links('Inception', 'movie')
        media_key = cache_key('media', ['inception', 'movie', 'us', 'test-key'])
        await cache.adelete(media_key)
        await cache.adelete(cache_key('tmdb', ['search/movie', {'query': 'Inception', 'include_adult': 'false', 'api_key': 'test-key'}]))
        with patch('api.core.fetch_json', AsyncMock(return_value=None)):
            response = await fetch_media_links('Inception', 'movie')
        self.assertEqual(response['Official Title'], original['Official Title'])
        self.assertEqual(response['_cache']['status'], 'stale')
        self.assertIsNone(await cache.aget(media_key))

    async def test_genuine_no_match_is_short_cached(self):
        with patch('api.core.fetch_json', AsyncMock(return_value={'results': []})) as fetch:
            first = await fetch_media_links('Nonexistent unique film', 'movie')
            second = await fetch_media_links('Nonexistent unique film', 'movie')
        self.assertEqual(first['code'], 'not_found')
        self.assertEqual(first, second)
        self.assertEqual(fetch.await_count, 2)

    async def test_malformed_provider_response_is_not_saved(self):
        with patch('api.core.fetch_json', AsyncMock(side_effect=[{'results': 'bad'}, SEARCH, DETAIL])):
            first = await fetch_media_links('Inception', 'movie')
            second = await fetch_media_links('Inception', 'movie')
        self.assertEqual(first['code'], 'provider_unavailable')
        self.assertEqual(second['Official Title'], 'Inception')

    async def test_cache_failure_does_not_break_a_valid_search(self):
        with patch('api.provider_cache.cache.aget', AsyncMock(side_effect=ConnectionError)), patch(
            'api.provider_cache.cache.aset', AsyncMock(side_effect=ConnectionError)
        ), patch('api.core.fetch_json', AsyncMock(side_effect=[SEARCH, DETAIL])):
            response = await fetch_media_links('Inception', 'movie')
        self.assertEqual(response['Official Title'], 'Inception')

    async def test_endpoint_cache_cannot_be_mutated_by_a_caller(self):
        with patch('api.core.fetch_json', AsyncMock(return_value=DETAIL)) as fetch:
            first = await fetch_tmdb_endpoint('movie/27205')
            first.pop('credits')
            second = await fetch_tmdb_endpoint('movie/27205')
        self.assertIn('credits', second)
        self.assertEqual(fetch.await_count, 1)

    def test_exact_title_beats_unrelated_extreme_popularity(self):
        exact = {'id': 1, 'title': 'Dune', 'vote_count': 1, 'popularity': 1}
        other = {'id': 2, 'title': 'Dune Part Two', 'vote_count': 10000, 'popularity': 999999}
        self.assertEqual(rank_candidates([other, exact], 'Dune'), exact)

    def test_original_title_and_punctuation_match(self):
        exact = {'id': 1, 'title': 'Localized Title', 'original_title': 'Spider-Man', 'popularity': 1}
        self.assertEqual(rank_candidates([exact], 'Spider Man'), exact)

    @override_settings(API_REQUEST_TIMEOUT=0.01)
    async def test_total_deadline_returns_provider_error(self):
        async def slow_provider(*args):
            await asyncio.Event().wait()
        with patch('api.core.fetch_json', new=slow_provider):
            result = await fetch_media_links('Inception', 'movie')
        self.assertEqual(result['code'], 'provider_unavailable')

    async def test_long_retry_after_does_not_retry_early(self):
        response = Mock(status=429, headers={'Retry-After': '60'})
        context = AsyncMock()
        context.__aenter__.return_value = response
        session = Mock()
        session.get.return_value = context
        with patch('api.utils.asyncio.sleep', AsyncMock()) as sleep:
            result = await fetch_json(session, 'https://example.invalid/test')
        self.assertIsNone(result)
        self.assertEqual(session.get.call_count, 1)
        sleep.assert_not_awaited()


@override_settings(CACHES=CACHE, TMDB_API_KEY='test-key', SECURE_SSL_REDIRECT=False, DEMO_API_ENABLED=True)
class MediaAPIBehaviorTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_provider_outage_maps_to_http_503(self):
        with patch('api.views.fetch_media_links', AsyncMock(return_value={'Error': 'Unavailable', 'code': 'provider_unavailable'})):
            response = self.client.get('/api/v1/search/?q=Inception', HTTP_X_DEMO_TOKEN=demo_token())
        self.assertEqual(response.status_code, 503)

    def test_duplicate_batch_queries_share_work_but_preserve_field_selection(self):
        result = {'Official Title': 'Dune', 'Release Year': '2021'}
        with patch('api.views.fetch_media_links', AsyncMock(return_value=result)) as provider:
            response = self.client.post('/api/v1/batch/', {
                'items': [
                    {'q': ' Dune ', 'type': 'movie', 'fields': 'title'},
                    {'q': 'DUNE', 'type': 'film', 'fields': 'year'},
                ]
            }, content_type='application/json', HTTP_X_DEMO_TOKEN=demo_token())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(provider.await_count, 1)
        self.assertEqual(response.json()['results'], [{'Official Title': 'Dune'}, {'Release Year': '2021'}])

    def test_field_selection_keeps_stale_cache_label(self):
        with patch('api.views.fetch_media_links', AsyncMock(return_value={
            'Official Title': 'Inception', 'Release Year': '2010',
            '_cache': {'status': 'stale', 'reason': 'provider_unavailable'},
        })):
            response = self.client.get('/api/v1/search/?q=Inception&fields=title', HTTP_X_DEMO_TOKEN=demo_token())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['_cache']['status'], 'stale')
        self.assertNotIn('Release Year', response.json())

    def test_country_specific_detail_formatting_does_not_corrupt_shared_cache(self):
        data = {**DETAIL, 'watch/providers': {'results': {'US': {'link': 'https://example.com/us'}, 'GB': {'link': 'https://example.com/gb'}}}, 'recommendations': {'results': []}}
        with patch('api.core.fetch_json', AsyncMock(return_value=data)) as fetch:
            first = self.client.get('/api/v1/media/movie/27205/?country=us', HTTP_X_DEMO_TOKEN=demo_token())
            second = self.client.get('/api/v1/media/movie/27205/?country=gb', HTTP_X_DEMO_TOKEN=demo_token())
        self.assertEqual(first.json()['watch_providers']['link'], 'https://example.com/us')
        self.assertEqual(second.json()['watch_providers']['link'], 'https://example.com/gb')
        self.assertEqual(fetch.await_count, 1)
