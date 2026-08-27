import json

from django.test import TestCase
from django.urls import reverse

from .models import SupportConversation, SupportMessage, SupportTicket


class SupportBotTests(TestCase):
    def post_json(self, url_name, payload):
        return self.client.post(
            reverse(url_name),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_chat_uses_safe_fallback_without_api_key(self):
        response = self.post_json("support-chat", {"message": "How do I use my API key?"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["source"], "fallback")
        self.assertIn("X-API-Key", body["message"])
        self.assertEqual(SupportConversation.objects.count(), 1)
        self.assertEqual(SupportMessage.objects.filter(role="user").count(), 1)
        self.assertEqual(SupportMessage.objects.filter(role="assistant").count(), 1)

    def test_escalation_creates_ticket_with_transcript(self):
        chat_response = self.post_json(
            "support-chat",
            {"message": "I need a human because I have a billing issue."},
        )
        self.assertEqual(chat_response.status_code, 200)
        conversation_id = chat_response.json()["conversation_id"]

        ticket_response = self.post_json(
            "support-ticket-create",
            {
                "conversation_id": conversation_id,
                "name": "Test User",
                "email": "test@example.com",
                "subject": "Billing help",
            },
        )

        self.assertEqual(ticket_response.status_code, 201)
        self.assertEqual(SupportTicket.objects.count(), 1)
        ticket = SupportTicket.objects.get()
        self.assertEqual(str(ticket.conversation_id), conversation_id)
        self.assertIn("billing issue", ticket.message)
        self.assertEqual(ticket.priority, "urgent")

    def test_chat_rejects_another_session_conversation(self):
        first = self.post_json("support-chat", {"message": "Hello support"})
        conversation_id = first.json()["conversation_id"]
        self.client.cookies.clear()

        response = self.post_json(
            "support-chat",
            {"conversation_id": conversation_id, "message": "Can I access this?"},
        )

        self.assertEqual(response.status_code, 403)
