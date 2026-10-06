from unittest.mock import patch

from django.db import OperationalError
from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from .errors import FriendlyErrorMiddleware, error_response


@override_settings(SECURE_SSL_REDIRECT=False)
class FriendlyErrorTests(SimpleTestCase):
    def test_error_pages_need_no_database(self):
        for code in (400, 401, 403, 404, 405, 408, 409, 410, 413, 422, 429, 500, 502, 503, 504):
            with self.subTest(code=code):
                response = self.client.get(f"/errors/{code}/")
                self.assertEqual(response.status_code, code)
                self.assertContains(response, f"<b>{code}</b>", status_code=code)
                self.assertEqual(response["Cache-Control"], "no-store")

    def test_missing_page_uses_friendly_404_in_both_modes(self):
        for debug in (True, False):
            with self.subTest(debug=debug), override_settings(DEBUG=debug):
                response = self.client.get("/this-page-does-not-exist/")
                self.assertContains(response, "This page could not be found", status_code=404)
                self.assertNotContains(response, "URLconf", status_code=404)

    def test_database_failure_returns_page_without_exception_details(self):
        self.client.raise_request_exception = False
        for debug in (True, False):
            with self.subTest(debug=debug), override_settings(DEBUG=debug):
                with patch("api.views.DocsPageView.dispatch", side_effect=OperationalError("private-database-path")):
                    with self.assertLogs("django.request", level="ERROR"):
                        response = self.client.get("/docs/")
                self.assertContains(response, "Still developing. Back soon.", status_code=500)
                self.assertNotContains(response, "private-database-path", status_code=500)
                self.assertNotContains(response, "Traceback", status_code=500)

    def test_response_metadata_and_cookies_are_preserved(self):
        response = HttpResponse("old body", status=429)
        response["Retry-After"] = "60"
        response["Content-Length"] = "8"
        response["ETag"] = "old-body"
        response.set_cookie("existing", "value")
        middleware = FriendlyErrorMiddleware(lambda request: response)
        result = middleware(RequestFactory().get("/billing/"))
        self.assertEqual(result.status_code, 429)
        self.assertEqual(result["Retry-After"], "60")
        self.assertEqual(result.cookies["existing"].value, "value")
        self.assertEqual(int(result["Content-Length"]), len(result.content))
        self.assertFalse(result.has_header("ETag"))

    def test_api_errors_are_not_replaced_by_html(self):
        response = JsonResponse({"error": "API key missing."}, status=401)
        middleware = FriendlyErrorMiddleware(lambda request: response)
        result = middleware(RequestFactory().get("/api/search/"))
        self.assertIs(result, response)
        self.assertEqual(result.content, b'{"error": "API key missing."}')

    def test_successful_pages_are_not_modified(self):
        response = HttpResponse("Original page", status=200)
        result = FriendlyErrorMiddleware(lambda request: response)(RequestFactory().get("/docs/"))
        self.assertIs(result, response)
        self.assertEqual(result.content, b"Original page")

    def test_offline_page_has_no_asset_or_database_dependency(self):
        response = self.client.get("/offline/")
        self.assertContains(response, "You are offline")
        self.assertContains(response, "<b>NETWORK</b>")
        self.assertNotContains(response, 'src="')
        self.assertEqual(error_response(503, offline=True).status_code, 200)

    def test_developing_page_and_worker(self):
        self.assertContains(self.client.get("/developing/"), "Still developing", status_code=503)
        worker = self.client.get("/service-worker.js")
        self.assertEqual(worker.status_code, 200)
        self.assertEqual(worker["Service-Worker-Allowed"], "/")
        self.assertIn("application/javascript", worker["Content-Type"])
        self.assertContains(worker, "event.request.mode !== 'navigate'")

    def test_csrf_failure_shows_friendly_403(self):
        from django.test import Client
        response = Client(enforce_csrf_checks=True).post("/accounts/login/", {"login": "test"})
        self.assertContains(response, "Access unavailable", status_code=403)
        self.assertNotContains(response, "CSRF verification failed", status_code=403)
