from django.contrib import admin
from django.urls import path, include
from api.views import CustomPasswordChangeView, SecureSignupView

urlpatterns = [
    path("", include("api.urls")),

    path("admin/", admin.site.urls),
    path("accounts/password/change/", CustomPasswordChangeView.as_view(), name="account_change_password"),
    path("accounts/signup/", SecureSignupView.as_view(), name="account_signup"),
    path('accounts/', include('allauth.urls')),
]
