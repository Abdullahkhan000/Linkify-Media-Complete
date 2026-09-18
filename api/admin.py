from django.contrib import admin
from .models import (
    APIKey,
    BillingWebhookEvent,
    Profile,
    SupportConversation,
    SupportMessage,
    SupportTicket,
    UsageLog,
)

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'tier', 'lemonsqueezy_customer_id', 'subscription_id']
    list_filter = ['tier']
    search_fields = ['user__username', 'user__email']

@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display  = ['user', 'name', 'prefix', 'tier', 'is_active', 'last_used_at', 'created_at']
    list_filter   = ['user__profile__tier', 'is_active']
    search_fields = ['user__username', 'name']
    readonly_fields = ['key_hash', 'prefix', 'created_at', 'last_used_at', 'revoked_at']

@admin.register(UsageLog)
class UsageLogAdmin(admin.ModelAdmin):
    list_display = ['api_key', 'method', 'endpoint', 'status_code', 'latency_ms', 'created_at']
    list_filter = ['date', 'method', 'status_code', 'endpoint']


@admin.register(BillingWebhookEvent)
class BillingWebhookEventAdmin(admin.ModelAdmin):
    list_display = ['event_id', 'event_name', 'processed_at']
    search_fields = ['event_id', 'event_name']
    readonly_fields = ['event_id', 'event_name', 'processed_at']

@admin.register(SupportConversation)
class SupportConversationAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'user', 'status', 'updated_at']
    list_filter = ['status', 'updated_at']
    search_fields = ['title', 'user__username', 'user__email', 'messages__content']
    readonly_fields = ['id', 'session_id', 'created_at', 'updated_at']


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ['conversation', 'role', 'source', 'created_at']
    list_filter = ['role', 'source', 'created_at']
    search_fields = ['content']
    readonly_fields = ['created_at']


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ['subject', 'email', 'category', 'priority', 'status', 'created_at']
    list_filter = ['status', 'priority', 'category', 'created_at']
    search_fields = ['subject', 'email', 'name', 'message']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['priority', 'status']
