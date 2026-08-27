import resend
from django.conf import settings
from allauth.account.adapter import DefaultAccountAdapter
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives

class CustomAccountAdapter(DefaultAccountAdapter):
    def send_mail(self, template_prefix, email, context):
        # Configure Resend
        resend.api_key = getattr(settings, "RESEND_API_KEY", "")
        
        # Load Subject
        subject = render_to_string(f"{template_prefix}_subject.txt", context).strip()
        
        # Load Plain Text Body
        body_text = render_to_string(f"{template_prefix}_message.txt", context)
        
        # Load HTML Body (The "Achi" Template)
        body_html = render_to_string(f"{template_prefix}_message.html", context)

        # From Email
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "onboarding@resend.dev")

        # Send using Resend SDK
        params = {
            "from": from_email,
            "to": [email],
            "subject": subject,
            "html": body_html,
            "text": body_text,
        }
        
        try:
            resend.Emails.send(params)
        except Exception as e:
            # Fallback to console if Resend fails or key is missing during dev
            print(f"Resend Error: {e}")
            if settings.DEBUG:
                print(f"--- FAILED EMAIL START ---")
                print(f"To: {email}")
                print(f"Subject: {subject}")
                print(f"Body: {body_text}")
                print(f"--- FAILED EMAIL END ---")
