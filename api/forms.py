from django import forms
from django.contrib.auth import get_user_model
from allauth.account.forms import SignupForm

User = get_user_model()


class LinkifySignupForm(SignupForm):
    terms = forms.BooleanField(
        required=True,
        error_messages={"required": "Accept the Terms and Privacy Policy to continue."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = "Use at least 3 letters, numbers, dots, dashes, or underscores."
        self.order_fields(["username", "email", "password1", "password2", "terms"])

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


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "first_name", "last_name"]
        widgets = {
            "username": forms.TextInput(attrs={"autocomplete": "username", "maxlength": 150}),
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name", "maxlength": 150}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name", "maxlength": 150}),
        }

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if len(username) < 3:
            raise forms.ValidationError("Username must contain at least 3 characters.")
        if User.objects.exclude(pk=self.instance.pk).filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is already taken.")
        return username

    def clean_first_name(self):
        return self.cleaned_data.get("first_name", "").strip()

    def clean_last_name(self):
        return self.cleaned_data.get("last_name", "").strip()


class AccountDeleteForm(forms.Form):
    confirmation = forms.CharField(max_length=150)
    password = forms.CharField(required=False, strip=False, widget=forms.PasswordInput)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["password"].required = user.has_usable_password()

    def clean_confirmation(self):
        confirmation = self.cleaned_data["confirmation"].strip()
        if confirmation.casefold() != self.user.username.casefold():
            raise forms.ValidationError("Type your exact username to confirm deletion.")
        return confirmation

    def clean_password(self):
        password = self.cleaned_data.get("password", "")
        if self.user.has_usable_password() and not self.user.check_password(password):
            raise forms.ValidationError("Your password is incorrect.")
        return password


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
