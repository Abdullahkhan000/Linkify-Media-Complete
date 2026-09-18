import hashlib
import hmac
import json
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .billing import (
    BillingConfigurationError,
    cancel_subscription,
    create_checkout,
    resume_subscription,
    refresh_subscription,
    update_subscription_variant,
)
from .models import AuditLog, BillingEvent, BillingSubscription, Profile
from .tasks import apply_billing_event, process_billing_event


class CreateLemonSqueezyCheckoutView(LoginRequiredMixin, View):
    login_url = "/accounts/login/"

    def post(self, request, *args, **kwargs):
        tier = request.POST.get("tier", "").strip().lower()
        if tier not in {"pro", "business"}:
            messages.error(request, "Choose a valid subscription plan.")
            return redirect("billing")
        try:
            return redirect(create_checkout(user=request.user, tier=tier))
        except BillingConfigurationError as exc:
            messages.error(request, str(exc))
            return redirect("billing")
        except Exception:
            messages.error(request, "Checkout is temporarily unavailable. Please try again shortly.")
            return redirect("billing")


@method_decorator(csrf_exempt, name="dispatch")
class LemonSqueezyWebhookView(View):
    """Persist and queue Lemon Squeezy events, returning quickly and idempotently."""

    def post(self, request, *args, **kwargs):
        raw_payload = request.body
        secret = getattr(settings, "LEMONSQUEEZY_WEBHOOK_SECRET", "")
        signature = request.META.get("HTTP_X_SIGNATURE", "")
        if not secret or not signature:
            return HttpResponse(status=401)

        expected = hmac.new(secret.encode(), raw_payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return HttpResponse(status=401)

        try:
            payload = json.loads(raw_payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return HttpResponse(status=400)

        meta = payload.get("meta") or {}
        event_name = str(meta.get("event_name") or "unknown")
        provider_event_id = meta.get("webhook_id") or meta.get("id")
        data_id = (payload.get("data") or {}).get("id")
        event_id = str(provider_event_id or (f"{event_name}:{data_id}" if data_id else hashlib.sha256(raw_payload).hexdigest()))
        event, created = BillingEvent.objects.get_or_create(
            event_id=event_id,
            defaults={"event_name": event_name, "payload": payload},
        )
        if created:
            process_billing_event.delay(event.pk)
        return HttpResponse(status=200)


class BillingSubscriptionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        subscription = BillingSubscription.objects.filter(user=request.user).first()
        profile = Profile.objects.get_or_create(user=request.user)[0]
        return Response({
            "tier": profile.tier,
            "subscription_id": profile.subscription_id or "",
            "status": profile.subscription_status or "",
            "renews_at": profile.subscription_renews_at,
            "ends_at": profile.subscription_ends_at,
            "customer_portal_url": profile.customer_portal_url or (subscription.customer_portal_url if subscription else ""),
            "update_payment_method_url": subscription.update_payment_method_url if subscription else "",
        })


class BillingActionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        subscription = BillingSubscription.objects.filter(user=request.user).first()
        if not subscription:
            return Response({"error": "No active subscription found."}, status=404)
        action = str(request.data.get("action", "")).strip().lower()
        try:
            if action == "cancel":
                data = cancel_subscription(subscription.provider_subscription_id)
                event_name = "subscription_cancelled"
            elif action == "resume":
                data = resume_subscription(subscription.provider_subscription_id)
                event_name = "subscription_resumed"
            elif action == "switch":
                tier = str(request.data.get("tier", "")).strip().lower()
                variant_id = {
                    "pro": getattr(settings, "LEMONSQUEEZY_VARIANT_PRO", ""),
                    "business": getattr(settings, "LEMONSQUEEZY_VARIANT_BIZ", ""),
                }.get(tier, "")
                if not variant_id:
                    return Response({"error": "A valid target plan is required."}, status=400)
                data = update_subscription_variant(subscription.provider_subscription_id, variant_id)
                event_name = "subscription_updated"
            else:
                return Response({"error": "Action must be cancel, resume, or switch."}, status=400)
        except Exception:
            return Response({"error": "Lemon Squeezy could not complete this action."}, status=502)

        event = BillingEvent.objects.create(
            event_id=f"dashboard:{uuid.uuid4()}",
            event_name=event_name,
            payload={"meta": {"custom_data": {"user_id": request.user.id}}, "data": data},
        )
        apply_billing_event(event)
        event.processed = True
        event.save(update_fields=["processed"])
        AuditLog.objects.create(
            user=request.user,
            action=f"billing.{action}",
            target_type="billing_subscription",
            target_id=str(subscription.pk),
            metadata={"provider_subscription_id": subscription.provider_subscription_id},
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
        )
        return Response({"status": "updated", "subscription": data})


class BillingPortalView(LoginRequiredMixin, View):
    login_url = "/accounts/login/"

    def get(self, request, *args, **kwargs):
        subscription = BillingSubscription.objects.filter(user=request.user).first()
        if not subscription:
            messages.info(request, "Your customer portal link will appear after the first subscription webhook.")
            return redirect("billing")
        try:
            fresh_data = refresh_subscription(subscription.provider_subscription_id)
            event = BillingEvent.objects.create(
                event_id=f"portal-refresh:{subscription.provider_subscription_id}:{uuid.uuid4()}",
                event_name="subscription_updated",
                payload={"meta": {"custom_data": {"user_id": request.user.id}}, "data": fresh_data},
            )
            apply_billing_event(event)
            event.processed = True
            event.save(update_fields=["processed"])
            subscription.refresh_from_db()
        except Exception:
            # A previously persisted URL is still useful if the provider is temporarily unavailable.
            pass
        if not subscription.customer_portal_url:
            messages.info(request, "Lemon Squeezy has not provided a customer portal link yet.")
            return redirect("billing")
        return redirect(subscription.customer_portal_url)
