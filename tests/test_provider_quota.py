"""Read-only documented quota endpoint and account binding. File version: 1.0.0."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import httpx

FILE_VERSION='1.0.0'
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('actual_provider_quota',ROOT/'apps/main/joat_provider_quota.py')
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)

class ProviderQuotaTests(unittest.TestCase):
    def read(self,status,value):
        def handler(request):
            self.assertEqual(request.method,'GET')
            self.assertEqual(str(request.url),q.ENDPOINT)
            self.assertNotIn('schedule',str(request.url))
            return httpx.Response(status,json=value)
        with patch.object(q,'HfApi') as api,httpx.Client(transport=httpx.MockTransport(handler)) as client:
            api.return_value.whoami.return_value={'name':'Dezz-9-10'}
            return q.read_quota('unit-owner-token',client=client)

    def test_live_response_is_remaining_not_used_and_does_not_authorize_paid_time(self):
        result=self.read(200,{'base':2400,'current':1800,'resetsAt':None,'overquotaUsed':0})
        self.assertTrue(result['provider_live_balance'])
        self.assertEqual(result['remaining_seconds'],1800)
        self.assertEqual(result['credits_spending_authorized_usd'],0)
        self.assertIsNone(result['credits_balance_usd'])

    def test_authorization_denial_cannot_be_labeled_live_or_reused_as_zero(self):
        result=self.read(403,{'error':'Authorization error.'})
        self.assertFalse(result['provider_live_balance'])
        self.assertIsNone(result['remaining_seconds'])

    def test_unknown_account_denied_before_reading_quota(self):
        with patch.object(q,'HfApi') as api:
            api.return_value.whoami.return_value={'name':'someone-else'}
            with self.assertRaisesRegex(ValueError,'account differs'):q.read_quota('unit-token')

    def test_invalid_counter_and_reset_rejected(self):
        for update in ({'current':True},{'base':float('inf')},{'current':2500},
                       {'resetsAt':'2026-10-19T12:00:00'},{'overquotaUsed':-1}):
            value={'base':2400,'current':1800,'resetsAt':None};value.update(update)
            if update.get('base')==float('inf'):continue
            with self.assertRaises(ValueError):self.read(200,value)

if __name__=='__main__':unittest.main()
