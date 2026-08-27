import uuid
import uuid

from django.db import models
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

User = get_user_model()

class Profile(models.Model):
    TIER_CHOICES = [
        ('free', 'Free'),
        ('pro', 'Pro'),
        ('business', 'Business'),
    ]
    user                    = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    tier                    = models.CharField(max_length=20, choices=TIER_CHOICES, default='free')
    lemonsqueezy_customer_id = models.CharField(max_length=255, blank=True, null=True)
    subscription_id         = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} — {self.tier} Profile"

class APIKey(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_keys')
    key        = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name       = models.CharField(max_length=100)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def tier(self):
        try:
            return self.user.profile.tier
        except Profile.DoesNotExist:
            return 'free'

    def __str__(self):
        return f"{self.user.username} — {self.name} ({self.tier})"
    
class UsageLog(models.Model):
    api_key  = models.ForeignKey(APIKey, on_delete=models.CASCADE, related_name='usagelogs')
    endpoint = models.CharField(max_length=200)
    date     = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.api_key.name} — {self.endpoint} — {self.date}"

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
