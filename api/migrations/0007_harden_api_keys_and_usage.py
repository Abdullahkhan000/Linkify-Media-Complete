import hashlib

import django.utils.timezone
from django.db import migrations, models


def hash_existing_keys(apps, schema_editor):
    APIKey = apps.get_model("api", "APIKey")
    Profile = apps.get_model("api", "Profile")
    for api_key in APIKey.objects.all().iterator():
        raw_key = str(api_key.key)
        tier = Profile.objects.filter(user_id=api_key.user_id).values_list("tier", flat=True).first()
        api_key.key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        api_key.prefix = raw_key[:16]
        api_key.scopes = ["search", "usage"] + (["batch"] if tier in {"pro", "business"} else [])
        api_key.save(update_fields=["key_hash", "prefix", "scopes"])


class Migration(migrations.Migration):
    dependencies = [("api", "0006_supportconversation_supportticket_conversation_and_more")]

    operations = [
        migrations.AddField(
            model_name="apikey",
            name="key_hash",
            field=models.CharField(editable=False, max_length=64, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="apikey",
            name="prefix",
            field=models.CharField(db_index=True, default="", editable=False, max_length=20),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="apikey",
            name="scopes",
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name="apikey",
            name="last_used_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="apikey",
            name="expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="apikey",
            name="revoked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="usagelog",
            name="method",
            field=models.CharField(default="GET", max_length=10),
        ),
        migrations.AddField(
            model_name="usagelog",
            name="status_code",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="usagelog",
            name="latency_ms",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="usagelog",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                db_index=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
        migrations.CreateModel(
            name="BillingWebhookEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("event_id", models.CharField(max_length=255, unique=True)),
                ("event_name", models.CharField(max_length=100)),
                ("processed_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-processed_at"]},
        ),
        migrations.RunPython(hash_existing_keys, migrations.RunPython.noop),
        migrations.RemoveField(model_name="apikey", name="key"),
        migrations.AlterField(
            model_name="apikey",
            name="key_hash",
            field=models.CharField(editable=False, max_length=64, unique=True),
        ),
    ]
