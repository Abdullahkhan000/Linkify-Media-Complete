import json
import secrets
import uuid
from datetime import date, timedelta
from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.text import slugify
from django.views import View
from django.views.generic import TemplateView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .tasks import deliver_webhook, enqueue_webhook_delivery

from .models import (
    APIKey,
    AuditLog,
    Profile,
    StatusIncident,
    Team,
    TeamInvitation,
    TeamMembership,
    UsageLog,
    WebhookDelivery,
    WebhookEndpoint,
)


PLANS = {
    "free": {"label": "Free", "daily_requests": 100, "max_keys": 1, "max_webhooks": 1, "max_members": 1, "price": 0},
    "pro": {"label": "Pro", "daily_requests": 5000, "max_keys": 5, "max_webhooks": 10, "max_members": 5, "price": 19},
    "business": {"label": "Business", "daily_requests": None, "max_keys": 100, "max_webhooks": 50, "max_members": 25, "price": 79},
}


def plan_for(user):
    tier = getattr(getattr(user, "profile", None), "tier", "free")
    return tier, PLANS.get(tier, PLANS["free"])


def audit(request, action, target_type="", target_id="", metadata=None):
    AuditLog.objects.create(
        user=request.user if request.user.is_authenticated else None,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        metadata=metadata or {},
        ip_address=request.META.get("REMOTE_ADDR"),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
    )


class PlatformDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "platform_dashboard.html"
    login_url = "/accounts/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tier, plan = plan_for(self.request.user)
        keys = APIKey.objects.filter(user=self.request.user)
        logs = UsageLog.objects.filter(api_key__user=self.request.user)
        today = date.today()
        week = [today - timedelta(days=index) for index in range(6, -1, -1)]
        counts = {item["date"]: item["count"] for item in logs.filter(date__gte=week[0]).values("date").annotate(count=Count("id"))}
        context.update({
            "platform_plan": plan,
            "platform_tier": tier,
            "platform_keys": keys,
            "platform_key_count": keys.count(),
            "platform_webhooks": WebhookEndpoint.objects.filter(user=self.request.user),
            "platform_teams": TeamMembership.objects.filter(user=self.request.user).select_related("team"),
            "platform_today": logs.filter(date=today).count(),
            "platform_week_total": logs.filter(date__gte=week[0]).count(),
            "platform_week_labels": json.dumps([item.strftime("%a") for item in week]),
            "platform_week_values": json.dumps([counts.get(item, 0) for item in week]),
            "platform_plan_json": json.dumps(plan),
            "onboarding_complete": self.request.user.profile.onboarding_completed,
        })
        return context


class PlatformAnalyticsView(PlatformDashboardView):
    template_name = "analytics.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        logs = UsageLog.objects.filter(api_key__user=self.request.user)
        context["analytics_endpoints"] = list(logs.values("endpoint").annotate(total=Count("id")).order_by("-total")[:10])
        context["analytics_status"] = list(logs.values("status_code").annotate(total=Count("id")).order_by("-total"))
        context["analytics_average_latency"] = round(sum(log.latency_ms for log in logs[:500]) / max(logs[:500].count(), 1))
        return context


class PlaygroundView(LoginRequiredMixin, TemplateView):
    template_name = "playground.html"
    login_url = "/accounts/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["api_keys"] = APIKey.objects.filter(user=self.request.user, is_active=True)
        context["plans"] = PLANS
        return context


class PricingView(TemplateView):
    template_name = "pricing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["plans"] = PLANS
        return context


class TeamWorkspaceView(LoginRequiredMixin, TemplateView):
    template_name = "teams.html"
    login_url = "/accounts/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teams = TeamMembership.objects.filter(user=self.request.user).select_related("team")
        context["teams"] = teams
        context["team_invites"] = TeamInvitation.objects.filter(team__memberships__user=self.request.user, status="pending").select_related("team")
        context["team_plan"] = plan_for(self.request.user)[1]
        return context

    def post(self, request, *args, **kwargs):
        name = request.POST.get("name", "").strip()
        if not name:
            messages.error(request, "Team name is required.")
            return redirect("teams")
        tier, plan = plan_for(request.user)
        if Team.objects.filter(owner=request.user).count() >= 1 and tier == "free":
            messages.error(request, "Upgrade to Pro to create a team workspace.")
            return redirect("pricing")
        base_slug = slugify(name) or "team"
        slug = base_slug
        index = 2
        while Team.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{index}"
            index += 1
        team = Team.objects.create(owner=request.user, name=name[:120], slug=slug)
        TeamMembership.objects.create(team=team, user=request.user, role="owner")
        audit(request, "team.created", "team", team.id, {"name": team.name})
        messages.success(request, "Team workspace created.")
        return redirect("teams")


class TeamInviteAcceptView(LoginRequiredMixin, View):
    login_url = "/accounts/login/"

    def get(self, request, token):
        invite = get_object_or_404(TeamInvitation, token=token, status="pending")
        if invite.email.lower() != request.user.email.lower():
            messages.error(request, "This invitation was sent to a different email address.")
            return redirect("teams")
        TeamMembership.objects.get_or_create(team=invite.team, user=request.user, defaults={"role": invite.role})
        invite.status = "accepted"
        invite.save(update_fields=["status"])
        audit(request, "team.invitation_accepted", "team", invite.team_id)
        messages.success(request, f"You joined {invite.team.name}.")
        return redirect("teams")


class TeamInviteAPIView(APIView):
    permission_classes = [IsAuthenticated]
    login_url = "/accounts/login/"

    def post(self, request):
        team = get_object_or_404(Team, pk=request.data.get("team_id"))
        membership = get_object_or_404(TeamMembership, team=team, user=request.user)
        if membership.role not in {"owner", "admin"}:
            return Response({"error": "Only team owners and admins can invite members."}, status=403)
        _, plan = plan_for(request.user)
        if team.memberships.count() + team.invitations.filter(status="pending").count() >= plan["max_members"]:
            return Response({"error": "Your plan member limit has been reached."}, status=400)
        email = str(request.data.get("email", "")).strip().lower()
        role = str(request.data.get("role", "developer"))
        if "@" not in email or role not in {"admin", "developer", "viewer"}:
            return Response({"error": "A valid email and role are required."}, status=400)
        invite, _ = TeamInvitation.objects.update_or_create(team=team, email=email, status="pending", defaults={"role": role})
        audit(request, "team.invitation_created", "team", team.id, {"email": email, "role": role})
        return Response({"message": "Invitation created.", "token": str(invite.token)}, status=201)


class TeamMemberRemoveAPIView(APIView):
    permission_classes = [IsAuthenticated]
    login_url = "/accounts/login/"

    def delete(self, request, membership_id):
        membership = get_object_or_404(TeamMembership, pk=membership_id)
        actor = get_object_or_404(TeamMembership, team=membership.team, user=request.user)
        if actor.role not in {"owner", "admin"} or membership.role == "owner":
            return Response({"error": "You cannot remove this member."}, status=403)
        membership.delete()
        audit(request, "team.member_removed", "team", membership.team_id, {"user_id": membership.user_id})
        return Response(status=204)


class OnboardingAPIView(APIView):
    permission_classes = [IsAuthenticated]
    login_url = "/accounts/login/"

    def post(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        profile.company_name = str(request.data.get("company_name", profile.company_name)).strip()[:160]
        profile.job_title = str(request.data.get("job_title", profile.job_title)).strip()[:120]
        profile.onboarding_completed = bool(request.data.get("completed", True))
        profile.save(update_fields=["company_name", "job_title", "onboarding_completed"])
        audit(request, "onboarding.completed", "profile", profile.id)
        return Response({"completed": profile.onboarding_completed})


class AuditLogAPIView(APIView):
    permission_classes = [IsAuthenticated]
    login_url = "/accounts/login/"

    def get(self, request):
        logs = AuditLog.objects.filter(user=request.user)[:100]
        return Response([{"action": item.action, "target_type": item.target_type, "target_id": item.target_id, "metadata": item.metadata, "created_at": item.created_at.isoformat()} for item in logs])


class APIKeyRotateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    login_url = "/accounts/login/"

    def post(self, request, pk):
        key = get_object_or_404(APIKey, pk=pk, user=request.user)
        key.key = uuid.uuid4()
        key.save(update_fields=["key"])
        audit(request, "api_key.rotated", "api_key", key.id, {"name": key.name})
        return Response({"id": key.id, "key": key.key, "name": key.name})


class APIKeyRevokeAPIView(APIView):
    permission_classes = [IsAuthenticated]
    login_url = "/accounts/login/"

    def post(self, request, pk):
        key = get_object_or_404(APIKey, pk=pk, user=request.user)
        key.is_active = False
        key.save(update_fields=["is_active"])
        audit(request, "api_key.revoked", "api_key", key.id, {"name": key.name})
        return Response({"status": "revoked"})


class WebhookPageView(LoginRequiredMixin, TemplateView):
    template_name = "webhooks.html"
    login_url = "/accounts/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["endpoints"] = WebhookEndpoint.objects.filter(user=self.request.user)
        context["deliveries"] = WebhookDelivery.objects.filter(endpoint__user=self.request.user).select_related("endpoint")[:50]
        return context


class AuditPageView(LoginRequiredMixin, TemplateView):
    template_name = "audit.html"
    login_url = "/accounts/login/"


class WebhookEndpointAPIView(APIView):
    permission_classes = [IsAuthenticated]
    login_url = "/accounts/login/"

    def get(self, request):
        endpoints = WebhookEndpoint.objects.filter(user=request.user)
        return Response([{"id": item.id, "name": item.name, "url": item.url, "events": item.events, "is_active": item.is_active, "failure_count": item.failure_count, "last_delivery_at": item.last_delivery_at} for item in endpoints])

    def post(self, request):
        _, plan = plan_for(request.user)
        if WebhookEndpoint.objects.filter(user=request.user).count() >= plan["max_webhooks"]:
            return Response({"error": "Your plan webhook limit has been reached."}, status=400)
        name = str(request.data.get("name", "")).strip()[:120]
        url = str(request.data.get("url", "")).strip()
        events = request.data.get("events", ["media.completed", "media.failed"])
        if not name or urlparse(url).scheme not in {"http", "https"}:
            return Response({"error": "A name and valid HTTP(S) URL are required."}, status=400)
        endpoint = WebhookEndpoint.objects.create(user=request.user, name=name, url=url, secret="whsec_" + secrets.token_urlsafe(24), events=events if isinstance(events, list) else [])
        audit(request, "webhook.created", "webhook", endpoint.id, {"url": url})
        return Response({"id": endpoint.id, "name": endpoint.name, "url": endpoint.url, "secret": endpoint.secret, "events": endpoint.events}, status=201)


class WebhookEndpointDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]
    login_url = "/accounts/login/"

    def delete(self, request, pk):
        endpoint = get_object_or_404(WebhookEndpoint, pk=pk, user=request.user)
        endpoint.delete()
        audit(request, "webhook.deleted", "webhook", pk)
        return Response(status=204)

    def patch(self, request, pk):
        endpoint = get_object_or_404(WebhookEndpoint, pk=pk, user=request.user)
        if "is_active" in request.data:
            endpoint.is_active = bool(request.data["is_active"])
        if "events" in request.data and isinstance(request.data["events"], list):
            endpoint.events = request.data["events"]
        endpoint.save(update_fields=["is_active", "events"])
        return Response({"id": endpoint.id, "is_active": endpoint.is_active, "events": endpoint.events})


class WebhookTestAPIView(APIView):
    permission_classes = [IsAuthenticated]
    login_url = "/accounts/login/"

    def post(self, request, pk):
        endpoint = get_object_or_404(WebhookEndpoint, pk=pk, user=request.user)
        event = "endpoint.test"
        body = {
            "id": secrets.token_hex(12),
            "type": event,
            "created_at": timezone.now().isoformat(),
            "data": {"message": "Linkify webhook test"},
        }
        delivery = enqueue_webhook_delivery(endpoint, event, body)
        audit(request, "webhook.queued", "webhook", endpoint.id, {"delivery_id": delivery.id})
        return Response(
            {
                "queued": True,
                "delivery_id": delivery.id,
                "status": "queued",
                "message": "Webhook delivery queued for background processing.",
            },
            status=202,
        )


class WebhookRetryAPIView(APIView):
    permission_classes = [IsAuthenticated]
    login_url = "/accounts/login/"

    def post(self, request, pk):
        delivery = get_object_or_404(WebhookDelivery, pk=pk, endpoint__user=request.user)
        if delivery.success:
            return Response({"error": "This delivery already succeeded."}, status=400)
        delivery.completed_at = None
        delivery.next_attempt_at = timezone.now()
        delivery.last_error = ""
        delivery.save(update_fields=["completed_at", "next_attempt_at", "last_error"])
        deliver_webhook.delay(delivery.pk)
        audit(request, "webhook.retry_queued", "webhook_delivery", delivery.pk)
        return Response({"queued": True, "delivery_id": delivery.pk}, status=202)


class StatusAPIView(APIView):
    permission_classes = []

    def get(self, request):
        incidents = StatusIncident.objects.exclude(status="resolved")[:10]
        return Response({"status": "operational" if not incidents else "degraded", "services": [{"name": "Media Search API", "status": "operational"}, {"name": "API Dashboard", "status": "operational"}, {"name": "Authentication", "status": "operational"}], "incidents": [{"title": item.title, "status": item.status, "impact": item.impact, "message": item.message, "started_at": item.started_at.isoformat()} for item in incidents]})


class StatusPageView(TemplateView):
    template_name = "status.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["incidents"] = StatusIncident.objects.all()[:20]
        context["active_incidents"] = StatusIncident.objects.exclude(status="resolved").count()
        return context


class OpenAPISchemaView(View):
    def get(self, request):
        schema = {
            "openapi": "3.0.3",
            "info": {"title": "Linkify Media API", "version": "1.0.0", "description": "Verified media metadata and link discovery API."},
            "servers": [{"url": request.build_absolute_uri("/").rstrip("/")}],
            "components": {"securitySchemes": {"ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"}}},
            "paths": {
                "/api/search/": {"get": {"summary": "Search for media", "security": [{"ApiKeyAuth": []}], "parameters": [{"name": "q", "in": "query", "required": True, "schema": {"type": "string"}}, {"name": "type", "in": "query", "schema": {"type": "string", "default": "movie"}}], "responses": {"200": {"description": "Media result"}, "401": {"description": "Invalid API key"}}}},
                "/api/batch/": {"post": {"summary": "Search multiple media items", "security": [{"ApiKeyAuth": []}], "responses": {"200": {"description": "Batch results"}}}},
                "/api/usage/": {"get": {"summary": "Get key usage", "security": [{"ApiKeyAuth": []}], "responses": {"200": {"description": "Usage metrics"}}}},
            },
        }
        return JsonResponse(schema)


class APIReferenceView(TemplateView):
    template_name = "api_reference.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["schema_url"] = self.request.build_absolute_uri("/api/schema/")
        return context
