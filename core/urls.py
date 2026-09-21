from django.contrib import admin
from django.urls import path, include
from api.views import CustomPasswordChangeView, SecureSignupView
from api.headless import SecureHeadlessSignupView
from allauth.headless.constants import Client

urlpatterns = [
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
