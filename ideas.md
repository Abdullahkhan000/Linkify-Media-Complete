# Linkify Media project direction

- Keep the product as one Django application: Django templates render every user-facing page and native account flow; Django REST Framework serves the API.
- Preserve the established Linkify visual system in Django: its palette, typography, cards, page structure, interaction behavior, and responsive dashboard.
- Keep the original template copy available through a sanitized, noindex Django template archive. Regenerate it with `python scripts/generate_django_template_data.py`.
- Local startup must require Python dependencies only. Keep JavaScript interactions framework-free and static assets directly served by Django/WhiteNoise.
- Do not describe unavailable backend features as implemented; keep incomplete workspace areas explicit and honest.
