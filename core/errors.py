"""Database-independent error pages and an offline navigation fallback."""
from pathlib import Path

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.template import Context, engines
from django.views.decorators.http import require_GET
from django.views.defaults import server_error as default_server_error


ERROR_MESSAGES = {
    400: ("Request not understood", "Please check the address or information you entered and try again."),
    401: ("Sign in to continue", "This page needs an authenticated session. Please sign in and try again."),
    403: ("Access unavailable", "You do not have access to this request, or your form session has expired."),
    404: ("This page could not be found", "The address may have changed, or this page is not available yet."),
    405: ("This action is not available", "This page does not accept that request. Return to the site and try again."),
    408: ("The request took too long", "Please check your connection and try again in a moment."),
    409: ("Something has changed", "Refresh the page to get the latest information before trying again."),
    410: ("This page is no longer available", "This address is no longer in use. You can continue from the home page."),
    413: ("This request is too large", "Please reduce the size of your request and try again."),
    422: ("Please check your information", "Some of the information could not be accepted. Return to the form and check it."),
    429: ("A little too many requests", "Please wait a moment before trying again."),
    500: ("Something went wrong", "We could not load this page due to a server error. Please try again shortly."),
    502: ("A service is taking a break", "We could not reach a service we need. Please try again shortly."),
    503: ("Service temporarily unavailable", "The service is temporarily unavailable. Please try again shortly."),
    504: ("The service took too long", "A service did not respond in time. Please try again in a moment."),
}


def error_response(code, *, offline=False, developing=False):
    if code == 500 and not settings.CUSTOM_500_PAGE_ENABLED and not offline:
        response = default_server_error(HttpRequest())
        response['Cache-Control'] = 'no-store'
        return response
    title, description = ERROR_MESSAGES.get(code, (
        "We could not complete this request", "Please try again, or return to the home page."
    ))
    if developing:
        title = "Still developing. Back soon."
        description = "This part of Linkify Media is still being developed. Please check back soon."
    if offline:
        title = "You are offline"
        description = "Your connection is unavailable. Check your internet connection, then retry this page."
    context = {
        "code": "NETWORK" if offline else code,
        "title": title,
        "description": description,
        "category": "Connection unavailable" if offline else ("Service in progress" if developing else ("Service error" if code >= 500 else "Let's get you back")),
        "offline": offline,
        "developing": developing,
    }
    # Do not use RequestContext: authentication and social-provider processors
    # can depend on the same database that caused the original error.
    template = engines["django"].engine.get_template("errors/page.html")
    response = HttpResponse(template.render(Context(context)), status=200 if offline else code)
    response["Cache-Control"] = "no-store"
    response.linkify_developing = developing
    return response


def bad_request(request, exception=None):
    return error_response(400)


def permission_denied(request, exception=None):
    return error_response(403)


def page_not_found(request, exception=None):
    return error_response(404)


def server_error(request):
    if request.path.startswith("/api/"):
        return JsonResponse({"error": "Service temporarily unavailable.", "code": 500}, status=500)
    return error_response(500)


def csrf_failure(request, reason=""):
    return error_response(403)


@require_GET
def preview(request, code):
    return error_response(code if 400 <= code <= 599 else 404)


@require_GET
def developing(request):
    return error_response(503, developing=True)


@require_GET
def offline(request):
    return error_response(503, offline=True)


@require_GET
def service_worker(request):
    source = Path(settings.BASE_DIR) / "static" / "js" / "offline-worker.js"
    response = HttpResponse(source.read_text(encoding="utf-8"), content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response


class FriendlyErrorMiddleware:
    """Replace HTML error bodies, keeping status codes and response headers."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (
            request.path.startswith(("/api/", "/_allauth/", "/static/", "/media/"))
            or response.streaming
            or (response.status_code == 500 and not settings.CUSTOM_500_PAGE_ENABLED)
            or not 400 <= response.status_code <= 599
            or "text/html" not in response.get("Content-Type", "")
        ):
            return response
        response.content = error_response(
            response.status_code,
            developing=getattr(response, "linkify_developing", False),
        ).content
        if response.has_header("Content-Length"):
            response["Content-Length"] = str(len(response.content))
        if response.has_header("ETag"):
            del response["ETag"]
        response["Cache-Control"] = "no-store"
        return response
