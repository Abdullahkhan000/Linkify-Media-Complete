from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import APIKey, UsageLog, Profile, SupportConversation, SupportMessage, SupportTicket
from .serializers import APIKeySerializer
from .core import fetch_media_links, filter_fields
import asyncio
import secrets
import hashlib
import hmac
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.base import View, TemplateView
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from asgiref.sync import sync_to_async, async_to_sync
from datetime import date, timedelta
from django.db.models import Count
import json
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django.conf import settings
from django.http import HttpResponse, JsonResponse
import requests

from .forms import QuickSignUpForm
from .support_bot import generate_reply

# ─────────────────────────────────────────
# API Key CRUD Views
# ─────────────────────────────────────────

class APIKeyListCreateView(LoginRequiredMixin, APIView):
    login_url = '/accounts/login/'

    def get(self, request):
        keys = APIKey.objects.filter(user=request.user)
        serializer = APIKeySerializer(keys, many=True)
        return Response(serializer.data)

    def post(self, request):
        limit_map = {'free': 1, 'pro': 5, 'business': 100}
        max_keys = limit_map.get(request.user.profile.tier, 1)
        
        existing = APIKey.objects.filter(user=request.user).count()
        if existing >= max_keys:
            return Response(
                {'error': f'Your current plan ({request.user.profile.tier}) allows only {max_keys} API key(s). Upgrade for more.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = APIKeySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class APIKeyDetailView(LoginRequiredMixin, APIView):
    login_url = '/accounts/login/'

    def get_object(self, pk, user):
        try:
            return APIKey.objects.get(pk=pk, user=user)
        except APIKey.DoesNotExist:
            return None

    def patch(self, request, pk):
        key = self.get_object(pk, request.user)
        if not key:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = APIKeySerializer(key, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        key = self.get_object(pk, request.user)
        if not key:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        key.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─────────────────────────────────────────
# Linkify Core Views
# ─────────────────────────────────────────

class SearchAPIView(APIView):
    permission_classes = []

    def get(self, request):
        is_demo = getattr(request, 'is_demo', False)
        if not getattr(request, 'api_key', None) and not is_demo:
            return Response({'error': 'API Key missing or invalid.'}, status=401)

        query = request.GET.get('q', '').strip()
        raw_type = (request.GET.get('type') or 'movie').strip().lower()
        country = (request.GET.get('country') or 'us').strip().lower()
        fields_param = request.GET.get('fields', '').strip()

        if not query or len(query) < 2:
            return Response({'error': 'Search query "q" must be at least 2 characters long.'}, status=400)

        # Strict media type validation & mapping
        TYPE_MAP = {
            'movie': 'movie',
            'film': 'movie',
            'tv': 'tv',
            'show': 'tv',
            'series': 'tv',
            'anime': 'tv',
            'tvshow': 'tv',
            'tv show': 'tv',
        }

        if raw_type not in TYPE_MAP:
            return Response({
                'error': f"Invalid media type '{raw_type}'. Supported types: 'movie', 'tv', 'show', 'anime', 'series'."
            }, status=400)

        media_type = TYPE_MAP[raw_type]

        result = async_to_sync(fetch_media_links)(query, media_type, country=country)

        if not result:
            return Response({'error': f"No verified media found matching '{query}'."}, status=404)

        if isinstance(result, dict) and "Error" in result:
            return Response({'error': result["Error"]}, status=404)

        if fields_param and isinstance(result, dict):
            result = filter_fields(result, fields_param)

        if not is_demo and getattr(request, 'api_key', None):
            UsageLog.objects.create(
                api_key=request.api_key,
                endpoint='/api/search/'
            )

        return Response(result, status=200)


class BatchAPIView(APIView):
    permission_classes = []

    def post(self, request):
        is_demo = getattr(request, 'is_demo', False)
        api_key = getattr(request, 'api_key', None)

        if not api_key and not is_demo:
            return Response({'error': 'API Key missing or invalid.'}, status=401)

        tier = api_key.tier if api_key else ('pro' if is_demo else 'free')

        if tier == 'free':
            return Response({'error': 'Batch endpoint is available on Pro and Business plans only.'}, status=403)

        items = request.data.get('items')
        if not items or not isinstance(items, list):
            return Response({'error': 'items list array required.'}, status=400)

        async def run_batch():
            tasks = [
                fetch_media_links(
                    item.get('q', ''),
                    item.get('type', 'movie'),
                    country=item.get('country', 'us')
                ) for item in items
            ]
            raw_results = await asyncio.gather(*tasks)
            final_results = []
            for idx, res in enumerate(raw_results):
                req_fields = items[idx].get('fields')
                if req_fields and isinstance(res, dict):
                    final_results.append(filter_fields(res, req_fields))
                else:
                    final_results.append(res)
            return final_results

        results = async_to_sync(run_batch)()

        if not is_demo and api_key:
            UsageLog.objects.create(
                api_key=api_key,
                endpoint='/api/batch/'
            )

        return Response({'results': results}, status=200)


class UsageAPIView(APIView):
    permission_classes = []

    def get(self, request):
        if not getattr(request, 'api_key', None):
            return Response({'error': 'API Key missing or invalid.'}, status=401)

        today = date.today()
        LIMITS = {'free': 100, 'pro': 5000, 'business': None}
        limit = LIMITS.get(request.api_key.tier)

        today_count = UsageLog.objects.filter(api_key=request.api_key, date=today).count()

        return Response({
            'tier': request.api_key.tier,
            'today_usage': today_count,
            'daily_limit': limit if limit else 'unlimited',
            'remaining': (limit - today_count) if limit else 'unlimited',
        })


# ─────────────────────────────────────────
# Lemon Squeezy Billing Views
# ─────────────────────────────────────────

class BillingView(LoginRequiredMixin, TemplateView):
    template_name = "billing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, _ = Profile.objects.get_or_create(user=self.request.user)
        context['profile'] = profile
        return context

class CreateLemonSqueezyCheckoutView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        tier = request.POST.get('tier')
        
        # Lemon Squeezy Variant IDs (Replace these with your actual IDs)
        VARIANT_IDS = {
            'pro': getattr(settings, 'LEMONSQUEEZY_VARIANT_PRO', 'variant_pro_id'),
            'business': getattr(settings, 'LEMONSQUEEZY_VARIANT_BIZ', 'variant_biz_id'),
        }

        if tier not in VARIANT_IDS:
            return redirect('billing')

        api_key = getattr(settings, 'LEMONSQUEEZY_API_KEY', '')
        store_id = getattr(settings, 'LEMONSQUEEZY_STORE_ID', '')

        # Lemon Squeezy API Checkouts creation
        url = "https://api.lemonsqueezy.com/v1/checkouts"
        headers = {
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/vnd.api+json",
            "Authorization": f"Bearer {api_key}"
        }
        
        payload = {
            "data": {
                "type": "checkouts",
                "attributes": {
                    "checkout_data": {
                        "email": request.user.email,
                        "custom": {
                            "user_id": str(request.user.id),
                            "tier": tier
                        }
                    }
                },
                "relationships": {
                    "store": {
                        "data": {"type": "stores", "id": str(store_id)}
                    },
                    "variant": {
                        "data": {"type": "variants", "id": str(VARIANT_IDS[tier])}
                    }
                }
            }
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            response_data = response.json()
            checkout_url = response_data['data']['attributes']['url']
            return redirect(checkout_url)
        except Exception as e:
            return JsonResponse({'error': f"Checkout failed: {str(e)}"})

@method_decorator(csrf_exempt, name='dispatch')
class LemonSqueezyWebhookView(View):
    def post(self, request, *args, **kwargs):
        payload = request.body
        secret = getattr(settings, 'LEMONSQUEEZY_WEBHOOK_SECRET', '')
        
        # Verify signature
        signature = request.META.get('HTTP_X_SIGNATURE')
        if not signature:
            return HttpResponse(status=401)
        
        expected_signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            return HttpResponse(status=401)

        event_data = json.loads(payload)
        event_name = event_data.get('meta', {}).get('event_name')

        if event_name in ['subscription_created', 'subscription_updated']:
            custom_data = event_data.get('meta', {}).get('custom_data', {})
            user_id = custom_data.get('user_id')
            tier = custom_data.get('tier')
            
            if user_id:
                profile = Profile.objects.get(user_id=user_id)
                profile.tier = tier
                profile.subscription_id = event_data['data']['id']
                profile.save()

        return HttpResponse(status=200)

class SupportChatAPIView(APIView):
    permission_classes = []

    def _get_accessible_conversation(self, request, conversation_id):
        try:
            conversation = SupportConversation.objects.get(pk=conversation_id)
        except (SupportConversation.DoesNotExist, ValueError):
            return None, Response({"error": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)

        user = request.user if request.user.is_authenticated else None
        if conversation.user_id not in {None, user.id if user else None}:
            return None, Response({"error": "Conversation access denied."}, status=status.HTTP_403_FORBIDDEN)
        if conversation.user_id is None and request.session.get("support_conversation_id") != str(conversation.pk):
            return None, Response({"error": "Conversation access denied."}, status=status.HTTP_403_FORBIDDEN)
        return conversation, None

    def get(self, request):
        conversation_id = request.query_params.get("conversation_id")
        if not conversation_id:
            return Response({"messages": []}, status=status.HTTP_200_OK)
        conversation, error = self._get_accessible_conversation(request, conversation_id)
        if error:
            return error
        return Response(
            {
                "conversation_id": str(conversation.pk),
                "status": conversation.status,
                "messages": [
                    {"role": item.role, "content": item.content, "source": item.source}
                    for item in conversation.messages.order_by("created_at")
                    if item.role in {"user", "assistant"}
                ],
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        message = str(request.data.get("message", "")).strip()
        if not message or len(message) > 4000:
            return Response(
                {"error": "message is required and must be 1–4000 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        conversation_id = request.data.get("conversation_id")
        conversation = None
        if conversation_id:
            conversation, error = self._get_accessible_conversation(request, conversation_id)
            if error:
                return error

        user = request.user if request.user.is_authenticated else None
        if conversation is None:
            conversation = SupportConversation.objects.create(
                user=user,
                title=message[:180],
            )

        request.session["support_conversation_id"] = str(conversation.pk)
        SupportMessage.objects.create(
            conversation=conversation,
            role="user",
            content=message,
            source="human",
        )
        result = generate_reply(conversation)
        SupportMessage.objects.create(
            conversation=conversation,
            role="assistant",
            content=result["content"],
            source=result["source"],
        )

        if result["should_escalate"] and conversation.status == "open":
            conversation.status = "escalated"
            conversation.save(update_fields=["status", "updated_at"])

        return Response(
            {
                "conversation_id": str(conversation.pk),
                "message": result["content"],
                "source": result["source"],
                "status": conversation.status,
                "can_escalate": conversation.status != "resolved",
            },
            status=status.HTTP_200_OK,
        )


class SupportTicketCreateAPIView(APIView):
    permission_classes = []

    def post(self, request):
        conversation_id = request.data.get("conversation_id")
        if not conversation_id:
            return Response({"error": "conversation_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            conversation = SupportConversation.objects.get(pk=conversation_id)
        except (SupportConversation.DoesNotExist, ValueError):
            return Response({"error": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)

        user = request.user if request.user.is_authenticated else None
        if conversation.user_id not in {None, user.id if user else None}:
            return Response({"error": "Conversation access denied."}, status=status.HTTP_403_FORBIDDEN)
        if conversation.user_id is None and request.session.get("support_conversation_id") != str(conversation.pk):
            return Response({"error": "Conversation access denied."}, status=status.HTTP_403_FORBIDDEN)

        name = str(request.data.get("name", "")).strip()
        email = str(request.data.get("email", "")).strip()
        subject = str(request.data.get("subject", "Support request")).strip() or "Support request"
        category = str(request.data.get("category", "general")).strip() or "general"
        extra_message = str(request.data.get("message", "")).strip()

        if user:
            name = name or user.get_full_name() or user.get_username()
            email = email or user.email

        if not name or not email or "@" not in email:
            return Response(
                {"error": "name and a valid email are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        transcript = "\n\n".join(
            f"{item.role.upper()}: {item.content}" for item in conversation.messages.order_by("created_at")[:20]
        )
        ticket_message = extra_message or "Escalated from the Linkify support assistant."
        ticket_message = f"{ticket_message}\n\nConversation transcript:\n{transcript}"[:5000]
        ticket = SupportTicket.objects.create(
            conversation=conversation,
            user=user,
            name=name[:120],
            email=email[:254],
            subject=subject[:180],
            message=ticket_message,
            category=category[:60],
            priority="urgent" if conversation.status == "escalated" else "normal",
        )
        conversation.status = "escalated"
        conversation.save(update_fields=["status", "updated_at"])

        return Response(
            {
                "ticket_id": ticket.id,
                "status": ticket.status,
                "message": "Your request has been escalated to the support team.",
            },
            status=status.HTTP_201_CREATED,
        )


# ─────────────────────────────────────────
# Page Views
# ─────────────────────────────────────────

User = get_user_model()

class LandingPageView(View):
    template_name = "landing.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return render(request, self.template_name)
        return render(request, self.template_name, {'form': QuickSignUpForm()})

    def post(self, request, *args, **kwargs):
        form = QuickSignUpForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            name = form.cleaned_data['name']
            try:
                user = User.objects.create_user(
                    username=email, email=email, 
                    password=secrets.token_urlsafe(16), 
                    first_name=name.split(' ')[0]
                )
                api_key_obj = APIKey.objects.create(user=user, name=f"{name}'s Default Key")
                return render(request, self.template_name, {'success': True, 'new_api_key': api_key_obj.key})
            except IntegrityError:
                form.add_error('email', "User already exists.")
        return render(request, self.template_name, {'form': form})

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, _ = Profile.objects.get_or_create(user=self.request.user)
        api_keys = APIKey.objects.filter(user=self.request.user)
        context['api_keys'] = api_keys
        
        limit_map = {'free': 1, 'pro': 5, 'business': 100}
        max_keys = limit_map.get(profile.tier, 1)
        context['can_create_key'] = api_keys.count() < max_keys

        api_key = api_keys.first()
        if api_key:
            limit = {'free': 100, 'pro': 5000, 'business': None}.get(profile.tier)
            today_count = UsageLog.objects.filter(api_key=api_key, date=date.today()).count()
            context['usage'] = {
                'tier': profile.tier,
                'today_usage': today_count,
                'daily_limit': limit if limit else 'unlimited',
                'usage_percent': (today_count / limit * 100) if limit else 0
            }
            # Chart data omitted for brevity but logic remains same
        return context

class DocsPageView(TemplateView):
    template_name = "docs.html"

class PrivacyPolicyView(TemplateView):
    template_name = "legal/privacy.html"

class AboutPageView(TemplateView):
    template_name = "about.html"

class TermsOfServiceView(TemplateView):
    template_name = "legal/terms.html"
    
class FAQView(TemplateView):
    template_name = "legal/faq.html"

@method_decorator(ensure_csrf_cookie, name="dispatch")
class SupportView(TemplateView):
    template_name = "support.html"

    def post(self, request, *args, **kwargs):
        # Here you would typically send an email via Resend to your support address
        messages.success(request, "Your message has been sent! We'll get back to you soon.")
        return redirect('support')

class UsageLogsListView(LoginRequiredMixin, TemplateView):
    template_name = "usage_logs.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get all logs for the current user's API keys, ordered by newest first
        logs = UsageLog.objects.filter(api_key__user=self.request.user).order_by('-id')[:100]
        context['logs'] = logs
        return context

# ─────────────────────────────────────────
# Profile & Settings Views
# ─────────────────────────────────────────

from allauth.account.views import PasswordChangeView as AllauthPasswordChangeView
from django.urls import reverse_lazy
from django.contrib import messages

class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, _ = Profile.objects.get_or_create(user=self.request.user)
        context['profile'] = profile
        return context

    def post(self, request, *args, **kwargs):
        user = request.user
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        
        user.first_name = first_name
        user.last_name = last_name
        user.save()
        
        messages.success(request, "Profile updated successfully!")
        return redirect('profile')

class CustomPasswordChangeView(AllauthPasswordChangeView):
    template_name = "account/password_change.html"
    success_url = reverse_lazy('profile')

    def form_valid(self, form):
        messages.success(self.request, "Password changed successfully!")
        return super().form_valid(form)
