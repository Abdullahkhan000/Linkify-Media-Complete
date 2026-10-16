import os
import re
import logging
from typing import Iterable

import requests

from .models import SupportConversation, SupportMessage

logger = logging.getLogger(__name__)
SECRET_PATTERN = re.compile(r'(?:lm_live_|sk-|whsec_)[A-Za-z0-9_-]{8,}|Bearer\s+[A-Za-z0-9._-]{12,}', re.I)


def redact_secrets(text):
    return SECRET_PATTERN.sub('[secret removed]', text)


PRODUCT_KNOWLEDGE = """
Linkify Media is a Django and Django REST Framework media metadata API.
Current API behavior:
- Search: GET /api/v1/search/?q=Inception&type=movie&country=us&fields=title,poster,imdb
- Authentication: X-API-Key header is preferred. API keys are managed at /api/keys/.
- Supported media aliases: movie, film, tv, show, series, anime, tvshow, tv show.
- Batch: POST /api/v1/batch/ with {\"items\":[{\"q\":\"Dune\",\"type\":\"movie\"}]}; Pro and Business plans only.
- Usage: GET /api/v1/usage/ with an active API key.
- Free plan: 1 API key and 100 requests/day.
- Pro plan: 5 API keys and 5,000 requests/day.
- Business plan: up to 100 API keys and unlimited daily requests.
- Search results use TMDB metadata including title, year, genres, runtime, rating, poster and cast.
  IMDb, Rotten Tomatoes, Metacritic, Letterboxd and JustWatch are outbound links, not separately aggregated ratings.
- Users edit names and profile photos at /profile/. Photos accept JPG, PNG or WebP up to 5 MB and 16 megapixels.
- API responses include X-Request-ID. The API Playground displays it and links to /usage-logs/ for exact lookup. Signed-in developers can filter their own reserved API-key request logs by ID, endpoint, key name, status, and dates, then export filtered CSV. Authentication, scope, and quota rejections have IDs but no usage-log entry.
- Signed-in users save movies/shows and mark favorites at /watchlist/. They can save watch status, a personal 1–10 rating, and private notes, search their collection, and sort it by title, date, or personal rating. Picked for you recommends new titles from up to three favorites or titles rated at least 8/10; use Refresh recommendations after changing preferences. It needs no personal API key. Where to watch shows country-specific JustWatch/TMDB availability.
- Google/GitHub login and signup use /accounts/login/ and /accounts/signup/; password reset is /accounts/password/reset/.
- API keys are scoped, stored as hashes, displayed only once, and can be rotated or revoked.
- Users must never share API keys, passwords, payment card details, or webhook secrets in chat.
""".strip()

ESCALATION_TERMS = re.compile(
    r"\b(human|agent|representative|support team|billing|refund|charge|payment|invoice|security|breach|hack|delete my account|legal|urgent|complaint)\b",
    re.IGNORECASE,
)


def _api_base() -> str:
    base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/")
    return base if base.endswith("/v1") else f"{base}/v1"


def ai_is_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def _fallback_reply(message: str) -> str:
    if ESCALATION_TERMS.search(message):
        return (
            "I can help collect the details, but this request should be reviewed by our support team. "
            "Please use **Escalate to a human** below and include your account email, endpoint, and the "
            "exact error or checkout reference. Never include an API key or payment details."
        )

    lowered = message.lower()
    if 'creat' in lowered and ('key' in lowered or 'token' in lowered):
        return 'Open your dashboard, choose Create key, give it a name and the scopes you need, then save the secret securely: it is only shown once. If you lost it, rotate the key. Never paste it here.'
    if any(term in lowered for term in ('watchlist', 'favorite', 'favourite', 'where to watch')):
        return 'Sign in and open /watchlist/. Search a movie or TV show, select Save to watchlist, then mark it as a Favorite if you like. You can filter Favorites or remove a title. Where to watch shows viewing options for a two-letter country code, such as US, PK or GB. No personal API key is needed.'
    if any(term in lowered for term in ('profile', 'photo', 'avatar', 'name change')):
        return 'Open /profile/ to edit your first and last name or upload a profile photo. Photos must be JPG, PNG or WebP, at most 5 MB and 16 megapixels. Select Save profile to apply changes. You can also replace or remove the current photo.'
    if any(term in lowered for term in ('login', 'sign in', 'signup', 'sign up', 'password', 'google', 'github')):
        return 'Use /accounts/login/ to sign in with email, username, Google or GitHub. New users can use /accounts/signup/. If you forgot your password, use /accounts/password/reset/. Tell me the exact error message, without sharing a password or verification link.'
    if any(term in lowered for term in ('search', 'movie', 'anime', '404')):
        return 'Search with GET /api/v1/search/?q=Inception&type=movie and your X-API-Key header. Supported types include movie, tv, show, series and anime. If a title is missing, try its official name and correct media type. Which title and HTTP status are you seeing?'
    if "api key" in lowered or "401" in lowered or "authenticat" in lowered:
        return (
            "For authentication issues, send the key in the `X-API-Key` header, confirm that the key is "
            "active, and make sure you are calling the correct base URL. Do not put the key in a public "
            "frontend bundle or paste it into this chat."
        )
    if "rate" in lowered or "quota" in lowered or "429" in lowered or 'limit' in lowered:
        return (
            "A 429 response usually means a minute or daily quota has been reached. Check `/api/v1/usage/`, review "
            "your usage logs, or upgrade the plan. Free has 100 requests/day, Pro has 5,000, and Business "
            "is unlimited according to the current application rules."
        )
    if "batch" in lowered:
        return (
            "The batch endpoint is `POST /api/v1/batch/` and expects an `items` array containing `q` and "
            "optional `type` and `country` values. It is available on Pro and Business plans."
        )
    if any(term in lowered for term in ('500', '502', '503', 'unavailable', 'server error')):
        return 'Retry once and check /api/health/ and /api/ready/. A 500 is a server error; changing your API key will not fix a database or upstream outage. Share the endpoint, status and approximate time, or open a support ticket with the redacted error.'
    return (
        "I can help with API authentication, media search, batch requests, usage limits, billing, and "
        "account troubleshooting. Tell me the endpoint, HTTP status, and a redacted version of the error "
        "you received."
    )


def _history_messages(messages: Iterable[SupportMessage]) -> list[dict[str, str]]:
    history = [{"role": "system", "content": _system_prompt()}]
    for item in list(messages)[-12:]:
        if item.role in {"user", "assistant"}:
            history.append({"role": item.role, "content": redact_secrets(item.content)})
    return history


def _system_prompt() -> str:
    return (
        "You are Linkify Media's senior developer-support assistant. Give concise, accurate, "
        "actionable answers using only the product context below. Ask one focused follow-up question "
        "when key details are missing. Explain code examples clearly. Never invent outages, refunds, "
        "account changes, or policy commitments. Never request secrets. If the user reports billing, "
        "security, legal, account deletion, a refund, or explicitly asks for a human, recommend human "
        "escalation. Match the user's language, including Roman Urdu. You cannot access or modify accounts, "
        "billing or infrastructure. Never claim that a ticket exists until the user submits the ticket form. "
        "End technical replies with a short next step.\n\n"
        f"PRODUCT CONTEXT:\n{PRODUCT_KNOWLEDGE}"
    )


def generate_reply(conversation: SupportConversation) -> dict:
    latest_messages = list(reversed(list(conversation.messages.order_by('-created_at', '-id')[:24])))
    latest_user_message = next(
        (item.content for item in reversed(latest_messages) if item.role == "user"), ""
    )
    should_escalate = bool(ESCALATION_TERMS.search(latest_user_message))

    if not ai_is_configured():
        return {
            "content": _fallback_reply(latest_user_message),
            "source": "fallback",
            "should_escalate": should_escalate,
        }

    payload = {
        "model": os.getenv("SUPPORT_BOT_MODEL", "gpt-5-mini"),
        "messages": _history_messages(latest_messages),
        "max_completion_tokens": int(os.getenv("SUPPORT_BOT_MAX_TOKENS", "1500")),
        "store": False,
    }
    headers = {
        "Authorization": f"Bearer {os.environ['OPENAI_API_KEY'].strip()}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            f"{_api_base()}/chat/completions",
            json=payload,
            headers=headers,
            timeout=(5, 30),
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("AI provider returned an empty response")
        return {
            "content": content.strip(),
            "source": "ai",
            "should_escalate": should_escalate,
        }
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
        logger.warning('Support AI unavailable (%s); using built-in assistance.', type(exc).__name__)
        return {
            "content": (
                "Live AI is temporarily unavailable. " + _fallback_reply(latest_user_message)
            ),
            "source": "fallback",
            "should_escalate": True,
        }
