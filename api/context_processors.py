from django.db.utils import OperationalError, ProgrammingError

from allauth.socialaccount.models import SocialApp


def social_auth_providers(request):
    try:
        apps = SocialApp.objects.on_site(request)
        configured = {
            provider: apps.filter(provider=provider).exists()
            for provider in ("google", "github")
        }
    except (OperationalError, ProgrammingError):
        configured = {"google": False, "github": False}

    return {"social_auth_providers": configured}
