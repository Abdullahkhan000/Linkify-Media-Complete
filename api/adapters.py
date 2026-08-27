import resend

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from allauth.account.adapter import DefaultAccountAdapter


class CustomAccountAdapter(DefaultAccountAdapter):
    def send_mail(self, template_prefix, email, context):
        subject = render_to_string(f"{template_prefix}_subject.txt", context).strip()
        body_text = render_to_string(f"{template_prefix}_message.txt", context)
        body_html = render_to_string(f"{template_prefix}_message.html", context)
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "onboarding@resend.dev")
        api_key = getattr(settings, "RESEND_API_KEY", "")

        if not api_key:
            EmailMultiAlternatives(
                subject=subject,
                body=body_text,
                from_email=from_email,
                to=[email],
            ).send(fail_silently=False)
            return

        resend.api_key = api_key
        params = {
            "from": from_email,
            "to": [email],
            "subject": subject,
            "html": body_html,
            "text": body_text,
        }

        try:
            resend.Emails.send(params)
        except Exception as exc:
            if not settings.DEBUG:
                raise
            print(f"Resend Error: {exc}")
            EmailMultiAlternatives(
                subject=subject,
                body=body_text,
                from_email=from_email,
                to=[email],
            ).send(fail_silently=False)
