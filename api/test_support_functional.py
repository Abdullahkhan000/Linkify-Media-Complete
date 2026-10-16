import json
import os
from unittest.mock import Mock, patch

import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from .models import SupportConversation, SupportMessage, SupportTicket
from .support_bot import generate_reply


@override_settings(SECURE_SSL_REDIRECT=False)
class FunctionalSupportTests(TestCase):
    def setUp(self):
        cache.clear()
        self.env = patch.dict(os.environ, {'OPENAI_API_KEY': ''})
        self.env.start()
        self.addCleanup(self.env.stop)

    def post(self, data, path='/api/support/chat/', client=None):
        return (client or self.client).post(path, json.dumps(data), content_type='application/json')

    def test_roundtrip_history_and_ticket_status(self):
        response = self.post({'message': 'Help with my profile photo'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('/profile/', response.json()['message'])
        identifier = response.json()['conversation_id']
        ticket = self.post({'conversation_id': identifier, 'name': 'Tester', 'email': 'test@example.com'}, '/api/support/ticket/')
        self.assertEqual(ticket.status_code, 201)
        history = self.client.get('/api/support/chat/').json()
        self.assertEqual(history['conversation_id'], identifier)
        self.assertEqual(history['ticket']['id'], ticket.json()['ticket_id'])
        self.assertEqual(len(history['messages']), 2)

    def test_repeated_ticket_submission_returns_existing_ticket(self):
        identifier = self.post({'message': 'Need a human'}).json()['conversation_id']
        data = {'conversation_id': identifier, 'name': 'Test', 'email': 'test@example.com'}
        self.assertEqual(self.post(data, '/api/support/ticket/').status_code, 201)
        self.assertEqual(self.post(data, '/api/support/ticket/').status_code, 200)
        self.assertEqual(SupportTicket.objects.count(), 1)

    def test_malformed_conversation_id_and_message_are_handled(self):
        for identifier in ('invalid-id', ['bad'], 123):
            response = self.post({'message': 'hello', 'conversation_id': identifier})
            self.assertEqual(response.status_code, 404)
        self.assertEqual(self.post({'message': {'text': 'wrong'}}).status_code, 400)

    def test_anonymous_mutations_require_csrf(self):
        browser = Client(enforce_csrf_checks=True)
        self.assertEqual(self.post({'message': 'hello'}, client=browser).status_code, 403)
        self.assertEqual(self.post({}, '/api/support/ticket/', client=browser).status_code, 403)
        browser.get('/support/')
        response = browser.post('/api/support/chat/', json.dumps({'message': 'hello'}),
            content_type='application/json', HTTP_X_CSRFTOKEN=browser.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 200)

    def test_secrets_not_stored_or_forwarded(self):
        response = self.post({'message': 'My key is lm_live_123456789abcdef and I see 401'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('123456789abcdef', response.json()['user_message'])
        self.assertFalse(SupportMessage.objects.filter(content__contains='123456789abcdef').exists())

    def test_latest_turn_is_used_after_long_conversation(self):
        conversation = SupportConversation.objects.create()
        SupportMessage.objects.bulk_create([
            SupportMessage(conversation=conversation, role='user', content=f'old message {i}') for i in range(30)
        ])
        SupportMessage.objects.create(conversation=conversation, role='user', content='How do batch requests work?')
        self.assertIn('POST /api/v1/batch/', generate_reply(conversation)['content'])

    def test_ai_receives_recent_history_and_uses_its_reply(self):
        provider = Mock()
        provider.json.return_value = {'choices': [{'message': {'content': 'Here is the correct API help.'}}]}
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}), patch('api.support_bot.requests.post', return_value=provider) as call:
            response = self.post({'message': 'How do I authenticate?'})
        self.assertEqual(response.json()['source'], 'ai')
        self.assertEqual(response.json()['message'], 'Here is the correct API help.')
        payload = call.call_args.kwargs['json']
        self.assertEqual(payload['messages'][-1]['content'], 'How do I authenticate?')
        self.assertFalse(payload['store'])

    def test_ai_failure_keeps_topic_specific_help(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}), patch('api.support_bot.requests.post', side_effect=requests.Timeout):
            response = self.post({'message': 'How do batch requests work?'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['source'], 'fallback')
        self.assertIn('POST /api/v1/batch/', response.json()['message'])

    def test_logged_in_user_cannot_read_or_ticket_another_users_chat(self):
        owner = get_user_model().objects.create_user(username='chat_owner')
        other = get_user_model().objects.create_user(username='other_user')
        self.client.force_login(owner)
        identifier = self.post({'message': 'hello'}).json()['conversation_id']
        self.client.force_login(other)
        self.assertEqual(self.client.get('/api/support/chat/', {'conversation_id': identifier}).status_code, 403)
        self.assertEqual(self.post({'conversation_id': identifier}, '/api/support/ticket/').status_code, 403)

    def test_staff_replies_are_visible_and_resolved_chat_reopens(self):
        identifier = self.post({'message': 'hello'}).json()['conversation_id']
        conversation = SupportConversation.objects.get(pk=identifier)
        SupportMessage.objects.create(conversation=conversation, role='assistant', content='A staff reply', source='human')
        self.assertEqual(self.client.get('/api/support/chat/').json()['messages'][-1]['content'], 'A staff reply')
        conversation.status = 'resolved'
        conversation.save()
        response = self.post({'conversation_id': identifier, 'message': 'How do batch calls work?'})
        self.assertEqual(response.json()['status'], 'open')

    @override_settings(SUPPORT_RATE_LIMIT=1)
    def test_history_refresh_does_not_consume_message_limit(self):
        identifier = self.post({'message': 'hello'}).json()['conversation_id']
        for _ in range(3):
            self.assertEqual(self.client.get('/api/support/chat/').status_code, 200)
        self.assertEqual(self.post({'message': 'another', 'conversation_id': identifier}).status_code, 429)
