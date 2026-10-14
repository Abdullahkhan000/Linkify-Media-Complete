from django.db.utils import OperationalError, ProgrammingError

from allauth.socialaccount.adapter import get_adapter


def social_auth_providers(request):
    try:
        apps = get_adapter(request).list_apps(request)
        configured = {
            provider: any(app.provider == provider and app.client_id and app.secret for app in apps)
            for provider in ("google", "github")
        }
    except (OperationalError, ProgrammingError):
        configured = {"google": False, "github": False}

    return {"social_auth_providers": configured}
