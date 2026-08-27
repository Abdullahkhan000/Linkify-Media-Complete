from django.contrib import admin
from .models import APIKey, Profile, UsageLog, SupportTicket

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'tier', 'lemonsqueezy_customer_id', 'subscription_id']
    list_filter = ['tier']
    search_fields = ['user__username', 'user__email']

@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display  = ['user', 'name', 'tier', 'is_active', 'created_at']
    list_filter   = ['user__profile__tier', 'is_active']
    search_fields = ['user__username', 'name']
    readonly_fields = ['key', 'created_at']

@admin.register(UsageLog)
class UsageLogAdmin(admin.ModelAdmin):
    list_display = ['api_key', 'endpoint', 'date']
    list_filter = ['date', 'endpoint']

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ['subject', 'email', 'category', 'priority', 'status', 'created_at']
    list_filter = ['status', 'priority', 'category', 'created_at']
    search_fields = ['subject', 'email', 'name', 'message']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['priority', 'status']
