# Support chat

The floating support widget and `/support/` use the same chat API and conversation.
Visitors can type messages, restore session history, start a new chat, and create
a support ticket from the full support page. Replies are rendered as text, so
user/provider content cannot inject HTML.

Conversations, messages and tickets are stored in PostgreSQL. Anonymous history
belongs to its browser session; signed-in chats belong to the account. Known API
key/token patterns are redacted before storage and before sending history to AI.
CSRF protection applies to anonymous and signed-in submissions. Message sending
is rate limited; history refreshes do not consume the message quota.

## AI setup

Without an AI key the bot provides built-in help for authentication, API keys,
search, quotas, batch calls, account access, profile photos, and server errors.

For AI replies, set these server-side variables on every host running Django:

```env
OPENAI_API_KEY=
OPENAI_API_BASE=https://api.openai.com/v1
SUPPORT_BOT_MODEL=gpt-5-mini
SUPPORT_BOT_MAX_TOKENS=1500
SUPPORT_RATE_LIMIT=20
```

Add them to local `.env` for development; restart/redeploy after changes. Never
expose the AI key in browser code. Existing OpenAI-compatible endpoints remain
supported through `OPENAI_API_BASE`. Provider failures use topic-specific built-in
help rather than making chat unavailable. AI context uses the most recent turns.

## Staff inbox and replies

Staff use Django admin's Support tickets and Support conversations sections.
Each ticket references its full conversation; its text contains the recent
transcript. Repeated submission returns the existing open ticket. In a support
conversation, staff can add a message with role `assistant` and source `human`.
The customer sees it by reopening the widget or using Refresh on `/support/`.
Changing a ticket to resolved in admin resolves its conversation when all its
tickets are resolved. A new customer message reopens that conversation.

This is an asynchronous support inbox, not a staffed live-chat service. Ticket
creation does not automatically send email. No notification service is required.

## Verification

Automated coverage includes guest and account ownership, invalid UUIDs, CSRF,
history after long chats, AI success/failure (mocked), redaction, tickets and rate
limits. A live AI response requires an actual provider key. No new database
migration is needed: this uses the existing support models.
