# Request IDs and searchable logs

Application API responses include a server-generated UUID in `X-Request-ID`, including authentication errors and public/session API endpoints. Client-provided IDs are ignored. Reserved API-key requests persist that same ID with their status, endpoint, timestamp, and latency. No body, query values, or full API key is stored. Authentication, scope, and quota rejections receive an ID but do not reserve usage or create a usage log; public/session API calls are also excluded from usage logs.

Open `/usage-logs/` from the dashboard. Search by Request ID (exact UUID), endpoint, or key name; combine with status group and inclusive date filters. Results paginate 50 per page and remain limited to the signed-in user's keys. Filtered CSV exports use the same filters and append `request_id` after the existing columns. Old rows retain a blank ID and are labelled legacy requests.

The API Playground displays `X-Request-ID` and links directly to the filtered logs page. Logs and CSV downloads are private and not cached. No extra API key or environment setting is needed.

Migration: `0014_usage_request_id` adds a nullable unique UUID column so existing rows stay intact and old application versions can still insert rows without IDs. Test on a Neon branch, then apply with `python manage.py migrate --noinput` before deploying this code.
