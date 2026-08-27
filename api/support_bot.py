import os
import re
from typing import Iterable

import requests

from .models import SupportConversation, SupportMessage


PRODUCT_KNOWLEDGE = """
Linkify Media is a Django and Django REST Framework media metadata API.
Current API behavior:
- Search: GET /api/search/?q=Inception&type=movie&country=us&fields=title,poster,imdb
- Authentication: X-API-Key header is preferred. API keys are managed at /api/keys/.
- Supported media aliases: movie, film, tv, show, series, anime, tvshow, tv show.
- Batch: POST /api/batch/ with {\"items\":[{\"q\":\"Dune\",\"type\":\"movie\"}]}; Pro and Business plans only.
- Usage: GET /api/usage/ with an active API key.
- Free plan: 1 API key and 100 requests/day.
- Pro plan: 5 API keys and 5,000 requests/day.
- Business plan: up to 100 API keys and unlimited daily requests.
- Search results are enriched through TMDB and can include title, year, genres, runtime,
  rating, poster, cast, TMDB/IMDb links, Rotten Tomatoes, Metacritic, Letterboxd, and JustWatch.
- Users must never share API keys, passwords, payment card details, or webhook secrets in chat.
""".strip()

ESCALATION_TERMS = re.compile(
    r"\b(human|agent|representative|support team|refund|charge|payment|invoice|security|breach|hack|delete my account|legal|urgent|complaint)\b",
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
    if "api key" in lowered or "401" in lowered or "authentication" in lowered:
        return (
            "For authentication issues, send the key in the `X-API-Key` header, confirm that the key is "
            "active, and make sure you are calling the correct base URL. Do not put the key in a public "
            "frontend bundle or paste it into this chat."
        )
    if "rate" in lowered or "quota" in lowered or "429" in lowered:
        return (
            "A 429 response usually means the daily quota has been reached. Check `/api/usage/`, review "
            "your usage logs, or upgrade the plan. Free has 100 requests/day, Pro has 5,000, and Business "
            "is unlimited according to the current application rules."
        )
    if "batch" in lowered:
        return (
            "The batch endpoint is `POST /api/batch/` and expects an `items` array containing `q` and "
            "optional `type` and `country` values. It is available on Pro and Business plans."
        )
    return (
        "I can help with API authentication, media search, batch requests, usage limits, billing, and "
        "account troubleshooting. Tell me the endpoint, HTTP status, and a redacted version of the error "
        "you received."
    )


def _history_messages(messages: Iterable[SupportMessage]) -> list[dict[str, str]]:
    history = [{"role": "system", "content": _system_prompt()}]
    for item in list(messages)[-12:]:
        if item.role in {"user", "assistant"}:
            history.append({"role": item.role, "content": item.content})
    return history


def _system_prompt() -> str:
    return (
        "You are Linkify Media's senior developer-support assistant. Give concise, accurate, "
        "actionable answers using only the product context below. Ask one focused follow-up question "
        "when key details are missing. Explain code examples clearly. Never invent outages, refunds, "
        "account changes, or policy commitments. Never request secrets. If the user reports billing, "
        "security, legal, account deletion, a refund, or explicitly asks for a human, recommend human "
        "escalation. End technical replies with a short next step.\n\n"
        f"PRODUCT CONTEXT:\n{PRODUCT_KNOWLEDGE}"
    )


def generate_reply(conversation: SupportConversation) -> dict:
    latest_messages = list(conversation.messages.order_by("created_at")[:24])
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
        "max_completion_tokens": int(os.getenv("SUPPORT_BOT_MAX_TOKENS", "700")),
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
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return {
            "content": (
                "The AI assistant is temporarily unavailable, but your request can still be handled. "
                "Please try again or use **Escalate to a human** so the support team receives the conversation."
            ),
            "source": "fallback",
            "should_escalate": True,
        }
