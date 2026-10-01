from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import html
import json
import re

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
OUT = ROOT / "frontend" / "data"
OUT.mkdir(parents=True, exist_ok=True)

URLS = {
    "landing-page": "/", "docs-page": "/docs", "billing": "/billing",
    "about-page": "/about", "dashboard": "/dashboard", "profile": "/account",
    "account_login": "/login", "account_signup": "/signup",
    "terms-of-service": "/terms", "privacy-policy": "/privacy",
    "support": "/support", "swagger-ui": "/api-reference",
    "usage-logs": "/usage-logs", "usage-logs-export": "/api/backend/usage-logs/export/",
    "platform-dashboard": "/platform", "playground": "/playground",
    "status-page": "/status", "analytics": "/analytics", "webhooks-page": "/webhooks",
    "teams": "/teams", "audit-page": "/audit", "account_change_password": "/change-password",
    "account_set_password": "/set-password", "socialaccount_connections": "/social/connections",
    "mfa_activate_totp": "/mfa/setup", "mfa_deactivate_totp": "/mfa/manage",
    "mfa_view_recovery_codes": "/mfa/recovery-codes", "account_reset_password": "/forgot-password",
}

# Every HTML file under templates/ is assigned to a Next route or a shared Next component.
ASSIGNMENTS = {
    "404.html": ("/not-found", "app/not-found.tsx"),
    "base.html": ("shared", "components/marketing-nav.tsx + site-footer.tsx + support entry point"),
    "about.html": ("/about", "app/[...legacy]/page.tsx"),
    "analytics.html": ("/analytics", "app/[...legacy]/page.tsx"),
    "api_reference.html": ("/api-reference", "app/[...legacy]/page.tsx"),
    "audit.html": ("/audit", "app/[...legacy]/page.tsx"),
    "billing.html": ("/billing", "app/[...legacy]/page.tsx"),
    "dashboard.html": ("/dashboard", "app/dashboard/page.tsx"),
    "docs.html": ("/docs", "app/docs/page.tsx"),
    "faq.html": ("/faq", "app/[...legacy]/page.tsx"),
    "landing.html": ("/", "app/page.tsx"),
    "platform_dashboard.html": ("/platform", "app/[...legacy]/page.tsx"),
    "playground.html": ("/playground", "app/[...legacy]/page.tsx"),
    "pricing.html": ("/pricing", "app/pricing/page.tsx"),
    "profile.html": ("/account", "app/account/page.tsx"),
    "profile copy.html": ("/account", "app/account/page.tsx"),
    "status.html": ("/status", "app/[...legacy]/page.tsx"),
    "support.html": ("/support", "app/[...legacy]/page.tsx"),
    "teams.html": ("/teams", "app/[...legacy]/page.tsx"),
    "usage_logs.html": ("/usage-logs", "app/[...legacy]/page.tsx"),
    "webhooks.html": ("/webhooks", "app/[...legacy]/page.tsx"),
    "legal/privacy.html": ("/privacy", "app/privacy/page.tsx"),
    "legal/terms.html": ("/terms", "app/terms/page.tsx"),
    "account/account_already_exists_message.html": ("/account-exists", "app/[...legacy]/page.tsx"),
    "account/account_inactive.html": ("/account-inactive", "app/[...legacy]/page.tsx"),
    "account/auth_base.html": ("shared", "components/auth-shell.tsx"),
    "account/email/account_already_exists_message.html": ("/account-exists", "app/[...legacy]/page.tsx"),
    "account/email/email_confirmation_message.html": ("/email-confirmation", "app/[...legacy]/page.tsx"),
    "account/email/email_confirmation_signup_message.html": ("/verification-sent", "app/[...legacy]/page.tsx"),
    "account/email/password_reset_key_message.html": ("/reset-password/:key", "app/reset-password/[key]/page.tsx"),
    "account/email_change.html": ("/change-email", "app/[...legacy]/page.tsx"),
    "account/email_confirm.html": ("/verify-email/:key", "app/verify-email/[key]/page.tsx"),
    "account/login.html": ("/login", "app/login/page.tsx"),
    "account/logout.html": ("/logout", "app/[...legacy]/page.tsx"),
    "account/password_change.html": ("/change-password", "app/[...legacy]/page.tsx"),
    "account/password_reset.html": ("/forgot-password", "app/forgot-password/page.tsx"),
    "account/password_reset_done.html": ("/password-reset-done", "app/[...legacy]/page.tsx"),
    "account/password_reset_from_key.html": ("/reset-password/:key", "app/reset-password/[key]/page.tsx"),
    "account/password_reset_from_key_done.html": ("/password-reset-done", "app/[...legacy]/page.tsx"),
    "account/password_set.html": ("/set-password", "app/[...legacy]/page.tsx"),
    "account/reauthenticate.html": ("/reauthenticate", "app/[...legacy]/page.tsx"),
    "account/signup.html": ("/signup", "app/signup/page.tsx"),
    "account/social_buttons.html": ("shared", "components/social-buttons.tsx"),
    "account/verification_sent.html": ("/verification-sent", "app/[...legacy]/page.tsx"),
    "account/verified_email_required.html": ("/verified-email-required", "app/[...legacy]/page.tsx"),
    "mfa/base_entrance.html": ("/mfa", "components/auth-shell.tsx"),
    "mfa/base_manage.html": ("/mfa", "components/dashboard-shell.tsx"),
    "mfa/index.html": ("/mfa", "app/[...legacy]/page.tsx"),
    "socialaccount/authentication_error.html": ("/social/error", "app/[...legacy]/page.tsx"),
    "socialaccount/base_entrance.html": ("shared", "components/auth-shell.tsx"),
    "socialaccount/base_manage.html": ("shared", "components/dashboard-shell.tsx"),
    "socialaccount/connections.html": ("/social/connections", "app/[...legacy]/page.tsx"),
    "socialaccount/login.html": ("/social/approval", "app/[...legacy]/page.tsx"),
    "socialaccount/login_cancelled.html": ("/social/cancelled", "app/[...legacy]/page.tsx"),
    "socialaccount/login_redirect.html": ("/social/redirect", "app/[...legacy]/page.tsx"),
    "socialaccount/signup.html": ("/social/signup", "app/[...legacy]/page.tsx"),
    "socialaccount/snippets/login_extra.html": ("shared", "components/social-buttons.tsx"),
    "socialaccount/snippets/provider_list.html": ("shared", "components/social-buttons.tsx"),
}

TXT_ASSIGNMENTS = {
    "account/email/email_confirmation_message.txt": ("/email-confirmation", "Next.js email-confirmation route reference"),
    "account/email/email_confirmation_subject.txt": ("/email-confirmation", "Next.js email-confirmation route reference"),
    "account/email/email_confirmation_signup_message.txt": ("/verification-sent", "Next.js verification-sent route reference"),
    "account/email/email_confirmation_signup_subject.txt": ("/verification-sent", "Next.js verification-sent route reference"),
    "account/email/password_reset_key_message.txt": ("/reset-password/:key", "Next.js reset-password route reference"),
    "account/email/password_reset_key_subject.txt": ("/reset-password/:key", "Next.js reset-password route reference"),
}

PAGES = {
    "about": {"path":"/about", "title":"About Linkify Media", "description":"Meet the developer-focused media intelligence platform and the product principles behind Linkify Media.", "eyebrow":"Company", "audience":"public", "templates":["about.html"], "links":[["/docs","Developer docs"],["/support","Contact support"]]},
    "privacy": {"path":"/privacy", "title":"Privacy policy", "description":"Read the Linkify Media privacy policy, including account information, API activity, support information, retention and privacy requests.", "eyebrow":"Privacy", "audience":"public", "templates":["legal/privacy.html"], "links":[["/support","Contact support"]]},
    "terms": {"path":"/terms", "title":"Terms of service", "description":"Review the terms for Linkify Media accounts, API keys, acceptable use, plans, third-party content, availability and termination.", "eyebrow":"Legal", "audience":"public", "templates":["legal/terms.html"], "links":[["/privacy","Privacy policy"],["/support","Contact support"]]},
    "faq": {"path":"/faq", "title":"Frequently asked questions", "description":"Answers about Linkify Media, API access, authentication, usage, billing, security and integrations.", "eyebrow":"Knowledge base", "audience":"public", "templates":["faq.html"], "links":[["/support","Contact support"],["/docs","Read the docs"]]},
    "api-reference": {"path":"/api-reference", "title":"API reference", "description":"Versioned media search, batch, usage, detail, trending and people-search endpoints with request guidance.", "eyebrow":"Developer reference", "audience":"public", "templates":["api_reference.html"], "links":[["/docs","Quickstart"],["/playground","Open playground"]]},
    "status": {"path":"/status", "title":"Linkify Media status", "description":"Check live health and readiness responses for the Linkify Media backend.", "eyebrow":"Live operations", "audience":"public", "templates":["status.html"], "links":[]},
    "playground": {"path":"/playground", "title":"API Playground", "description":"Build a request and inspect the real API response. Requests use the configured backend and report its actual status.", "eyebrow":"Developer tools", "audience":"public", "templates":["playground.html"], "links":[["/docs","Read the docs"]]},
    "support": {"path":"/support", "title":"Help & Support", "description":"Search support guidance, ask the Linkify support assistant or create a ticket when the backend is configured.", "eyebrow":"Developer support", "audience":"public", "templates":["support.html"], "links":[["/faq","Frequently asked questions"],["/docs","Documentation"],["/status","Service status"]]},
    "analytics": {"path":"/analytics", "title":"Request analytics", "description":"Review API request activity and usage metrics for the signed-in workspace.", "eyebrow":"Observability", "audience":"private", "templates":["analytics.html"], "links":[["/usage-logs","Usage logs"],["/platform","Platform overview"]]},
    "audit": {"path":"/audit", "title":"Audit activity", "description":"Review security and workspace events when an audit feed is available from the backend.", "eyebrow":"Security trail", "audience":"private", "templates":["audit.html"], "links":[["/platform","Back to platform"],["/account","Account settings"]]},
    "platform": {"path":"/platform", "title":"Developer platform", "description":"Manage API keys, usage, testing and the Linkify Media workspace from one place.", "eyebrow":"Workspace", "audience":"private", "templates":["platform_dashboard.html"], "links":[["/dashboard","API keys"],["/analytics","Analytics"],["/api-reference","API reference"],["/webhooks","Webhooks"],["/teams","Teams"],["/status","Service status"]]},
    "billing": {"path":"/billing", "title":"Billing & plans", "description":"Review plan information and billing availability for this signed-in account.", "eyebrow":"Plan management", "audience":"private", "templates":["billing.html"], "links":[["/pricing","Compare plans"],["/support","Billing support"]]},
    "teams": {"path":"/teams", "title":"Team workspace", "description":"Team collaboration screens are available here; team API persistence is not mounted in the reviewed Django URL configuration.", "eyebrow":"Collaboration", "audience":"private", "templates":["teams.html"], "links":[["/platform","Back to platform"],["/pricing","Compare plans"]]},
    "usage-logs": {"path":"/usage-logs", "title":"Usage logs", "description":"Review request status, latency, endpoint and API-key activity; CSV export remains available through the Django backend.", "eyebrow":"Request history", "audience":"private", "templates":["usage_logs.html"], "links":[["/dashboard","Dashboard"],["/platform","Platform overview"]]},
    "webhooks": {"path":"/webhooks", "title":"Webhooks", "description":"Webhook screens are available here; the reviewed Django migration head has no matching webhook endpoint/model API to persist changes.", "eyebrow":"Event delivery", "audience":"private", "templates":["webhooks.html"], "links":[["/platform","Back to platform"],["/docs","Developer docs"]]},
    "account-exists": {"path":"/account-exists", "title":"Account already exists", "description":"The email address is already linked to an account. Sign in or recover access instead of creating a duplicate.", "eyebrow":"Account help", "audience":"auth", "templates":["account/account_already_exists_message.html","account/email/account_already_exists_message.html"], "links":[["/login","Sign in"],["/forgot-password","Reset password"]]},
    "account-inactive": {"path":"/account-inactive", "title":"Account inactive", "description":"This account is not active yet. Follow the verification instructions or contact support for help.", "eyebrow":"Account status", "audience":"auth", "templates":["account/account_inactive.html"], "links":[["/verification-sent","Verification help"],["/support","Contact support"]]},
    "change-email": {"path":"/change-email", "title":"Change email address", "description":"Manage the email address attached to your Linkify Media account and follow its verification state.", "eyebrow":"Account security", "audience":"private", "templates":["account/email_change.html"], "links":[["/account","Back to profile"],["/verified-email-required","Verification help"]]},
    "change-password": {"path":"/change-password", "title":"Change password", "description":"Change the password for your signed-in Linkify Media account using the secure allauth account endpoint.", "eyebrow":"Account security", "audience":"private", "templates":["account/password_change.html"], "links":[["/account","Back to profile"],["/forgot-password","Forgot password?"]]},
    "set-password": {"path":"/set-password", "title":"Set a password", "description":"Add a password to an account that currently signs in using a connected provider.", "eyebrow":"Account security", "audience":"private", "templates":["account/password_set.html"], "links":[["/account","Back to profile"]]},
    "email-confirmation": {"path":"/email-confirmation", "title":"Email confirmation", "description":"Email confirmation details for Linkify Media accounts. Use the secure verification link from the email to complete the action.", "eyebrow":"Account verification", "audience":"auth", "templates":["account/email/email_confirmation_message.html"], "links":[["/login","Sign in"],["/support","Contact support"]]},
    "verification-sent": {"path":"/verification-sent", "title":"Verification email sent", "description":"Check the account inbox for the verification link and continue once the email address is confirmed.", "eyebrow":"Account verification", "audience":"auth", "templates":["account/verification_sent.html","account/email/email_confirmation_signup_message.html"], "links":[["/login","Sign in"],["/support","Contact support"]]},
    "verified-email-required": {"path":"/verified-email-required", "title":"Verify your email", "description":"Email verification is required for the account action. Resend a verification message using the backend if available.", "eyebrow":"Account verification", "audience":"auth", "templates":["account/verified_email_required.html"], "links":[["/account","Account settings"],["/support","Contact support"]]},
    "logout": {"path":"/logout", "title":"Sign out", "description":"Confirm before ending the current Linkify Media session.", "eyebrow":"Account", "audience":"private", "templates":["account/logout.html"], "links":[["/dashboard","Cancel and return"]]},
    "password-reset-done": {"path":"/password-reset-done", "title":"Password updated", "description":"The password reset flow is complete. Sign in again with the updated credential.", "eyebrow":"Account recovery", "audience":"auth", "templates":["account/password_reset_done.html","account/password_reset_from_key_done.html"], "links":[["/login","Sign in"]]},
    "reauthenticate": {"path":"/reauthenticate", "title":"Confirm your identity", "description":"Confirm your current account credentials before continuing a sensitive account action.", "eyebrow":"Account security", "audience":"private", "templates":["account/reauthenticate.html"], "links":[["/account","Account settings"]]},
    "social/connections": {"path":"/social/connections", "title":"Connected accounts", "description":"Review connected Google and GitHub sign-in providers for the current account.", "eyebrow":"Account security", "audience":"private", "templates":["socialaccount/connections.html"], "links":[["/account","Back to profile"]]},
    "social/approval": {"path":"/social/approval", "title":"Connect a social account", "description":"Continue securely with a configured social identity provider. Provider passwords are never shared with Linkify Media.", "eyebrow":"Secure OAuth", "audience":"auth", "templates":["socialaccount/login.html"], "links":[["/login","Cancel and return to sign in"]]},
    "social/cancelled": {"path":"/social/cancelled", "title":"Sign-in cancelled", "description":"No account changes were made. You can try a provider again or continue with email and password.", "eyebrow":"Social sign-in", "audience":"auth", "templates":["socialaccount/login_cancelled.html"], "links":[["/login","Return to sign in"]]},
    "social/error": {"path":"/social/error", "title":"Social sign-in error", "description":"Social sign-in could not be completed. Try again or contact support.", "eyebrow":"Social sign-in", "audience":"auth", "templates":["socialaccount/authentication_error.html"], "links":[["/login","Try again"],["/support","Contact support"]]},
    "social/redirect": {"path":"/social/redirect", "title":"Connecting securely", "description":"Continue through the configured identity provider to finish authentication.", "eyebrow":"Secure OAuth", "audience":"auth", "templates":["socialaccount/login_redirect.html"], "links":[["/login","Return to sign in"]]},
    "social/signup": {"path":"/social/signup", "title":"Complete social sign-up", "description":"Review account details and finish provider-based account creation.", "eyebrow":"Social sign-up", "audience":"auth", "templates":["socialaccount/signup.html"], "links":[["/login","Already have an account? Sign in"]]},
    "mfa": {"path":"/mfa", "title":"Two-factor authentication", "description":"Manage authenticator-app protection and recovery-code guidance for your account.", "eyebrow":"Account security", "audience":"private", "templates":["mfa/index.html","mfa/base_manage.html","mfa/base_entrance.html"], "links":[["/account","Back to profile"]]},
    "mfa/setup": {"path":"/mfa/setup", "title":"Set up an authenticator", "description":"Set up an authenticator app to protect your account with rotating one-time codes.", "eyebrow":"Account security", "audience":"private", "templates":["mfa/base_entrance.html","mfa/base_manage.html"], "links":[["/mfa","Two-factor settings"]]},
    "mfa/manage": {"path":"/mfa/manage", "title":"Manage two-factor authentication", "description":"Manage authenticator protection and recovery settings for your account.", "eyebrow":"Account security", "audience":"private", "templates":["mfa/base_manage.html","mfa/index.html"], "links":[["/mfa","Two-factor settings"]]},
    "mfa/recovery-codes": {"path":"/mfa/recovery-codes", "title":"Recovery codes", "description":"Review one-time recovery-code guidance and store codes in a secure password manager.", "eyebrow":"Account security", "audience":"private", "templates":["mfa/index.html"], "links":[["/mfa","Two-factor settings"]]},
}

class VisibleCopy(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items: list[str] = []
        self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "svg", "noscript"}: self.hidden += 1
    def handle_endtag(self, tag):
        if tag in {"script", "style", "svg", "noscript"} and self.hidden: self.hidden -= 1
    def handle_data(self, data):
        if not self.hidden:
            value = re.sub(r"\s+", " ", data).strip()
            value = re.sub(r"\{\{.*?\}\}", "", value).strip()
            if value and not value.startswith("{%") and not value.startswith("{#"):
                self.items.append(value)

class SafeHTML(HTMLParser):
    ALLOWED = {"h1","h2","h3","h4","p","ul","ol","li","blockquote","strong","b","em","i","code","pre","div","section","article","header","footer","span","a","br","hr","table","thead","tbody","tr","th","td","dl","dt","dd","small","details","summary"}
    VOID = {"br","hr"}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0
        self.form_depth = 0
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script","style","svg","noscript","img","input","select","textarea","option"}:
            if tag in {"script","style","svg","noscript"}: self.skip += 1
            return
        if self.skip: return
        if tag == "form":
            self.form_depth += 1
            return
        if tag not in self.ALLOWED: return
        if tag == "a":
            href = attrs.get("href", "")
            if href.startswith(("/", "#", "mailto:", "https://")):
                self.out.append(f'<a href="{html.escape(href, quote=True)}">')
            else:
                self.out.append("<span>")
            return
        self.out.append(f"<{tag}>")
    def handle_endtag(self, tag):
        if tag in {"script","style","svg","noscript"} and self.skip:
            self.skip -= 1
            return
        if self.skip: return
        if tag == "form":
            self.form_depth = max(0, self.form_depth - 1)
            return
        if tag in self.ALLOWED and tag not in self.VOID:
            self.out.append(f"</{tag}>")
    def handle_data(self, data):
        if not self.skip:
            text = re.sub(r"\{\{.*?\}\}", "", data)
            text = re.sub(r"\{%.*?%\}", "", text)
            if text.strip(): self.out.append(html.escape(text))
    def result(self): return "".join(self.out)


def trim_to_page(source: str, name: str) -> str:
    source = re.sub(r"\{% comment %\}.*?\{% endcomment %\}", "", source, flags=re.S)
    # Pick page-specific content instead of inheriting Django's obsolete shared layout.
    for block in ("content", "auth_content"):
        match = re.search(r"\{%\s*block\s+" + block + r"\s*%\}(.*?)\{%\s*endblock(?:\s+\w+)?\s*%\}", source, flags=re.S)
        if match:
            source = match.group(1)
            break
    else:
        if name in {"base.html", "account/auth_base.html", "mfa/base_entrance.html", "mfa/base_manage.html", "socialaccount/base_entrance.html", "socialaccount/base_manage.html", "account/social_buttons.html", "socialaccount/snippets/login_extra.html", "socialaccount/snippets/provider_list.html", "404.html"}:
            return ""
        body = re.search(r"<body[^>]*>(.*?)</body>", source, flags=re.S|re.I)
        if body: source = body.group(1)
    # Drop behavior that belongs to Django and remove Django tag syntax from static content.
    source = re.sub(r"<script\b[^>]*>.*?</script\s*>", "", source, flags=re.S|re.I)
    source = re.sub(r"<style\b[^>]*>.*?</style\s*>", "", source, flags=re.S|re.I)
    source = re.sub(r"\{%\s*(?:load|extends|include|csrf_token|url|static|now|with|endwith|block|endblock|if|elif|else|endif|for|endfor|empty|trans|comment|endcomment|provider_login_url|querystring|autoescape|endautoescape|firstof|cycle|spaceless|endspaceless|filter|endfilter|regroup|widthratio|debug|lorem|templatetag|verbatim|endverbatim|urlize|localtime|endlocaltime)[^%]*%\}", "", source, flags=re.S)
    source = re.sub(r"\{%.*?%\}", "", source, flags=re.S)
    source = re.sub(r"\{\{.*?\}\}", "", source, flags=re.S)
    source = re.sub(r'href="\{\{[^\"]*\}\}"', 'href="#"', source)
    source = re.sub(r"<form\b[^>]*>", "<div>", source, flags=re.I)
    source = re.sub(r"</form\s*>", "</div>", source, flags=re.I)
    parser = SafeHTML()
    parser.feed(source)
    return parser.result()


def normalize_href(template: str) -> str:
    for name, path in URLS.items():
        template = re.sub(r"\{%\s*url\s+'" + re.escape(name) + r"'[^%]*%\}", path, template)
    return re.sub(r'href="\{\{[^\"]*\}\}"', 'href="#"', template)

files = sorted(TEMPLATES.rglob("*.html"))
rel_files = [p.relative_to(TEMPLATES).as_posix() for p in files]
missing = sorted(set(rel_files) - set(ASSIGNMENTS))
extra = sorted(set(ASSIGNMENTS) - set(rel_files))
text_files = sorted(TEMPLATES.rglob("*.txt"))
text_rel_files = [p.relative_to(TEMPLATES).as_posix() for p in text_files]
text_missing = sorted(set(text_rel_files) - set(TXT_ASSIGNMENTS))
text_extra = sorted(set(TXT_ASSIGNMENTS) - set(text_rel_files))
if missing or extra or text_missing or text_extra:
    raise SystemExit(f"Template map mismatch. HTML missing={missing}; HTML nonexistent={extra}; text missing={text_missing}; text nonexistent={text_extra}")

catalog = {}
for p, rel in zip(files, rel_files):
    raw = p.read_text(encoding="utf-8", errors="replace")
    visible = VisibleCopy()
    visible_source = re.sub(r"\{% comment %\}.*?\{% endcomment %\}", "", raw, flags=re.S)
    visible_source = re.sub(r"\{%.*?%\}|\{\{.*?\}\}", " ", visible_source, flags=re.S)
    visible.feed(visible_source)
    route, component = ASSIGNMENTS[rel]
    page_html = trim_to_page(normalize_href(raw), rel)
    catalog[rel] = {
        "kind": "html",
        "route": route,
        "component": component,
        "copy": list(dict.fromkeys(visible.items)),
        "html": page_html,
    }

for p, rel in zip(text_files, text_rel_files):
    raw = p.read_text(encoding="utf-8", errors="replace")
    raw = re.sub(r"\{#.*?#\}", "", raw, flags=re.S)
    raw = re.sub(r"\{%.*?%\}", "", raw, flags=re.S)
    raw = re.sub(r"\{\{.*?\}\}", "", raw, flags=re.S)
    copy = [re.sub(r"\s+", " ", part).strip() for part in re.split(r"\n\s*\n", raw) if part.strip()]
    route, component = TXT_ASSIGNMENTS[rel]
    catalog[rel] = {"kind": "plain-text email", "route": route, "component": component, "copy": copy, "html": ""}

# Attach the original template copy to the route-level pages without duplicating the whole base layout.
for slug, page in PAGES.items():
    page["html"] = "\n".join(catalog[t]["html"] for t in page["templates"] if catalog[t]["html"])
    page["sourceCopy"] = list(dict.fromkeys(text for t in page["templates"] for text in catalog[t]["copy"]))

(OUT / "django-template-archive.json").write_text(
    json.dumps({"templates": [{"file": name, **catalog[name]} for name in rel_files + text_rel_files]}, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
(OUT / "django-template-migration.json").write_text(json.dumps({"pages":PAGES,"templates":catalog},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
(OUT / "django-template-route-map.json").write_text(json.dumps({"templates":{k:{"route":v[0],"component":v[1]} for k,v in {**ASSIGNMENTS, **TXT_ASSIGNMENTS}.items()}},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(f"Mapped {len(rel_files)} HTML + {len(text_rel_files)} text templates ({len(rel_files) + len(text_rel_files)} total) to {len(PAGES)} Next route groups.")
print(f"Unmapped templates: {len(missing) + len(text_missing)}. Route map: {OUT/'django-template-route-map.json'}")
print(f"Migration content: {OUT/'django-template-migration.json'}")
