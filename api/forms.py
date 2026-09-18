from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()

class QuickSignUpForm(forms.Form):
    name = forms.CharField(max_length=100, required=True)
    email = forms.EmailField(required=True)

    def clean_email(self):
        email = self.cleaned_data.get('email').lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "An account with this email already exists. Please log in to get your key."
            )
        return email


class SupportRequestForm(forms.Form):
    name = forms.CharField(max_length=120)
    email = forms.EmailField(max_length=254)
    subject = forms.CharField(max_length=180)
    category = forms.ChoiceField(
        choices=[
            ("general", "General"),
            ("api", "API"),
            ("account", "Account"),
            ("billing", "Billing"),
            ("security", "Security"),
        ]
    )
    message = forms.CharField(max_length=5000, widget=forms.Textarea)

    def clean(self):
        cleaned = super().clean()
        combined = " ".join(str(value) for value in cleaned.values()).lower()
        secret_markers = ("lm_live_", "sk-", "whsec_", "bearer ")
        if any(marker in combined for marker in secret_markers):
            raise forms.ValidationError("Remove API keys, tokens, and webhook secrets before sending.")
        return cleaned
