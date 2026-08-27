#!/bin/sh
set -eu

python manage.py migrate --noinput
python manage.py configure_social_apps
python manage.py collectstatic --noinput

exec "$@"
