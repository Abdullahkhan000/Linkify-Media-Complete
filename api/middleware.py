import time

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone

from .models import APIKey, UsageLog


DAILY_LIMITS = {"free": 100, "pro": 5000, "business": None}
MINUTE_LIMITS = {"free": 20, "pro": 120, "business": 600}
PUBLIC_API_PATHS = {
    "/api/schema/",
    "/api/docs/",
    "/api/health/",
    "/api/ready/",
    "/api/support/chat/",
    "/api/support/ticket/",
}


def client_ip(request):
    return request.META.get("REMOTE_ADDR", "unknown")


def throttle(cache_key, limit, period=60):
    if cache.add(cache_key, 1, timeout=period):
        return False
    try:
        return cache.incr(cache_key) > limit
    except ValueError:
        cache.set(cache_key, 1, timeout=period)
        return False


def demo_token():
    return TimestampSigner(salt="linkify-demo").sign("browser-demo")


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline' "
            "https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' "
            "https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; font-src 'self' data: "
            "https://cdnjs.cloudflare.com; img-src 'self' data: https:; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
        )
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=()",
        )
        return response


class APIKeyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        normalized_path = request.path if request.path.endswith("/") else f"{request.path}/"
        if not normalized_path.startswith("/api/"):
            return self.get_response(request)

        if normalized_path in PUBLIC_API_PATHS or normalized_path.startswith("/api/keys/"):
            return self.get_response(request)

        request_started = time.monotonic()
        raw_demo_token = request.headers.get("X-Demo-Token", "")
        if raw_demo_token:
            error = self._authenticate_demo(request, raw_demo_token)
            if error:
                return error
            return self.get_response(request)

        raw_key = request.headers.get("X-API-Key", "").strip()
        if not raw_key:
            return JsonResponse({"error": "API key missing. Pass the X-API-Key header."}, status=401)

        try:
            key_obj = APIKey.objects.select_related("user__profile").get(
                key_hash=APIKey.digest_secret(raw_key)
            )
        except (APIKey.DoesNotExist, ValidationError, ValueError):
            return JsonResponse({"error": "Invalid or inactive API key."}, status=401)

        if not key_obj.is_usable:
            return JsonResponse({"error": "Invalid, expired, or revoked API key."}, status=401)

        required_scope = self._required_scope(normalized_path)
        if required_scope and not key_obj.has_scope(required_scope):
            return JsonResponse({"error": f"API key is missing the '{required_scope}' scope."}, status=403)

        minute_limit = MINUTE_LIMITS.get(key_obj.tier, MINUTE_LIMITS["free"])
        minute_bucket = int(time.time() // 60)
        if throttle(f"api-rate:{key_obj.pk}:{minute_bucket}", minute_limit):
            return JsonResponse({"error": "Per-minute request limit reached. Retry shortly."}, status=429)

        usage_log, error = self._reserve_usage(key_obj, request, normalized_path)
        if error:
            return error

        request.api_key = key_obj
        request.user = key_obj.user
        response = self.get_response(request)

        elapsed_ms = max(0, int((time.monotonic() - request_started) * 1000))
        UsageLog.objects.filter(pk=usage_log.pk).update(
            status_code=response.status_code,
            latency_ms=elapsed_ms,
        )
        APIKey.objects.filter(pk=key_obj.pk).update(last_used_at=timezone.now())
        return response

    @staticmethod
    def _required_scope(path):
        if "/batch/" in path:
            return "batch"
        if "/usage/" in path:
            return "usage"
        if "/search/" in path:
            return "search"
        if any(segment in path for segment in ("/media/", "/trending/", "/people/")):
            return "search"
        return None

    @staticmethod
    def _authenticate_demo(request, raw_token):
        if not settings.DEMO_API_ENABLED:
            return JsonResponse({"error": "The public demo is disabled."}, status=403)
        try:
            value = TimestampSigner(salt="linkify-demo").unsign(
                raw_token,
                max_age=settings.DEMO_TOKEN_MAX_AGE,
            )
        except (BadSignature, SignatureExpired):
            return JsonResponse({"error": "Demo session expired. Refresh the page."}, status=401)
        if value != "browser-demo":
            return JsonResponse({"error": "Invalid demo session."}, status=401)

        hour_bucket = int(time.time() // 3600)
        if throttle(
            f"demo-rate:{client_ip(request)}:{hour_bucket}",
            settings.DEMO_RATE_LIMIT,
            period=3600,
        ):
            return JsonResponse({"error": "Demo limit reached. Create a free account to continue."}, status=429)
        request.api_key = None
        request.is_demo = True
        return None

    @staticmethod
    def _reserve_usage(key_obj, request, normalized_path):
        limit = DAILY_LIMITS.get(key_obj.tier, DAILY_LIMITS["free"])
        today = timezone.localdate()
        with transaction.atomic():
            locked_key = APIKey.objects.select_for_update().get(pk=key_obj.pk)
            if not locked_key.is_usable:
                return None, JsonResponse({"error": "API key is no longer active."}, status=401)
            if limit is not None:
                usage_today = UsageLog.objects.filter(api_key=locked_key, date=today).count()
                if usage_today >= limit:
                    return None, JsonResponse(
                        {"error": f"{key_obj.tier.title()} tier daily limit of {limit} reached."},
                        status=429,
                    )
            log = UsageLog.objects.create(
                api_key=locked_key,
                endpoint=normalized_path,
                method=request.method[:10],
            )
        return log, None
