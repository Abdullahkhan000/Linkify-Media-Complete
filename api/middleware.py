from datetime import date

from django.core.exceptions import ValidationError
from django.http import JsonResponse

from .models import APIKey


class APIKeyMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith('/api/'):
            return self.get_response(request)

        # Swagger/OpenAPI documentation routes public rahengi.
        public_api_paths = {
            '/api/schema',
            '/api/schema/',
            '/api/docs',
            '/api/docs/',
            '/api/redoc',
            '/api/redoc/',
            '/api/support/chat/',
            '/api/support/ticket/',
        }
        if request.path in public_api_paths:
            return self.get_response(request)

        # API key management session/login authentication se protected hai.
        if request.path.startswith('/api/keys/'):
            return self.get_response(request)

        api_key = request.headers.get('X-API-Key')

        if not api_key:
            return JsonResponse(
                {'error': 'API key missing. Pass X-API-Key header.'},
                status=401
            )

        if api_key == 'demo_key':
            request.api_key = None
            request.is_demo = True
            return self.get_response(request)

        try:
            key_obj = APIKey.objects.select_related('user__profile').get(
                key=api_key,
                is_active=True
            )
        except (APIKey.DoesNotExist, ValidationError, ValueError):
            return JsonResponse(
                {'error': 'Invalid or inactive API key.'},
                status=401
            )

        # Rate limit check
        # Free = 100/day, Pro = 5000/day, Business = unlimited
        DAILY_LIMITS = {
            'free': 100,
            'pro': 5000,
            'business': None,
        }

        limit = DAILY_LIMITS.get(key_obj.tier)

        if limit is not None:
            today = date.today()
            usage_today = key_obj.usagelogs.filter(date=today).count()

            if usage_today >= limit:
                return JsonResponse(
                    {
                        'error': (
                            f'{key_obj.tier.title()} tier limit {limit}/day reached. '
                            'Upgrade your plan.'
                        )
                    },
                    status=429
                )

        request.api_key = key_obj
        request.user = key_obj.user

        return self.get_response(request)
