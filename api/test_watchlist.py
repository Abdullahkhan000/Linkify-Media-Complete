from unittest.mock import AsyncMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from .models import WatchlistItem

DETAIL = {'id': 27205, 'title': 'Inception', 'release_date': '2010-07-15', 'poster_path': '/poster.jpg', 'overview': 'A movie.'}


@override_settings(SECURE_SSL_REDIRECT=False)
class WatchlistTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username='watchlist_owner')
        self.other = get_user_model().objects.create_user(username='other_watchlist')
        self.client.force_login(self.user)

    def add(self, **extra):
        with patch('api.watchlist.fetch_tmdb_endpoint', AsyncMock(return_value=DETAIL)):
            return self.client.post('/api/v1/watchlist/', {'tmdb_id':27205, 'media_type':'movie', **extra}, content_type='application/json')

    def test_save_is_verified_owned_and_idempotent(self):
        first = self.add(user_id=self.other.pk, title='Forged', poster_url='https://evil.invalid/image')
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()['title'], 'Inception')
        self.assertTrue(first.json()['poster_url'].startswith('https://image.tmdb.org/'))
        with patch('api.watchlist.fetch_tmdb_endpoint', AsyncMock()) as provider:
            repeated = self.client.post('/api/v1/watchlist/', {'tmdb_id':27205,'media_type':'movie'}, content_type='application/json')
        self.assertEqual(repeated.status_code, 200)
        provider.assert_not_awaited()
        self.assertEqual(WatchlistItem.objects.count(), 1)
        self.assertEqual(WatchlistItem.objects.get().user, self.user)

    def test_favorites_and_removal_persist(self):
        saved = self.add().json()
        url = f'/api/v1/watchlist/{saved["id"]}/'
        changed = self.client.patch(url, {'favorite':True}, content_type='application/json')
        self.assertEqual(changed.status_code, 200)
        self.assertTrue(WatchlistItem.objects.get().favorite)
        filtered = self.client.get('/api/v1/watchlist/?favorite=true').json()
        self.assertEqual(filtered['favorites'], 1)
        self.assertEqual(len(filtered['results']), 1)
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertFalse(WatchlistItem.objects.exists())

    def test_other_user_cannot_read_modify_or_remove_item(self):
        saved = self.add().json()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get('/api/v1/watchlist/').json()['results'], [])
        url = f'/api/v1/watchlist/{saved["id"]}/'
        self.assertEqual(self.client.patch(url, {'favorite':True}, content_type='application/json').status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertTrue(WatchlistItem.objects.exists())

    def test_anonymous_cannot_use_watchlist(self):
        self.client.logout()
        self.assertEqual(self.client.get('/watchlist/').status_code, 302)
        self.assertEqual(self.client.get('/api/v1/watchlist/').status_code, 403)
        self.assertEqual(self.client.get('/api/v1/watchlist/search/?q=Dune').status_code, 403)

    def test_session_write_requires_csrf(self):
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.user)
        self.assertEqual(browser.post('/api/v1/watchlist/', {'tmdb_id':27205,'media_type':'movie'}, content_type='application/json').status_code, 403)
        self.assertContains(browser.get('/watchlist/'), 'Watchlist & favorites')

    def test_search_works_without_personal_api_key_and_marks_saved_items(self):
        saved = self.add().json()
        with patch('api.watchlist.fetch_tmdb_endpoint', AsyncMock(return_value={'results':[DETAIL]})):
            response = self.client.get('/api/v1/watchlist/search/?q=Inception&type=movie')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'][0]['saved_id'], saved['id'])
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_provider_outage_does_not_create_fabricated_saved_data(self):
        with patch('api.watchlist.fetch_tmdb_endpoint', AsyncMock(return_value={'Error':'Provider unavailable'})):
            response = self.client.post('/api/v1/watchlist/', {'tmdb_id':27205,'media_type':'movie'}, content_type='application/json')
        self.assertEqual(response.status_code, 503)
        self.assertFalse(WatchlistItem.objects.exists())

    def test_movie_and_tv_with_same_id_are_separate(self):
        self.add()
        with patch('api.watchlist.fetch_tmdb_endpoint', AsyncMock(return_value={'id':27205,'name':'A TV show'})):
            response = self.client.post('/api/v1/watchlist/', {'tmdb_id':27205,'media_type':'tv'}, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(WatchlistItem.objects.count(), 2)

    def test_invalid_identity_is_rejected(self):
        for data in ({'tmdb_id':-1,'media_type':'movie'}, {'tmdb_id':1,'media_type':'person'}, {'tmdb_id':'oops','media_type':'tv'}):
            self.assertEqual(self.client.post('/api/v1/watchlist/', data, content_type='application/json').status_code, 400)

    def test_country_availability_and_attribution(self):
        providers = {'results': {'US': {'flatrate':[{'provider_name':'Example service'}]}, 'GB': {'buy':[{'provider_name':'Another service'}]}}}
        with patch('api.watchlist.fetch_tmdb_endpoint', AsyncMock(return_value=providers)):
            response = self.client.get('/api/v1/watchlist/providers/movie/27205/?country=gb')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['attribution'], 'JustWatch')
        self.assertEqual(response.json()['providers']['buy'][0]['provider_name'], 'Another service')

    def test_pagination_and_user_deletion(self):
        WatchlistItem.objects.bulk_create([WatchlistItem(user=self.user,tmdb_id=index+1,media_type='movie',title=f'Title {index}') for index in range(25)])
        response = self.client.get('/api/v1/watchlist/?page=2').json()
        self.assertEqual(response['pages'], 2)
        self.assertEqual(len(response['results']), 1)
        self.user.delete()
        self.assertFalse(WatchlistItem.objects.exists())
