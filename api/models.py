import hashlib
import secrets
import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

User = get_user_model()

class Profile(models.Model):
    TIER_CHOICES = [
        ('free', 'Free'),
        ('pro', 'Pro'),
        ('business', 'Business'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    tier = models.CharField(
        max_length=20,
        choices=TIER_CHOICES,
        default='free'
    )
    lemonsqueezy_customer_id = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )
    subscription_id = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    company_name = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )
    job_title = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )

    def __str__(self):
        return f"{self.user.username} — {self.tier} Profile"

class APIKey(models.Model):
    SECRET_PREFIX = "lm_live_"
    DEFAULT_SCOPES = ["search", "usage"]
    ALLOWED_SCOPES = {"search", "batch", "usage"}

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_keys')
    key_hash = models.CharField(max_length=64, unique=True, editable=False)
    prefix = models.CharField(max_length=20, editable=False, db_index=True)
    name = models.CharField(max_length=100)
    scopes = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    revoked_at = models.DateTimeField(blank=True, null=True)

    @classmethod
    def digest_secret(cls, raw_key):
        return hashlib.sha256(str(raw_key).encode("utf-8")).hexdigest()

    @classmethod
    def issue(cls, *, user, name, scopes=None, expires_at=None):
        raw_key = f"{cls.SECRET_PREFIX}{secrets.token_urlsafe(32)}"
        requested_scopes = list(dict.fromkeys(scopes or cls.DEFAULT_SCOPES))
        if not requested_scopes or set(requested_scopes) - cls.ALLOWED_SCOPES:
            raise ValueError("Invalid API key scopes.")
        key = cls.objects.create(
            user=user,
            name=name,
            key_hash=cls.digest_secret(raw_key),
            prefix=raw_key[:16],
            scopes=requested_scopes,
            expires_at=expires_at,
        )
        return key, raw_key

    @property
    def masked_key(self):
        return f"{self.prefix}••••••••••••••••"

    @property
    def is_usable(self):
        return (
            self.is_active
            and self.revoked_at is None
            and (self.expires_at is None or self.expires_at > timezone.now())
        )

    def has_scope(self, scope):
        return scope in (self.scopes or [])

    def revoke(self):
        self.is_active = False
        self.revoked_at = timezone.now()
        self.save(update_fields=["is_active", "revoked_at"])

    @property
    def tier(self):
        try:
            return self.user.profile.tier
        except Profile.DoesNotExist:
            return 'free'

    def __str__(self):
        return f"{self.user.username} — {self.name} ({self.tier})"
    
class UsageLog(models.Model):
    api_key = models.ForeignKey(APIKey, on_delete=models.CASCADE, related_name='usagelogs')
    endpoint = models.CharField(max_length=200)
    method = models.CharField(max_length=10, default="GET")
    status_code = models.PositiveSmallIntegerField(blank=True, null=True)
    latency_ms = models.PositiveIntegerField(blank=True, null=True)
    date = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"{self.api_key.name} — {self.endpoint} — {self.date}"


class BillingWebhookEvent(models.Model):
    event_id = models.CharField(max_length=255, unique=True)
    event_name = models.CharField(max_length=100)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-processed_at"]

    def __str__(self):
        return f"{self.event_name} — {self.event_id}"

# Signals for Profile creation
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if not hasattr(instance, 'profile'):
        Profile.objects.get_or_create(user=instance)
    instance.profile.save()

class SupportConversation(models.Model):
    STATUS_CHOICES = [
        ("open", "Open"),
        ("escalated", "Escalated"),
        ("resolved", "Resolved"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_conversations",
    )
    session_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    title = models.CharField(max_length=180, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title or f"Support conversation {self.pk}"


class SupportMessage(models.Model):
    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
        ("system", "System"),
    ]

    conversation = models.ForeignKey(
        SupportConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField(max_length=12000)
    source = models.CharField(max_length=20, default="human")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role} message in {self.conversation_id}"


class SupportTicket(models.Model):
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
    ]
    PRIORITY_CHOICES = [
        ("normal", "Normal"),
        ("urgent", "Urgent"),
    ]

    conversation = models.ForeignKey(
        SupportConversation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_tickets",
    )
    name = models.CharField(max_length=120)
    email = models.EmailField()
    subject = models.CharField(max_length=180)
    message = models.TextField(max_length=5000)
    category = models.CharField(max_length=60, default="general")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="normal")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} — {self.email}"
