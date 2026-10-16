import csv
import io
import uuid
from unittest.mock import AsyncMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import APIKey, UsageLog


@override_settings(SECURE_SSL_REDIRECT=False)
class RequestLogTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user=get_user_model().objects.create_user(username='request_owner')
        self.other=get_user_model().objects.create_user(username='other_request_owner')
        self.key,self.secret=APIKey.issue(user=self.user,name='My production key',scopes=['search','usage'])
        self.other_key,_=APIKey.issue(user=self.other,name='Other private key')

    def test_request_id_matches_persisted_log_and_ignores_client_id(self):
        supplied=str(uuid.uuid4())
        response=self.client.get('/api/v1/usage/',HTTP_X_API_KEY=self.secret,HTTP_X_REQUEST_ID=supplied)
        request_id=uuid.UUID(response['X-Request-ID'])
        self.assertNotEqual(str(request_id),supplied)
        log=UsageLog.objects.get(request_id=request_id)
        self.assertEqual(log.api_key,self.key)
        self.assertEqual(log.status_code,200)
        self.assertIsNotNone(log.latency_ms)
        second=self.client.get('/api/v1/usage/',HTTP_X_API_KEY=self.secret)
        self.assertNotEqual(second['X-Request-ID'],str(request_id))

    def test_rejections_public_and_session_endpoints_have_ids_without_usage(self):
        for path in ['/api/v1/usage/','/api/health/','/api/v1/watchlist/']:
            response=self.client.get(path)
            self.assertEqual(uuid.UUID(response['X-Request-ID']).version,4)
        self.assertFalse(UsageLog.objects.exists())

    def test_provider_error_has_searchable_id_without_secrets(self):
        with patch('api.views.fetch_media_links',AsyncMock(return_value={'Error':'Unavailable','code':'provider_unavailable'})):
            response=self.client.get('/api/v1/search/',{'q':'PRIVATE_QUERY'},HTTP_X_API_KEY=self.secret)
        self.assertEqual(response.status_code,503)
        self.client.force_login(self.user)
        result=self.client.get('/usage-logs/',{'request_id':response['X-Request-ID']})
        self.assertContains(result,response['X-Request-ID'])
        self.assertContains(result,'503')
        self.assertNotContains(result,'PRIVATE_QUERY')
        self.assertNotContains(result,self.secret)
        self.assertNotContains(result,self.key.key_hash)

    def test_search_and_csv_are_owner_scoped(self):
        own=UsageLog.objects.create(api_key=self.key,request_id=uuid.uuid4(),endpoint='/api/v1/search/',status_code=400,latency_ms=12)
        other=UsageLog.objects.create(api_key=self.other_key,request_id=uuid.uuid4(),endpoint='/api/v1/search/',status_code=500)
        self.client.force_login(self.user)
        for filters in [{'q':str(own.request_id)},{'request_id':str(own.request_id)},{'q':'production'},{'q':'search','status':'client_error'}]:
            response=self.client.get('/usage-logs/',filters)
            self.assertEqual(list(response.context['logs']),[own])
        for endpoint in ['/usage-logs/','/usage-logs/export/']:
            response=self.client.get(endpoint,{'request_id':str(other.request_id)})
            if endpoint == '/usage-logs/':
                self.assertEqual(len(response.context['logs']),0)
            else:
                self.assertNotContains(response,str(other.request_id))
            self.assertNotContains(response,'Other private key')

    def test_status_date_filters_and_legacy_rows(self):
        legacy=UsageLog.objects.create(api_key=self.key,endpoint='/api/v1/usage/',status_code=200)
        UsageLog.objects.create(api_key=self.key,endpoint='/api/v1/search/',status_code=500,request_id=uuid.uuid4())
        self.client.force_login(self.user)
        today=timezone.localdate().isoformat()
        # Normalize the legacy OS-created date just as the request middleware does.
        UsageLog.objects.update(date=timezone.localdate())
        response=self.client.get('/usage-logs/',{'status':'success','date_from':today,'date_to':today})
        self.assertEqual(list(response.context['logs']),[legacy])
        self.assertContains(response,'Legacy request')
        self.assertEqual(response['Cache-Control'],'private, no-store')

    def test_invalid_filters_show_errors_and_export_rejects_them(self):
        self.client.force_login(self.user)
        for params in [{'request_id':'invalid'},{'date_from':'bad'},{'date_from':'2026-12-31','date_to':'2026-01-01'},{'status':'invalid'}]:
            response=self.client.get('/usage-logs/',params)
            self.assertTrue(response.context['filter_form'].errors)
            self.assertEqual(len(response.context['logs']),0)
            self.assertEqual(self.client.get('/usage-logs/export/',params).status_code,400)

    def test_filtered_csv_matches_table_and_preserves_old_columns(self):
        own=UsageLog.objects.create(api_key=self.key,request_id=uuid.uuid4(),endpoint='/api/v1/usage/',status_code=200,latency_ms=0)
        UsageLog.objects.create(api_key=self.key,endpoint='/api/v1/search/',status_code=400)
        self.client.force_login(self.user)
        response=self.client.get('/usage-logs/export/',{'status':'success'})
        rows=list(csv.reader(io.StringIO(response.content.decode())))
        self.assertEqual(rows[0],['timestamp','key','method','endpoint','status','latency_ms','request_id'])
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[1][-1],str(own.request_id))
        self.assertEqual(rows[1][-2],'0')
        self.assertEqual(response['Cache-Control'],'private, no-store')

    def test_paginated_logs_keep_filters_and_guests_cannot_read(self):
        self.assertEqual(self.client.get('/usage-logs/').status_code,302)
        self.assertEqual(self.client.get('/usage-logs/export/').status_code,302)
        UsageLog.objects.bulk_create([UsageLog(api_key=self.key,request_id=uuid.uuid4(),endpoint='/api/v1/search/') for _ in range(51)])
        self.client.force_login(self.user)
        response=self.client.get('/usage-logs/',{'q':'search','page':2})
        self.assertEqual(len(response.context['logs']),1)
        self.assertEqual(response.context['filter_query'],'q=search')
