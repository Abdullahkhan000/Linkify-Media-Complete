# Developer Playground

Open `/playground/` from the dashboard, mobile navigation, or documentation. Sign in, paste a full API key, select an endpoint, edit its parameters, then run it. Keys cannot be recovered from stored hashes; create or rotate a key if you lost the original secret.

Supported endpoints: title search, paginated search results, media details, trending, people search, usage, and batch search. Requests go directly to the existing API with `X-API-Key`; scopes, plan restrictions, throttling, and quota are enforced by the existing middleware. Batch requires the batch scope and a Pro or Business plan.

The response panel shows HTTP status, elapsed browser time, formatted JSON, request cost, daily limit, and remaining daily requests. Authenticated endpoint responses include:

- `X-Quota-Cost`: `1` when usage was reserved, including endpoint errors.
- `X-Quota-Limit`: the per-key daily limit, or `unlimited`.
- `X-Quota-Remaining`: remaining requests for this key on the server's current date, or `unlimited`.

Authentication, scope, and rate-limit failures before reservation do not include these headers or create a usage log. Cancelling a browser request does not guarantee cancellation of server processing or quota usage. Usage requests themselves also consume one request; the playground reads response headers instead of polling Usage.

API keys are only held in the page's password input, cleared on page exit, and never written to local/session storage. Responses and the playground HTML use `Cache-Control: private, no-store`. Snippets use `LINKIFY_API_KEY` from the server environment, never the pasted credential. Copyable cURL uses POSIX shell syntax; Python requires `requests`; JavaScript targets Node.js with built-in fetch.

Batch authenticates exclusively through the API-key middleware instead of Django session authentication so external API clients can POST without a browser CSRF cookie. Session-authenticated account endpoints retain their CSRF protection.

No new environment variables, API providers, packages, or database migrations are required.
