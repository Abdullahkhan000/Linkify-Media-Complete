from allauth.headless.account.inputs import SignupInput
from allauth.headless.account.views import SignupView
from allauth.headless.internal.restkit import inputs


class SecureSignupInput(SignupInput):
    """Headless signup contract with explicit consent and password confirmation."""

    password_confirm = inputs.CharField()
    terms = inputs.BooleanField(
        required=True,
        error_messages={"required": "Accept the Terms and Privacy Policy to continue."},
    )

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        confirmation = cleaned.get("password_confirm")
        if password and confirmation and password != confirmation:
            self.add_error("password_confirm", "The passwords do not match.")
        return cleaned


class SecureHeadlessSignupView(SignupView):
    input_class = {"POST": SecureSignupInput}
