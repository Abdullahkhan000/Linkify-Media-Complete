from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import (
    APIKey,
    BillingWebhookEvent,
    Profile,
    SupportConversation,
    SupportMessage,
    SupportTicket,
    UsageLog,
)
from .serializers import APIKeySerializer
from .core import fetch_media_links, fetch_tmdb_endpoint, filter_fields, summarize_result
import asyncio
import hashlib
import hmac
import csv
import logging
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.base import View, TemplateView
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model, logout
from django.db import OperationalError, transaction
from asgiref.sync import async_to_sync
from datetime import date, timedelta
from django.db.models import Avg, Count
import json
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.urls import reverse, reverse_lazy
from django.utils import timezone
import requests
from allauth.account.models import EmailAddress
from allauth.account.views import PasswordChangeView as AllauthPasswordChangeView
from allauth.account.views import SignupView as AllauthSignupView
from django.contrib import messages

from .forms import QuickSignUpForm, SupportRequestForm
from .middleware import DAILY_LIMITS, client_ip, demo_token, throttle
from .support_bot import generate_reply

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# API Key CRUD Views
# ─────────────────────────────────────────

class APIKeyListCreateView(LoginRequiredMixin, APIView):
    login_url = '/accounts/login/'

    def get(self, request):
        keys = APIKey.objects.filter(user=request.user).order_by('-created_at')
        serializer = APIKeySerializer(keys, many=True)
        return Response(serializer.data)

    def post(self, request):
        if not EmailAddress.objects.filter(
            user=request.user,
            email__iexact=request.user.email,
            verified=True,
        ).exists():
            return Response(
                {'error': 'Verify your email address before creating an API key.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        limit_map = {'free': 1, 'pro': 5, 'business': 100}
        serializer = APIKeySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        requested_scopes = serializer.validated_data.get('scopes') or APIKey.DEFAULT_SCOPES
        profile, _ = Profile.objects.get_or_create(user=request.user)
        if profile.tier == 'free' and 'batch' in requested_scopes:
            return Response(
                {'error': 'Batch scope requires a Pro or Business plan.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        with transaction.atomic():
            Profile.objects.select_for_update().get(pk=profile.pk)
            existing = APIKey.objects.filter(
                user=request.user,
                is_active=True,
                revoked_at__isnull=True,
            ).count()
            max_keys = limit_map.get(profile.tier, 1)
            if existing >= max_keys:
                return Response(
                    {'error': f'Your current plan ({profile.tier}) allows only {max_keys} active API key(s).'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            key_obj, raw_key = APIKey.issue(
                user=request.user,
                name=serializer.validated_data['name'],
                scopes=requested_scopes,
                expires_at=serializer.validated_data.get('expires_at'),
            )

        payload = APIKeySerializer(key_obj).data
        payload['key'] = raw_key
        payload['notice'] = 'Copy this key now. It will not be shown again.'
        return Response(payload, status=status.HTTP_201_CREATED)


class APIKeyDetailView(LoginRequiredMixin, APIView):
    login_url = '/accounts/login/'

    def get_object(self, pk, user):
        try:
            return APIKey.objects.get(pk=pk, user=user)
        except APIKey.DoesNotExist:
            return None

    def patch(self, request, pk):
        key = self.get_object(pk, request.user)
        if not key:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = APIKeySerializer(key, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        key = self.get_object(pk, request.user)
        if not key:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        key.revoke()
        return Response(status=status.HTTP_204_NO_CONTENT)


class APIKeyRotateView(LoginRequiredMixin, APIView):
    login_url = '/accounts/login/'

    def post(self, request, pk):
        try:
            old_key = APIKey.objects.get(pk=pk, user=request.user)
        except APIKey.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not old_key.is_usable:
            return Response({'error': 'Only an active key can be rotated.'}, status=400)

        with transaction.atomic():
            old_key = APIKey.objects.select_for_update().get(pk=old_key.pk)
            old_key.revoke()
            new_key, raw_key = APIKey.issue(
                user=request.user,
                name=old_key.name,
                scopes=old_key.scopes,
                expires_at=old_key.expires_at,
            )
        payload = APIKeySerializer(new_key).data
        payload['key'] = raw_key
        payload['notice'] = 'The previous key was revoked. Copy this replacement now.'
        return Response(payload, status=status.HTTP_201_CREATED)


# ─────────────────────────────────────────
# Linkify Core Views
# ─────────────────────────────────────────

class SearchAPIView(APIView):
    permission_classes = []

    def get(self, request):
        is_demo = getattr(request, 'is_demo', False)
        if not getattr(request, 'api_key', None) and not is_demo:
            return Response({'error': 'API Key missing or invalid.'}, status=401)

        query = request.GET.get('q', '').strip()
        raw_type = (request.GET.get('type') or 'movie').strip().lower()
        country = (request.GET.get('country') or 'us').strip().lower()
        fields_param = request.GET.get('fields', '').strip()

        if not query or not 2 <= len(query) <= 200:
            return Response({'error': 'Search query "q" must be 2–200 characters long.'}, status=400)
        if len(country) != 2 or not country.isalpha():
            return Response({'error': 'country must be a two-letter code such as us or gb.'}, status=400)
        if len(fields_param) > 500:
            return Response({'error': 'fields is too long.'}, status=400)

        # Strict media type validation & mapping
        TYPE_MAP = {
            'movie': 'movie',
            'film': 'movie',
            'tv': 'tv',
            'show': 'tv',
            'series': 'tv',
            'anime': 'tv',
            'tvshow': 'tv',
            'tv show': 'tv',
        }

        if raw_type not in TYPE_MAP:
            return Response({
                'error': f"Invalid media type '{raw_type}'. Supported types: 'movie', 'tv', 'show', 'anime', 'series'."
            }, status=400)

        media_type = TYPE_MAP[raw_type]

        result = async_to_sync(fetch_media_links)(query, media_type, country=country)

        if not result:
            return Response({'error': f"No verified media found matching '{query}'."}, status=404)

        if isinstance(result, dict) and "Error" in result:
            error_status = 503 if result.get('code') == 'provider_not_configured' else 404
            return Response({'error': result["Error"]}, status=error_status)

        if fields_param and isinstance(result, dict):
            result = filter_fields(result, fields_param)

        return Response(result, status=200)


class BatchAPIView(APIView):
    permission_classes = []

    def post(self, request):
        is_demo = getattr(request, 'is_demo', False)
        api_key = getattr(request, 'api_key', None)

        if not api_key and not is_demo:
            return Response({'error': 'API Key missing or invalid.'}, status=401)

        tier = api_key.tier if api_key else ('demo' if is_demo else 'free')

        if tier == 'free':
            return Response({'error': 'Batch endpoint is available on Pro and Business plans only.'}, status=403)

        items = request.data.get('items')
        if not items or not isinstance(items, list):
            return Response({'error': 'A non-empty items array is required.'}, status=400)

        batch_limit = settings.BATCH_LIMITS.get(tier, 1)
        if len(items) > batch_limit:
            return Response({'error': f'This plan allows at most {batch_limit} items per batch.'}, status=400)

        normalized_items = []
        allowed_types = {'movie', 'film', 'tv', 'show', 'series', 'anime', 'tvshow', 'tv show'}
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                return Response({'error': f'items[{index}] must be an object.'}, status=400)
            query = str(item.get('q', '')).strip()
            if len(query) < 2 or len(query) > 200:
                return Response({'error': f'items[{index}].q must be 2–200 characters.'}, status=400)
            media_type = str(item.get('type', 'movie')).strip().lower()
            if media_type not in allowed_types:
                return Response({'error': f'items[{index}].type is unsupported.'}, status=400)
            country = str(item.get('country', 'us')).strip().lower()
            if len(country) != 2 or not country.isalpha():
                return Response({'error': f'items[{index}].country must be a two-letter code.'}, status=400)
            normalized_items.append({
                'q': query,
                'type': media_type,
                'country': country,
                'fields': item.get('fields'),
            })

        async def run_batch():
            tasks = [
                fetch_media_links(
                    item.get('q', ''),
                    item.get('type', 'movie'),
                    country=item.get('country', 'us')
                ) for item in normalized_items
            ]
            raw_results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=settings.API_REQUEST_TIMEOUT,
            )
            final_results = []
            for idx, res in enumerate(raw_results):
                if isinstance(res, Exception):
                    final_results.append({'error': 'Provider request failed for this item.'})
                    continue
                req_fields = normalized_items[idx].get('fields')
                if req_fields and isinstance(res, dict):
                    final_results.append(filter_fields(res, req_fields))
                else:
                    final_results.append(res)
            return final_results

        try:
            results = async_to_sync(run_batch)()
        except TimeoutError:
            return Response({'error': 'The batch request timed out. Try fewer items.'}, status=504)

        return Response({'results': results}, status=200)


class UsageAPIView(APIView):
    permission_classes = []

    def get(self, request):
        if not getattr(request, 'api_key', None):
            return Response({'error': 'API Key missing or invalid.'}, status=401)

        today = date.today()
        limit = DAILY_LIMITS.get(request.api_key.tier)

        today_count = UsageLog.objects.filter(api_key=request.api_key, date=today).count()

        return Response({
            'tier': request.api_key.tier,
            'today_usage': today_count,
            'daily_limit': limit if limit else 'unlimited',
            'remaining': (limit - today_count) if limit else 'unlimited',
        })


def provider_response_error(result):
    if not isinstance(result, dict) or 'Error' not in result:
        return None
    code = result.get('code')
    response_status = 503 if code in {'provider_not_configured', 'provider_unavailable'} else 400
    return Response({'error': result['Error']}, status=response_status)


class SearchResultsAPIView(APIView):
    permission_classes = []

    def get(self, request):
        query = request.GET.get('q', '').strip()
        media_type = request.GET.get('type', 'movie').strip().lower()
        if not 2 <= len(query) <= 200:
            return Response({'error': 'q must be 2–200 characters.'}, status=400)
        if media_type not in {'movie', 'tv'}:
            return Response({'error': 'type must be movie or tv.'}, status=400)
        try:
            page = min(500, max(1, int(request.GET.get('page', '1'))))
        except ValueError:
            return Response({'error': 'page must be an integer.'}, status=400)
        params = {
            'query': query,
            'page': page,
            'include_adult': 'false',
            'language': request.GET.get('language', 'en-US')[:10],
        }
        year = request.GET.get('year', '').strip()
        if year:
            if not year.isdigit() or not 1880 <= int(year) <= 2100:
                return Response({'error': 'year must be between 1880 and 2100.'}, status=400)
            params['year' if media_type == 'movie' else 'first_air_date_year'] = year
        result = async_to_sync(fetch_tmdb_endpoint)(f'search/{media_type}', params)
        error = provider_response_error(result)
        if error:
            return error
        items = result.get('results', [])
        genre = request.GET.get('genre', '').strip()
        if genre:
            if not genre.isdigit():
                return Response({'error': 'genre must be a numeric TMDB genre ID.'}, status=400)
            items = [item for item in items if int(genre) in item.get('genre_ids', [])]
        return Response({
            'page': result.get('page', page),
            'total_pages': result.get('total_pages', 0),
            'total_results': result.get('total_results', 0),
            'results': [summarize_result(item) for item in items],
        })


class MediaDetailAPIView(APIView):
    permission_classes = []

    def get(self, request, media_type, media_id):
        if media_type not in {'movie', 'tv'}:
            return Response({'error': 'type must be movie or tv.'}, status=400)
        result = async_to_sync(fetch_tmdb_endpoint)(
            f'{media_type}/{media_id}',
            {'append_to_response': 'credits,recommendations,watch/providers,external_ids'},
        )
        error = provider_response_error(result)
        if error:
            return error
        country = request.GET.get('country', 'US').strip().upper()
        if len(country) != 2 or not country.isalpha():
            return Response({'error': 'country must be a two-letter code such as US or GB.'}, status=400)
        watch_data = result.pop('watch/providers', {}).get('results', {}).get(country, {})
        recommendations = result.pop('recommendations', {}).get('results', [])[:10]
        credits = result.get('credits') or {}
        result['credits'] = {
            'cast': credits.get('cast', [])[:15],
            'crew': credits.get('crew', [])[:15],
        }
        result['watch_providers'] = watch_data
        result['recommendations'] = [summarize_result(item) for item in recommendations]
        return Response(result)


class TrendingAPIView(APIView):
    permission_classes = []

    def get(self, request):
        media_type = request.GET.get('type', 'all').lower()
        if media_type not in {'all', 'movie', 'tv'}:
            return Response({'error': 'type must be all, movie, or tv.'}, status=400)
        result = async_to_sync(fetch_tmdb_endpoint)(f'trending/{media_type}/week')
        error = provider_response_error(result)
        if error:
            return error
        return Response({'results': [summarize_result(item) for item in result.get('results', [])]})


class PersonSearchAPIView(APIView):
    permission_classes = []

    def get(self, request):
        query = request.GET.get('q', '').strip()
        if not 2 <= len(query) <= 120:
            return Response({'error': 'q must be 2–120 characters.'}, status=400)
        result = async_to_sync(fetch_tmdb_endpoint)('search/person', {'query': query, 'include_adult': 'false'})
        error = provider_response_error(result)
        if error:
            return error
        people = [{
            'id': item.get('id'),
            'name': item.get('name'),
            'department': item.get('known_for_department'),
            'profile_url': f"https://image.tmdb.org/t/p/w500{item['profile_path']}" if item.get('profile_path') else None,
            'known_for': [summarize_result(work) for work in item.get('known_for', [])[:5]],
        } for item in result.get('results', [])]
        return Response({'results': people})


class HealthView(View):
    def get(self, request, *args, **kwargs):
        return JsonResponse({'status': 'ok', 'service': 'linkify-media'})


class ReadinessView(View):
    def get(self, request, *args, **kwargs):
        try:
            Profile.objects.exists()
        except OperationalError:
            return JsonResponse({'status': 'unavailable', 'database': 'down'}, status=503)
        return JsonResponse({
            'status': 'ready',
            'database': 'ok',
            'tmdb_configured': bool(settings.TMDB_API_KEY),
        })


class OpenAPISchemaView(View):
    def get(self, request, *args, **kwargs):
        security = [{'ApiKeyAuth': []}]
        schema = {
            'openapi': '3.1.0',
            'info': {
                'title': 'Linkify Media API',
                'version': '1.0.0',
                'description': 'Media metadata search, batch processing, and usage analytics.',
            },
            'servers': [{'url': request.build_absolute_uri('/api/v1/')}],
            'components': {
                'securitySchemes': {
                    'ApiKeyAuth': {'type': 'apiKey', 'in': 'header', 'name': 'X-API-Key'},
                },
            },
            'paths': {
                '/search/': {
                    'get': {
                        'summary': 'Search for a movie or TV title',
                        'security': security,
                        'parameters': [
                            {'name': 'q', 'in': 'query', 'required': True, 'schema': {'type': 'string', 'minLength': 2}},
                            {'name': 'type', 'in': 'query', 'schema': {'type': 'string', 'enum': ['movie', 'tv']}},
                            {'name': 'country', 'in': 'query', 'schema': {'type': 'string', 'default': 'us'}},
                            {'name': 'fields', 'in': 'query', 'schema': {'type': 'string'}},
                        ],
                        'responses': {'200': {'description': 'Media metadata'}, '401': {'description': 'Invalid API key'}},
                    },
                },
                '/batch/': {
                    'post': {
                        'summary': 'Search multiple titles',
                        'security': security,
                        'requestBody': {'required': True, 'content': {'application/json': {'schema': {
                            'type': 'object', 'required': ['items'], 'properties': {'items': {'type': 'array', 'items': {'type': 'object'}}},
                        }}}},
                        'responses': {'200': {'description': 'Batch results'}, '400': {'description': 'Invalid payload'}},
                    },
                },
                '/usage/': {
                    'get': {
                        'summary': 'Read current key usage',
                        'security': security,
                        'responses': {'200': {'description': 'Usage and remaining quota'}},
                    },
                },
                '/search/results/': {
                    'get': {
                        'summary': 'Paginated title search', 'security': security,
                        'parameters': [
                            {'name': 'q', 'in': 'query', 'required': True, 'schema': {'type': 'string'}},
                            {'name': 'type', 'in': 'query', 'schema': {'type': 'string', 'enum': ['movie', 'tv']}},
                            {'name': 'page', 'in': 'query', 'schema': {'type': 'integer', 'minimum': 1}},
                            {'name': 'year', 'in': 'query', 'schema': {'type': 'integer'}},
                            {'name': 'genre', 'in': 'query', 'schema': {'type': 'integer'}},
                        ],
                        'responses': {'200': {'description': 'Paginated media results'}},
                    },
                },
                '/media/{media_type}/{media_id}/': {
                    'get': {
                        'summary': 'Media details, recommendations and watch providers',
                        'security': security,
                        'parameters': [
                            {'name': 'media_type', 'in': 'path', 'required': True, 'schema': {'type': 'string', 'enum': ['movie', 'tv']}},
                            {'name': 'media_id', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}},
                            {'name': 'country', 'in': 'query', 'schema': {'type': 'string', 'default': 'US'}},
                        ],
                        'responses': {'200': {'description': 'Detailed media record'}},
                    },
                },
                '/trending/': {
                    'get': {'summary': 'Weekly trending media', 'security': security, 'responses': {'200': {'description': 'Trending results'}}},
                },
                '/people/search/': {
                    'get': {'summary': 'Search cast and creators', 'security': security, 'responses': {'200': {'description': 'People results'}}},
                },
            },
        }
        return JsonResponse(schema)


class SwaggerUIView(View):
    def get(self, request, *args, **kwargs):
        return HttpResponse("""<!doctype html>
<html><head><title>Linkify Media API</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
</head><body><div id="swagger-ui"></div>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>SwaggerUIBundle({url:'/api/schema/',dom_id:'#swagger-ui',deepLinking:true,persistAuthorization:false});</script>
</body></html>""", content_type='text/html')


# ─────────────────────────────────────────
# Lemon Squeezy Billing Views
# ─────────────────────────────────────────

class BillingView(LoginRequiredMixin, TemplateView):
    template_name = "billing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, _ = Profile.objects.get_or_create(user=self.request.user)
        context['profile'] = profile
        context['billing_configured'] = all([
            settings.LEMONSQUEEZY_API_KEY,
            settings.LEMONSQUEEZY_STORE_ID,
            settings.LEMONSQUEEZY_VARIANT_PRO,
            settings.LEMONSQUEEZY_VARIANT_BIZ,
            settings.LEMONSQUEEZY_WEBHOOK_SECRET,
        ])
        return context

class CreateLemonSqueezyCheckoutView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        if not EmailAddress.objects.filter(
            user=request.user,
            email__iexact=request.user.email,
            verified=True,
        ).exists():
            messages.error(request, 'Verify your email before starting checkout.')
            return redirect('billing')
        tier = request.POST.get('tier')
        
        VARIANT_IDS = {
            'pro': settings.LEMONSQUEEZY_VARIANT_PRO,
            'business': settings.LEMONSQUEEZY_VARIANT_BIZ,
        }

        if tier not in VARIANT_IDS:
            return redirect('billing')

        api_key = settings.LEMONSQUEEZY_API_KEY
        store_id = settings.LEMONSQUEEZY_STORE_ID
        if not api_key or not store_id or not VARIANT_IDS[tier]:
            messages.error(request, 'Billing is not configured yet. Please contact support.')
            return redirect('billing')

        # Lemon Squeezy API Checkouts creation
        url = "https://api.lemonsqueezy.com/v1/checkouts"
        headers = {
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/vnd.api+json",
            "Authorization": f"Bearer {api_key}"
        }
        
        payload = {
            "data": {
                "type": "checkouts",
                "attributes": {
                    "checkout_data": {
                        "email": request.user.email,
                        "custom": {
                            "user_id": str(request.user.id),
                            "tier": tier
                        }
                    }
                },
                "relationships": {
                    "store": {
                        "data": {"type": "stores", "id": str(store_id)}
                    },
                    "variant": {
                        "data": {"type": "variants", "id": str(VARIANT_IDS[tier])}
                    }
                }
            }
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=(5, 20))
            response.raise_for_status()
            response_data = response.json()
            checkout_url = response_data['data']['attributes']['url']
            if not checkout_url.startswith('https://'):
                raise ValueError('Billing provider returned an unsafe checkout URL.')
            return redirect(checkout_url)
        except (requests.RequestException, KeyError, TypeError, ValueError):
            logger.exception('LemonSqueezy checkout creation failed')
            messages.error(request, 'Checkout could not be started. Please try again or contact support.')
            return redirect('billing')


class LemonSqueezyCustomerPortalView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        if not profile.subscription_id or not settings.LEMONSQUEEZY_API_KEY:
            messages.error(request, 'No active subscription portal is available for this account.')
            return redirect('billing')
        try:
            response = requests.get(
                f'https://api.lemonsqueezy.com/v1/subscriptions/{profile.subscription_id}',
                headers={
                    'Accept': 'application/vnd.api+json',
                    'Authorization': f'Bearer {settings.LEMONSQUEEZY_API_KEY}',
                },
                timeout=(5, 20),
            )
            response.raise_for_status()
            portal_url = response.json()['data']['attributes']['urls']['customer_portal']
            if not portal_url.startswith('https://'):
                raise ValueError('Unsafe portal URL')
            return redirect(portal_url)
        except (requests.RequestException, KeyError, TypeError, ValueError):
            logger.exception('LemonSqueezy customer portal lookup failed')
            messages.error(request, 'Subscription portal is temporarily unavailable.')
            return redirect('billing')

@method_decorator(csrf_exempt, name='dispatch')
class LemonSqueezyWebhookView(View):
    def post(self, request, *args, **kwargs):
        payload = request.body
        secret = settings.LEMONSQUEEZY_WEBHOOK_SECRET
        if not secret:
            logger.error('Rejected billing webhook because LEMONSQUEEZY_WEBHOOK_SECRET is missing')
            return JsonResponse({'error': 'Billing webhook is not configured.'}, status=503)

        signature = request.META.get('HTTP_X_SIGNATURE')
        if not signature:
            return HttpResponse(status=401)

        expected_signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            return HttpResponse(status=401)

        try:
            event_data = json.loads(payload)
            meta = event_data.get('meta') or {}
            data = event_data.get('data') or {}
            event_name = str(meta.get('event_name') or '')
            event_id = str(meta.get('event_id') or hashlib.sha256(payload).hexdigest())
            custom_data = meta.get('custom_data') or {}
            user_id = custom_data.get('user_id')
            requested_tier = custom_data.get('tier')
            subscription_id = str(data.get('id') or '')
            attributes = data.get('attributes') or {}
            customer_id = attributes.get('customer_id')
        except (AttributeError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
            return JsonResponse({'error': 'Malformed webhook payload.'}, status=400)

        supported_events = {
            'subscription_created', 'subscription_updated', 'subscription_cancelled',
            'subscription_expired', 'subscription_payment_failed',
        }
        if event_name not in supported_events:
            return HttpResponse(status=200)
        if not user_id:
            return JsonResponse({'error': 'Webhook is missing user metadata.'}, status=400)

        with transaction.atomic():
            _, created = BillingWebhookEvent.objects.get_or_create(
                event_id=event_id,
                defaults={'event_name': event_name},
            )
            if not created:
                return HttpResponse(status=200)
            try:
                profile = Profile.objects.select_for_update().get(user_id=user_id)
            except (Profile.DoesNotExist, ValueError):
                transaction.set_rollback(True)
                return JsonResponse({'error': 'Unknown billing customer.'}, status=404)

            inactive_events = {
                'subscription_cancelled', 'subscription_expired', 'subscription_payment_failed',
            }
            if event_name in inactive_events:
                profile.tier = 'free'
            elif requested_tier in {'pro', 'business'}:
                profile.tier = requested_tier
            else:
                transaction.set_rollback(True)
                return JsonResponse({'error': 'Invalid subscription tier.'}, status=400)
            profile.subscription_id = subscription_id or profile.subscription_id
            if customer_id:
                profile.lemonsqueezy_customer_id = str(customer_id)
            profile.save(update_fields=[
                'tier', 'subscription_id', 'lemonsqueezy_customer_id',
            ])

        return HttpResponse(status=200)

class SupportChatAPIView(APIView):
    permission_classes = []

    @staticmethod
    def _rate_limited(request):
        bucket = int(timezone.now().timestamp() // 3600)
        return throttle(
            f'support-chat:{client_ip(request)}:{bucket}',
            settings.SUPPORT_RATE_LIMIT,
            period=3600,
        )

    def _get_accessible_conversation(self, request, conversation_id):
        try:
            conversation = SupportConversation.objects.get(pk=conversation_id)
        except (SupportConversation.DoesNotExist, ValueError):
            return None, Response({"error": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)

        user = request.user if request.user.is_authenticated else None
        if conversation.user_id not in {None, user.id if user else None}:
            return None, Response({"error": "Conversation access denied."}, status=status.HTTP_403_FORBIDDEN)
        if conversation.user_id is None and request.session.get("support_conversation_id") != str(conversation.pk):
            return None, Response({"error": "Conversation access denied."}, status=status.HTTP_403_FORBIDDEN)
        return conversation, None

    def get(self, request):
        if self._rate_limited(request):
            return Response({'error': 'Support request limit reached. Try again later.'}, status=429)
        conversation_id = request.query_params.get("conversation_id")
        if not conversation_id:
            return Response({"messages": []}, status=status.HTTP_200_OK)
        conversation, error = self._get_accessible_conversation(request, conversation_id)
        if error:
            return error
        return Response(
            {
                "conversation_id": str(conversation.pk),
                "status": conversation.status,
                "messages": [
                    {"role": item.role, "content": item.content, "source": item.source}
                    for item in conversation.messages.order_by("created_at")
                    if item.role in {"user", "assistant"}
                ],
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        if self._rate_limited(request):
            return Response({'error': 'Support request limit reached. Try again later.'}, status=429)
        message = str(request.data.get("message", "")).strip()
        if not message or len(message) > 4000:
            return Response(
                {"error": "message is required and must be 1–4000 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        conversation_id = request.data.get("conversation_id")
        conversation = None
        if conversation_id:
            conversation, error = self._get_accessible_conversation(request, conversation_id)
            if error:
                return error

        user = request.user if request.user.is_authenticated else None
        if conversation is None:
            conversation = SupportConversation.objects.create(
                user=user,
                title=message[:180],
            )

        request.session["support_conversation_id"] = str(conversation.pk)
        SupportMessage.objects.create(
            conversation=conversation,
            role="user",
            content=message,
            source="human",
        )
        result = generate_reply(conversation)
        SupportMessage.objects.create(
            conversation=conversation,
            role="assistant",
            content=result["content"],
            source=result["source"],
        )

        if result["should_escalate"] and conversation.status == "open":
            conversation.status = "escalated"
            conversation.save(update_fields=["status", "updated_at"])

        return Response(
            {
                "conversation_id": str(conversation.pk),
                "message": result["content"],
                "source": result["source"],
                "status": conversation.status,
                "can_escalate": conversation.status != "resolved",
            },
            status=status.HTTP_200_OK,
        )


class SupportTicketCreateAPIView(APIView):
    permission_classes = []

    def post(self, request):
        bucket = int(timezone.now().timestamp() // 3600)
        if throttle(
            f'support-ticket:{client_ip(request)}:{bucket}',
            max(5, settings.SUPPORT_RATE_LIMIT // 2),
            period=3600,
        ):
            return Response({'error': 'Support ticket limit reached. Try again later.'}, status=429)
        conversation_id = request.data.get("conversation_id")
        if not conversation_id:
            return Response({"error": "conversation_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            conversation = SupportConversation.objects.get(pk=conversation_id)
        except (SupportConversation.DoesNotExist, ValueError):
            return Response({"error": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)

        user = request.user if request.user.is_authenticated else None
        if conversation.user_id not in {None, user.id if user else None}:
            return Response({"error": "Conversation access denied."}, status=status.HTTP_403_FORBIDDEN)
        if conversation.user_id is None and request.session.get("support_conversation_id") != str(conversation.pk):
            return Response({"error": "Conversation access denied."}, status=status.HTTP_403_FORBIDDEN)

        name = str(request.data.get("name", "")).strip()
        email = str(request.data.get("email", "")).strip()
        subject = str(request.data.get("subject", "Support request")).strip() or "Support request"
        category = str(request.data.get("category", "general")).strip() or "general"
        extra_message = str(request.data.get("message", "")).strip()

        if user:
            name = name or user.get_full_name() or user.get_username()
            email = email or user.email

        if not name or not email or "@" not in email:
            return Response(
                {"error": "name and a valid email are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        transcript = "\n\n".join(
            f"{item.role.upper()}: {item.content}" for item in conversation.messages.order_by("created_at")[:20]
        )
        ticket_message = extra_message or "Escalated from the Linkify support assistant."
        ticket_message = f"{ticket_message}\n\nConversation transcript:\n{transcript}"[:5000]
        ticket = SupportTicket.objects.create(
            conversation=conversation,
            user=user,
            name=name[:120],
            email=email[:254],
            subject=subject[:180],
            message=ticket_message,
            category=category[:60],
            priority="urgent" if conversation.status == "escalated" else "normal",
        )
        conversation.status = "escalated"
        conversation.save(update_fields=["status", "updated_at"])

        return Response(
            {
                "ticket_id": ticket.id,
                "status": ticket.status,
                "message": "Your request has been escalated to the support team.",
            },
            status=status.HTTP_201_CREATED,
        )


# ─────────────────────────────────────────
# Page Views
# ─────────────────────────────────────────

User = get_user_model()

class LandingPageView(View):
    template_name = "landing.html"

    def get(self, request, *args, **kwargs):
        context = {'demo_token': demo_token() if settings.DEMO_API_ENABLED else ''}
        if request.user.is_authenticated:
            return render(request, self.template_name, context)
        context['form'] = QuickSignUpForm(initial={'email': request.GET.get('email', '')})
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        form = QuickSignUpForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            name = form.cleaned_data['name']
            request.session['pending_signup_name'] = name
            request.session['pending_signup_email'] = email
            return redirect('account_signup')
        return render(request, self.template_name, {
            'form': form,
            'demo_token': demo_token() if settings.DEMO_API_ENABLED else '',
        })

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, _ = Profile.objects.get_or_create(user=self.request.user)
        api_keys = APIKey.objects.filter(user=self.request.user).order_by('-created_at')
        context['api_keys'] = api_keys

        limit_map = {'free': 1, 'pro': 5, 'business': 100}
        max_keys = limit_map.get(profile.tier, 1)
        active_keys = api_keys.filter(is_active=True, revoked_at__isnull=True)
        email_verified = EmailAddress.objects.filter(
            user=self.request.user,
            email__iexact=self.request.user.email,
            verified=True,
        ).exists()
        context['email_verified'] = email_verified
        context['can_create_key'] = email_verified and active_keys.count() < max_keys

        logs = UsageLog.objects.filter(api_key__user=self.request.user)
        today_count = logs.filter(date=timezone.localdate()).count()
        limit = DAILY_LIMITS.get(profile.tier)
        context['usage'] = {
            'tier': profile.tier,
            'today_usage': today_count,
            'daily_limit': limit if limit is not None else 'unlimited',
            'usage_percent': min(100, (today_count / limit * 100)) if limit else 0,
            'active_keys': active_keys.count(),
            'success_rate': 0,
            'avg_latency': 0,
        }
        measured_logs = logs.exclude(status_code__isnull=True)
        measured_count = measured_logs.count()
        if measured_count:
            successful = measured_logs.filter(status_code__lt=400).count()
            context['usage']['success_rate'] = round(successful / measured_count * 100, 1)
            context['usage']['avg_latency'] = round(
                measured_logs.aggregate(value=Avg('latency_ms'))['value'] or 0
            )

        chart_days = [timezone.localdate() - timedelta(days=offset) for offset in range(6, -1, -1)]
        daily_counts = {
            item['date']: item['count']
            for item in logs.filter(date__in=chart_days).values('date').annotate(count=Count('id'))
        }
        context['chart_labels'] = json.dumps([day.strftime('%a') for day in chart_days])
        context['chart_data'] = json.dumps([daily_counts.get(day, 0) for day in chart_days])
        return context

class DocsPageView(TemplateView):
    template_name = "docs.html"

class PrivacyPolicyView(TemplateView):
    template_name = "legal/privacy.html"

class AboutPageView(TemplateView):
    template_name = "about.html"

class TermsOfServiceView(TemplateView):
    template_name = "legal/terms.html"
    
class FAQView(TemplateView):
    template_name = "faq.html"

@method_decorator(ensure_csrf_cookie, name="dispatch")
class SupportView(TemplateView):
    template_name = "support.html"

    def post(self, request, *args, **kwargs):
        if request.POST.get('website'):
            return JsonResponse({'ok': True})
        bucket = int(timezone.now().timestamp() // 3600)
        if throttle(f'support-form:{client_ip(request)}:{bucket}', 5, period=3600):
            return JsonResponse({'ok': False, 'error': 'Too many requests. Try again later.'}, status=429)

        form = SupportRequestForm(request.POST)
        if not form.is_valid():
            error = form.non_field_errors()[0] if form.non_field_errors() else next(iter(form.errors.values()))[0]
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'ok': False, 'error': str(error)}, status=400)
            messages.error(request, str(error))
            return redirect('support')

        ticket = SupportTicket.objects.create(
            user=request.user if request.user.is_authenticated else None,
            **form.cleaned_data,
            priority='urgent' if form.cleaned_data['category'] in {'billing', 'security'} else 'normal',
        )
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': True, 'ticket_id': ticket.pk}, status=201)
        messages.success(request, "Your message has been sent! We'll get back to you soon.")
        return redirect('support')

class UsageLogsListView(LoginRequiredMixin, TemplateView):
    template_name = "usage_logs.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get all logs for the current user's API keys, ordered by newest first
        logs = UsageLog.objects.filter(api_key__user=self.request.user).order_by('-id')[:100]
        context['logs'] = logs
        return context


class UsageLogsCSVView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="linkify-usage.csv"'
        writer = csv.writer(response)
        writer.writerow(['timestamp', 'key', 'method', 'endpoint', 'status', 'latency_ms'])
        logs = UsageLog.objects.filter(api_key__user=request.user).select_related('api_key').order_by('-created_at')
        for log in logs.iterator():
            writer.writerow([
                log.created_at.isoformat(), log.api_key.prefix, log.method, log.endpoint,
                log.status_code or '', log.latency_ms if log.latency_ms is not None else '',
            ])
        return response

# ─────────────────────────────────────────
# Profile & Settings Views
# ─────────────────────────────────────────

class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, _ = Profile.objects.get_or_create(user=self.request.user)
        context['profile'] = profile
        context['email_address'] = self.request.user.emailaddress_set.filter(email=self.request.user.email).first()
        return context

    def post(self, request, *args, **kwargs):
        user = request.user
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        
        user.first_name = first_name
        user.last_name = last_name
        user.save()
        
        messages.success(request, "Profile updated successfully!")
        return redirect('profile')

class ResendVerificationView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        if request.user.emailaddress_set.filter(verified=True).exists():
            messages.info(request, "Your email address is already verified.")
        else:
            email_address, _ = EmailAddress.objects.get_or_create(
                user=request.user,
                email=request.user.email,
                defaults={"primary": True, "verified": False},
            )
            email_address.send_confirmation(request, signup=False)
            messages.success(request, "A new verification email has been sent.")
        return redirect("profile")


class AccountDeleteView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        user = request.user
        confirmation_email = request.POST.get("confirm_email", "").strip().lower()
        password = request.POST.get("password", "")

        if confirmation_email != user.email.lower():
            messages.error(request, "Enter your current email address to confirm account deletion.")
            return redirect("profile")
        if user.has_usable_password() and not user.check_password(password):
            messages.error(request, "The password is incorrect. Your account was not deleted.")
            return redirect("profile")

        logout(request)
        user.delete()
        return redirect("landing-page")


class CustomPasswordChangeView(AllauthPasswordChangeView):
    template_name = "account/password_change.html"
    success_url = reverse_lazy('profile')

    def form_valid(self, form):
        messages.success(self.request, "Password changed successfully!")
        return super().form_valid(form)


class SecureSignupView(AllauthSignupView):
    def get_initial(self):
        initial = super().get_initial()
        pending_email = self.request.session.get('pending_signup_email', '')
        if pending_email:
            initial['email'] = pending_email
        return initial
