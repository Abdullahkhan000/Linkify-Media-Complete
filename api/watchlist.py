from asgiref.sync import async_to_sync
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .core import fetch_tmdb_endpoint, summarize_result
from .middleware import throttle
from .models import WatchlistItem


class WatchlistPage(LoginRequiredMixin, TemplateView):
    template_name = 'watchlist.html'


class MediaInput(serializers.Serializer):
    media_type = serializers.ChoiceField(choices=['movie', 'tv'])
    tmdb_id = serializers.IntegerField(min_value=1, max_value=2147483647)
    favorite = serializers.BooleanField(required=False, default=False)


def serialize_item(item):
    return {name: getattr(item, name) for name in (
        'id', 'tmdb_id', 'media_type', 'title', 'poster_url', 'release_year', 'overview', 'favorite',
    )}


def provider_error(data):
    if 'Error' in data:
        return Response({'error': data['Error']}, status=503)


class PrivateMediaAPI(APIView):
    permission_classes = [IsAuthenticated]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        return response

    def throttled(self, request):
        return throttle(f'watchlist-media:{request.user.pk}', 60, period=60)


class WatchlistAPI(PrivateMediaAPI):
    def get(self, request):
        items = WatchlistItem.objects.filter(user=request.user)
        total, favorites = items.count(), items.filter(favorite=True).count()
        if request.query_params.get('favorite') == 'true':
            items = items.filter(favorite=True)
        paginator = Paginator(items, 24)
        page = paginator.get_page(request.query_params.get('page', 1))
        return Response({'results': [serialize_item(item) for item in page],
            'total': total, 'favorites': favorites, 'page': page.number, 'pages': paginator.num_pages})

    def post(self, request):
        form = MediaInput(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        identity = {'user': request.user, 'tmdb_id': data['tmdb_id'], 'media_type': data['media_type']}
        existing = WatchlistItem.objects.filter(**identity).first()
        if existing:
            return Response(serialize_item(existing))
        if self.throttled(request):
            return Response({'error': 'Too many media requests. Please retry shortly.'}, status=429)
        detail = async_to_sync(fetch_tmdb_endpoint)(f"{data['media_type']}/{data['tmdb_id']}")
        error = provider_error(detail)
        if error is not None:
            return error
        summary = summarize_result(detail)
        if not summary['title'] or detail.get('id') != data['tmdb_id']:
            return Response({'error': 'Media details could not be verified.'}, status=503)
        item, created = WatchlistItem.objects.get_or_create(**identity, defaults={
            'title': summary['title'][:300], 'release_year': summary['release_year'] or '',
            'poster_url': summary['poster_url'] or '', 'overview': summary['overview'] or '',
            'favorite': data['favorite'],
        })
        return Response(serialize_item(item), status=201 if created else 200)


class WatchlistItemAPI(PrivateMediaAPI):
    def patch(self, request, pk):
        item = get_object_or_404(WatchlistItem, pk=pk, user=request.user)
        form = serializers.BooleanField()
        if 'favorite' not in request.data:
            return Response({'error': 'favorite is required.'}, status=400)
        item.favorite = form.run_validation(request.data['favorite'])
        item.save(update_fields=['favorite'])
        return Response(serialize_item(item))

    def delete(self, request, pk):
        item = get_object_or_404(WatchlistItem, pk=pk, user=request.user)
        item.delete()
        return Response(status=204)


class WatchlistSearchAPI(PrivateMediaAPI):
    def get(self, request):
        query = request.query_params.get('q', '').strip()
        media_type = request.query_params.get('type', 'movie')
        if not 2 <= len(query) <= 200 or media_type not in {'movie', 'tv'}:
            return Response({'error': 'Enter a title (2–200 characters) and choose Movie or TV.'}, status=400)
        if self.throttled(request):
            return Response({'error': 'Too many searches. Please retry shortly.'}, status=429)
        data = async_to_sync(fetch_tmdb_endpoint)(f'search/{media_type}', {'query': query, 'include_adult': 'false'})
        error = provider_error(data)
        if error is not None:
            return error
        candidates = data.get('results', [])[:20]
        saved = {item.tmdb_id: item for item in WatchlistItem.objects.filter(
            user=request.user, media_type=media_type, tmdb_id__in=[item['id'] for item in candidates],
        ).only('tmdb_id', 'favorite')}
        results = []
        for detail in candidates:
            item = summarize_result(detail)
            stored = saved.get(detail['id'])
            results.append({**item, 'tmdb_id': detail['id'], 'media_type': media_type,
                'saved_id': stored.pk if stored else None, 'favorite': stored.favorite if stored else False})
        return Response({'results': results, **({'_cache': data['_cache']} if '_cache' in data else {})})


class WatchlistProvidersAPI(PrivateMediaAPI):
    def get(self, request, media_type, tmdb_id):
        country = request.query_params.get('country', 'US').upper()
        if media_type not in {'movie', 'tv'} or tmdb_id < 1 or len(country) != 2 or not country.isascii() or not country.isalpha():
            return Response({'error': 'Choose a valid media type and a two-letter country code.'}, status=400)
        if self.throttled(request):
            return Response({'error': 'Too many media requests. Please retry shortly.'}, status=429)
        data = async_to_sync(fetch_tmdb_endpoint)(f'{media_type}/{tmdb_id}/watch/providers')
        error = provider_error(data)
        if error is not None:
            return error
        return Response({'country': country, 'providers': data.get('results', {}).get(country, {}),
            'attribution': 'JustWatch', **({'_cache': data['_cache']} if '_cache' in data else {})})
