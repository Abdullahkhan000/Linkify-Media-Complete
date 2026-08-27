<div align="center">

# 🎬 Linkify Media — Enterprise Media & Metadata API SaaS Platform

[![Django](https://img.shields.io/badge/Django-6.0-092E20?style=for-the-badge&logo=django&logoColor=white)](https://djangoproject.com/)
[![DRF](https://img.shields.io/badge/Django_REST_Framework-3.17-red?style=for-the-badge&logo=django&logoColor=white)](https://www.django-rest-framework.org/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-Supported-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![Celery](https://img.shields.io/badge/Celery-Task_Queue-37B24D?style=for-the-badge&logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](LICENSE)

<p align="center">
  <b>A high-performance, developer-first RESTful API platform and SaaS dashboard for media search, metadata aggregation, API key management, rate limiting, and monetization.</b>
</p>

[✨ Features](#-features) •
[🚀 Quick Start](#-quick-start) •
[🐳 Docker Guide](#-docker-setup) •
[💻 Local Setup](#-local-setup) •
[🔑 API Reference](#-api-reference) •
[⚙️ Configuration](#%EF%B8%8F-environment-variables)

---

</div>

## 🌟 Overview

**Linkify Media** is a full-featured Django & Django REST Framework application designed to deliver real-time movie, TV series, and media metadata with built-in API key authorization, usage tracking, tiered subscriptions via **LemonSqueezy**, and a modern web dashboard.

Whether you're running it locally or deploying containerized workloads with **Docker**, Linkify Media provides enterprise-ready scalability, task queues with Celery/Redis, and clean UI components out-of-the-box.

---

## ✨ Features

- 🔍 **Real-Time Media Search**: Multi-provider metadata query engine powered by TMDB API.
- 🔑 **API Key Management**: Instant API key generation, rotation, and tier scoping (`Free`, `Pro`, `Business`).
- ⚡ **Automated Usage Logs & Middleware**: Dynamic request tracking, custom middleware verification, and usage stats.
- 💳 **Subscription & Billing**: Seamless integration with **LemonSqueezy** checkouts & webhook events.
- 📧 **Transactional Emails**: Resend API integration for account events and notifications.
- 📊 **User & Admin Dashboard**: Interactive front-end views for API key generation, logs, billing, and system docs.
- 🐳 **Docker Native**: Pre-configured `Dockerfile` and `docker-compose.yml` for zero-friction setup.

---

## 🛠️ Tech Stack

| Component | Technology | Description |
|---|---|---|
| **Backend Framework** | Django 6.0 & DRF 3.17 | Robust Python REST API framework |
| **Database** | SQLite (Dev) / PostgreSQL (Prod) | Relational database storage |
| **Task Queue** | Celery + Redis | Asynchronous background job processor |
| **Authentication** | Django Allauth | Email-based authentication & social auth ready |
| **Payments** | LemonSqueezy SDK & Webhooks | Automated tier upgrades & checkout links |
| **Containerization** | Docker & Docker Compose | Containerized application setup |

---

## 🚀 Quick Start

### 📋 Prerequisites

Make sure you have the following installed on your machine:
- **Python**: `3.10` or higher
- **Git**: `2.x+`
- **Docker Desktop** *(Optional, for containerized run)*: `20.10+`

---

## 🐳 Docker Setup (Recommended)

Run the Django application and Redis service in isolated containers with **Docker Compose**. The Compose setup persists SQLite data and collected static files in named volumes.

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/Abdullahkhan000/Linkify-Media-Complete.git
cd "Linkify-Media-Complete"
```

### 2️⃣ Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
*(Update your `TMDB_API_KEY`, `RESEND_API_KEY`, and secrets in `.env`)*

### 3️⃣ Build and Launch Containers
```bash
docker compose up --build -d
```

### 4️⃣ Check Status & Logs
```bash
docker compose ps
docker compose logs -f web
```

### 5️⃣ Access the Application
Open your browser and navigate to:
- 🌐 **Web Dashboard & Landing Page**: `http://localhost:8000`
- 🛠️ **Django Admin Portal**: `http://localhost:8000/admin/`

To stop the Docker containers:
```bash
docker compose down
```

---

## 💻 Local Setup (Without Docker)

If you prefer running the app directly on your host environment:

### 1️⃣ Clone & Navigate
```bash
git clone https://github.com/Abdullahkhan000/Linkify-Media-Complete.git
cd "Linkify-Media-Complete"
```

### 2️⃣ Create & Activate Virtual Environment
- **Windows (PowerShell/CMD)**:
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\activate
  ```
- **macOS / Linux**:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

### 3️⃣ Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4️⃣ Set Up Environment Variables
Create a `.env` file in the root directory:
```bash
cp .env.example .env
```

### 5️⃣ Run Database Migrations
```bash
python manage.py migrate
```

### 6️⃣ Create Superuser (Admin)
```bash
python manage.py createsuperuser
```

### 7️⃣ Start Development Server
```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` in your browser! 🚀

---

## ⚙️ Environment Variables

Create `.env` in the root folder with the following variables:

```ini
# Django Settings
SECRET_KEY=your-django-secret-key
DEBUG=True
ALLOWED_HOSTS=*

# External Services
TMDB_API_KEY=your_tmdb_api_key_here
RESEND_API_KEY=your_resend_api_key_here

# LemonSqueezy Billing & Webhook Settings
LEMONSQUEEZY_API_KEY=your_lemonsqueezy_key
LEMONSQUEEZY_STORE_ID=your_store_id
LEMONSQUEEZY_WEBHOOK_SECRET=your_webhook_secret

# Redis / Celery (Optional)
REDIS_URL=redis://localhost:6379/0
```

---

## 🔑 API Reference & Usage

### 🛡️ Authentication
Include your generated API key in the `X-API-KEY` request header or `api_key` query parameter.

---

### 1️⃣ Search Media
Query movies and TV shows with automatic TMDB enrichment.

- **Endpoint**: `GET /api/search/`
- **Headers**: `X-API-KEY: <your-api-key>`
- **Query Params**: `query=Inception`

#### 💻 `cURL` Example:
```bash
curl -X GET "http://localhost:8000/api/search/?query=Inception" \
     -H "X-API-KEY: 123e4567-e89b-12d3-a456-426614174000"
```

#### 🐍 `Python` Example:
```python
import requests

url = "http://localhost:8000/api/search/"
headers = {"X-API-KEY": "123e4567-e89b-12d3-a456-426614174000"}
params = {"query": "Interstellar"}

response = requests.get(url, headers=headers, params=params)
print(response.json())
```

---

### 2️⃣ Batch Media Metadata
Process multiple query requests in a single payload.

- **Endpoint**: `POST /api/batch/`
- **Headers**: `X-API-KEY: <your-api-key>`
- **Body**:
```json
{
  "titles": ["The Dark Knight", "Avatar", "Oppenheimer"]
}
```

---

### 3️⃣ Manage API Keys
List or create API keys for your account.

- **Endpoint**: `GET / POST /api/keys/`
- **Authentication**: Session / Cookie Auth (Logged in user)

---

### 4️⃣ API Usage Analytics
Retrieve total request counts and endpoint breakdown.

- **Endpoint**: `GET /api/usage/`
- **Headers**: `X-API-KEY: <your-api-key>`

---

## 🤖 AI Support Assistant

The public `/support/` page includes a premium support assistant with persistent conversations, Linkify product knowledge, API troubleshooting guidance, browser-session protection, and one-click escalation to the Django `SupportTicket` workflow. The assistant works safely without an AI key by returning a deterministic support fallback; adding an OpenAI-compatible key activates AI responses.

Set these optional values in `.env`:

```ini
OPENAI_API_KEY=your_key_here
OPENAI_API_BASE=https://api.openai.com/v1
SUPPORT_BOT_MODEL=gpt-5-mini
SUPPORT_BOT_MAX_TOKENS=700
```

The backend endpoints are `GET/POST /api/support/chat/` for conversation history and replies, and `POST /api/support/ticket/` for human escalation. Never send API keys, passwords, payment details, or webhook secrets to the assistant.

---

## 📁 Project Architecture

```
drf linkify media app/
├── 📁 api/                   # Core REST API app
│   ├── adapters.py          # Custom Allauth adapter
│   ├── middleware.py        # API key verification middleware
│   ├── models.py            # Profile, APIKey, UsageLog models
│   ├── serializers.py       # DRF Serializers
│   ├── views.py             # API endpoints & web dashboard views
│   └── urls.py              # URL routing
├── 📁 core/                  # Django project settings
│   ├── settings.py          # Main settings file
│   ├── urls.py              # Root URL router
│   ├── wsgi.py              # WSGI entry point
│   └── asgi.py              # ASGI entry point
├── 📁 templates/             # HTML Templates (Landing, Dashboard, Docs)
├── 📄 Dockerfile            # Docker build container recipe
├── 📄 docker-compose.yml    # Docker Multi-container orchestration
├── 📄 manage.py             # Django CLI entry script
├── 📄 requirements.txt      # Python dependencies
└── 📄 README.md             # Project documentation
```

---

## 🧪 Testing

Run test suites using Django's built-in test runner:

```bash
python manage.py test api
```

---

## 🤝 Contributing

Contributions are always welcome!
1. **Fork** the repository
2. **Create** your feature branch (`git checkout -b feature/AmazingFeature`)
3. **Commit** your changes (`git commit -m 'Add some AmazingFeature'`)
4. **Push** to the branch (`git push origin feature/AmazingFeature`)
5. **Open** a Pull Request

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.

---

<div align="center">
  <sub>Built with ❤️ using Python, Django, and DRF.</sub>
</div>
