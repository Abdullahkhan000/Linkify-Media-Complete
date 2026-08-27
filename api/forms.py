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