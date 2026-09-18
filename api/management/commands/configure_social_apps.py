import os

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from allauth.socialaccount.models import SocialApp


class Command(BaseCommand):
    help = "Configure Google and GitHub django-allauth SocialApp records from environment variables."

    def handle(self, *args, **options):
        domain = os.getenv("SITE_DOMAIN", "localhost:8000").strip()
        site_name = os.getenv("SITE_NAME", "Linkify Media").strip()
        site, _ = Site.objects.update_or_create(
            id=getattr(settings, "SITE_ID", 1),
            defaults={"domain": domain, "name": site_name},
        )

        configured = 0
        credentials = {
            "google": (
                os.getenv("GOOGLE_CLIENT_ID", "").strip(),
                os.getenv("GOOGLE_CLIENT_SECRET", "").strip(),
            ),
            "github": (
                os.getenv("GITHUB_CLIENT_ID", "").strip(),
                os.getenv("GITHUB_CLIENT_SECRET", "").strip(),
            ),
        }
        for provider in ("google", "github"):
            client_id, secret = credentials[provider]

            if not client_id or not secret:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping {provider}: client ID or secret is not configured."
                    )
                )
                continue

            app = (
                SocialApp.objects.filter(provider=provider)
                .order_by("id")
                .first()
            )
            if app is None:
                app = SocialApp(provider=provider, name=provider.title())

            app.name = provider.title()
            app.client_id = client_id
            app.secret = secret
            app.key = ""
            app.save()
            app.sites.set([site])
            configured += 1
            self.stdout.write(self.style.SUCCESS(f"Configured {provider} SocialApp."))

        self.stdout.write(
            self.style.SUCCESS(
                f"Social auth configuration complete: {configured} provider(s), site={domain}."
            )
        )
