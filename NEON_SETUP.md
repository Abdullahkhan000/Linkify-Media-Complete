# Neon PostgreSQL

The existing Django ORM and psycopg2 driver connect directly to Neon PostgreSQL.
Neon Auth is disabled in `neon.ts`; Django/allauth continues to manage accounts.

## Link and provision

```sh
npx --yes neon@latest init -y --no-agent-setup --org-id org-still-firefly-07850187 --project-id divine-band-56553868 --branch production --services postgres
npx --yes neon@latest deploy
```

On Windows PowerShell, use `npx.cmd` / `npm.cmd` if execution policy blocks the
PowerShell launchers. Complete `neon login` in your browser when required.

The CLI preserves unrelated values and writes these secrets to the existing
`.env`, or to `.env.local` when no `.env` exists:

- `DATABASE_URL`: pooled PostgreSQL connection for application traffic.
- `DATABASE_URL_UNPOOLED`: direct PostgreSQL connection for migrations.
- `NEON_BRANCH`: linked database branch metadata.

Django reads both environment files, with process variables taking precedence,
then `.env`, then `.env.local`. Do not commit either file. `.neon` is also ignored;
`neon.ts` is the source-controlled service configuration.

## Initialize and run

```sh
python manage.py migrate --noinput
npm install
npm run build
python manage.py runserver 127.0.0.1:8765 --noreload
```

`migrate`, `showmigrations`, and `sqlmigrate` automatically prefer
`DATABASE_URL_UNPOOLED`. Normal requests use `DATABASE_URL`. Server-side cursors
are disabled for transaction pooling, connections close after each request by
default, and TLS/channel-binding options from Neon's URL are preserved.

## Verify against the running app

In a second terminal, using the same environment/database as the server:

```sh
python scripts/verify_neon.py --base-url http://127.0.0.1:8765
```

This requires local HTTP cookies/redirects to be enabled and
`ACCOUNT_EMAIL_VERIFICATION=none`. It verifies PostgreSQL reads, real HTTP signup,
the created user/profile and database-backed session, repeat login, and logout.
It removes its generated test user afterward. It does not print credentials.
Use only against a database and server you intend to test.

For an isolated branch, pull its variables into an ignored file and load that
file into the server environment before starting it. Pass the same file to the
verification script using `--env-file .env.neon-verify`.

## Render and Vercel

Local `.env` values are not uploaded to either host. Add `DATABASE_URL` and
`DATABASE_URL_UNPOOLED` in the environment settings of each host running Django,
then redeploy. Both deployments must target the same Neon production branch if
they should share accounts. Set `DEBUG=False` for production. Run migrations once
as a deployment task, never on every HTTP request.

Existing SQLite users and data are not copied by provisioning or migrations.

References: [Neon Django guide](https://neon.com/blog/python-django-and-neons-serverless-postgres),
[Neon pooling](https://neon.com/docs/connect/connection-pooling),
[Django PostgreSQL](https://docs.djangoproject.com/en/6.0/ref/databases/).
