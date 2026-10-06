from django.contrib import admin
from django.urls import path, include
from api.views import CustomPasswordChangeView, SecureSignupView
from api.headless import SecureHeadlessSignupView
from allauth.headless.constants import Client
from . import errors

handler400 = "core.errors.bad_request"
handler403 = "core.errors.permission_denied"
handler404 = "core.errors.page_not_found"
handler500 = "core.errors.server_error"

urlpatterns = [
    path("errors/<int:code>/", errors.preview, name="error-preview"),
    path("developing/", errors.developing, name="developing"),
    path("offline/", errors.offline, name="offline"),
    path("service-worker.js", errors.service_worker, name="service-worker"),
    path("", include("api.urls")),

    path("admin/", admin.site.urls),
    path(
        "_allauth/browser/v1/auth/signup",
        SecureHeadlessSignupView.as_api_view(client=Client.BROWSER),
        name="headless-secure-signup",
    ),
    path("_allauth/", include("allauth.headless.urls")),
    path("accounts/password/change/", CustomPasswordChangeView.as_view(), name="account_change_password"),
    path("accounts/signup/", SecureSignupView.as_view(), name="account_signup"),
    path('accounts/', include('allauth.urls')),
]
