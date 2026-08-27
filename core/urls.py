from django.contrib import admin
from django.urls import path, include
from api.views import CustomPasswordChangeView

urlpatterns = [
    path("", include("api.urls")),

    path("admin/", admin.site.urls),
    path("accounts/password/change/", CustomPasswordChangeView.as_view(), name="account_change_password"),
    path('accounts/', include('allauth.urls')),
]