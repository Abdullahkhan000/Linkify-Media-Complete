from django.urls import path
from .views import (
    APIKeyListCreateView,
    APIKeyDetailView,
    SearchAPIView,
    BatchAPIView,
    UsageAPIView,
    # Page Views
    LandingPageView, 
    DashboardView, 
    DocsPageView, 
    BillingView, 
    ProfileView,
    CreateLemonSqueezyCheckoutView,
    LemonSqueezyWebhookView,
    # New Views
    PrivacyPolicyView,
    AboutPageView,
    TermsOfServiceView,
    SupportView,
    UsageLogsListView,
    FAQView,
    SupportChatAPIView,
    SupportTicketCreateAPIView,
    ResendVerificationView,
    AccountDeleteView,
)

urlpatterns = [
    # Website Pages (HTML)
    path("", LandingPageView.as_view(), name="landing-page"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("about/", AboutPageView.as_view(), name="about-page"),
    path("docs/", DocsPageView.as_view(), name="docs-page"),
    path("billing/", BillingView.as_view(), name="billing"),
    path("billing/checkout/", CreateLemonSqueezyCheckoutView.as_view(), name="checkout"),
    path("billing/webhook/", LemonSqueezyWebhookView.as_view(), name="lemonsqueezy-webhook"),
    
    # New Pages
    path("privacy/", PrivacyPolicyView.as_view(), name="privacy-policy"),
    path("terms/", TermsOfServiceView.as_view(), name="terms-of-service"),
    path("faq/", FAQView.as_view(), name="faq"),
    path("support/", SupportView.as_view(), name="support"),
    path("usage-logs/", UsageLogsListView.as_view(), name="usage-logs"),

    # API Endpoints (JSON)
    path('api/keys/',          APIKeyListCreateView.as_view(), name='apikey-list-create'),
    path('api/keys/<int:pk>/', APIKeyDetailView.as_view()),
    path('api/search/',        SearchAPIView.as_view()),
    path('api/batch/',         BatchAPIView.as_view()),
    path('api/usage/',         UsageAPIView.as_view()),
    path('api/support/chat/',  SupportChatAPIView.as_view(), name='support-chat'),
    path('api/support/ticket/', SupportTicketCreateAPIView.as_view(), name='support-ticket-create'),
    path('account/verification/resend/', ResendVerificationView.as_view(), name='resend-verification'),
    path('account/delete/', AccountDeleteView.as_view(), name='account-delete'),
]