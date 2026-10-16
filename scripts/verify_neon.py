"""Exercise the running Django app and Neon database without keeping test users."""
import argparse
import os
from pathlib import Path
import re
import secrets
import sys

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base-url', default='http://127.0.0.1:8765')
parser.add_argument('--env-file', help='Must match the environment of the running app')
args = parser.parse_args()
if args.env_file:
    load_dotenv(args.env_file, override=True)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import connection

if connection.vendor != 'postgresql':
    raise RuntimeError('Verification requires PostgreSQL, not a SQLite fallback.')
with connection.cursor() as cursor:
    cursor.execute('SELECT 1')
    assert cursor.fetchone() == (1,)
print('PASS PostgreSQL SELECT 1', flush=True)

base = args.base_url.rstrip('/')
username = f'neon_verify_{secrets.token_hex(6)}'
email = f'{username}@example.com'
password = f'Neon-verify-{secrets.token_urlsafe(24)}'
User = get_user_model()
browser = requests.Session()


def page(path):
    response = browser.get(base + path, timeout=30)
    assert response.status_code == 200, f'{path}: HTTP {response.status_code}'
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', response.text)
    assert token, f'{path}: CSRF form token missing'
    print(f'PASS GET {path}: 200', flush=True)
    return token.group(1)


def post(path, data):
    response = browser.post(
        base + path, data=data, headers={'Referer': base + path},
        allow_redirects=False, timeout=30,
    )
    assert response.status_code == 302, f'{path}: HTTP {response.status_code}'
    return response


def check_session(user):
    key = browser.cookies.get(settings.SESSION_COOKIE_NAME)
    stored = Session.objects.get(session_key=key).get_decoded()
    assert stored['_auth_user_id'] == str(user.pk)
    print('PASS authenticated session persisted in PostgreSQL', flush=True)


try:
    token = page('/accounts/signup/')
    result = post('/accounts/signup/', {
        'csrfmiddlewaretoken': token, 'username': username, 'email': email,
        'password1': password, 'password2': password, 'terms': 'on',
    })
    assert result.headers['Location'] == '/dashboard/'
    user = User.objects.get(username=username, email=email)
    assert user.check_password(password)
    assert user.profile.pk
    print('PASS HTTP signup created user and profile in PostgreSQL', flush=True)
    check_session(user)
    token = page('/dashboard/')
    post('/accounts/logout/', {'csrfmiddlewaretoken': token})
    print('PASS HTTP logout', flush=True)
    token = page('/accounts/login/')
    result = post('/accounts/login/', {
        'csrfmiddlewaretoken': token, 'login': email, 'password': password,
    })
    assert result.headers['Location'] == '/dashboard/'
    check_session(user)
    print('PASS HTTP login with persisted user', flush=True)
    token = page('/dashboard/')
    key = browser.cookies.get(settings.SESSION_COOKIE_NAME)
    post('/accounts/logout/', {'csrfmiddlewaretoken': token})
    assert not Session.objects.filter(session_key=key).exists()
    print('PASS HTTP logout removed PostgreSQL session', flush=True)
finally:
    User.objects.filter(username=username, email=email).delete()
    browser.close()
    connection.close()
    print('Verification test user cleaned up', flush=True)
