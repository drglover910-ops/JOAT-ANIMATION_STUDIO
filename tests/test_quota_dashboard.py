"""Owner observation provenance, staleness and legacy compatibility. File version: 1.0.0."""
import copy
import importlib.util
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import unittest

FILE_VERSION='1.0.0'
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('actual_quota_panel',ROOT/'apps/main/joat_gpu_quota_panel.py')
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)


class QuotaDashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.report={'schema':'joat.quota_dashboard_report.v1','file_version':'1.0.0',
          'report_id':'a'*32,'owner':'Dezz-9-10','confirmed_at':datetime.now(timezone.utc).isoformat(),
          'display_mode':'used','displayed_minutes':0,'total_minutes':40,'credits_balance_usd':3.68,
          'inference_usage_display':'0.05%','owner_statement':'Owner reports zero out of 40 minutes used and $3.68 credits.'}

    def tearDown(self):self.temp.cleanup()

    def test_zero_used_means_forty_remaining_without_credit_authorization(self):
        saved=q.save_dashboard_report(self.report,self.root);state=q.state(self.root)
        self.assertEqual(saved['remaining_seconds'],2400)
        self.assertEqual(state['credits_balance_usd'],3.68)
        self.assertEqual(state['credits_spending_authorized_usd'],0)
        self.assertEqual(saved['inference_usage_display'],'0.05%')
        self.assertFalse(state['provider_live_balance'])
        self.assertFalse(state['browser_reader_connected'])

    def test_counter_mode_cannot_be_confused_with_remaining(self):
        report=dict(self.report,display_mode='remaining',displayed_minutes=0)
        self.assertEqual(q.save_dashboard_report(report,self.root)['remaining_seconds'],0)

    def test_stale_record_has_no_current_planning_allowance(self):
        report=dict(self.report,confirmed_at=(datetime.now(timezone.utc)-timedelta(minutes=16)).isoformat())
        q.save_dashboard_report(report,self.root);state=q.state(self.root)
        self.assertTrue(state['refresh_required'])
        self.assertIsNone(state['conservative_planning_seconds'])
        self.assertEqual(state['last_owner_confirmation']['remaining_seconds'],2400)

    def test_refresh_does_not_renew_observation_or_create_files(self):
        q.save_dashboard_report(self.report,self.root)
        before={str(p):p.read_bytes() for p in self.root.rglob('*.json')}
        first=q.state(self.root);second=q.state(self.root)
        self.assertEqual(first['last_owner_confirmation'],second['last_owner_confirmation'])
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob('*.json')})

    def test_invalid_values_and_unverified_sources_rejected(self):
        for change in ({'owner':'someone-else'},{'display_mode':'live_api'},{'displayed_minutes':True},
                       {'credits_balance_usd':float('nan')},{'displayed_minutes':41},
                       {'credits_balance_usd':-1},{'report_id':'../escape'}):
            with self.assertRaises(ValueError):q.save_dashboard_report(dict(self.report,**change),self.root)

    def test_report_can_be_reused_by_existing_zero_credit_reservation(self):
        q.save_dashboard_report(self.report,self.root)
        grant={'report_id':self.report['report_id'],'confirmed_at':self.report['confirmed_at'],
               'included_seconds_available':2400,'included_seconds_total':2400,'source':'owner_chat_report',
               'owner_statement':self.report['owner_statement']}
        reservation=q.reserve({'request_id':'b'*32,'gpu_ceiling_seconds':600},grant,self.root)
        self.assertEqual(reservation['paid_spending_authorized_usd'],0)
        self.assertEqual(q.state(self.root)['local_reserved_seconds'],600)

    def test_existing_legacy_record_is_preserved_byte_for_byte(self):
        grant={'report_id':'c'*32,'confirmed_at':self.report['confirmed_at'],'included_seconds_available':600,
               'included_seconds_total':2400,'source':'owner_chat_report','owner_statement':'Owner confirmation.'}
        original=q.save_confirmation(grant,self.root);original['file_version']='1.0.0'
        original=q.seal({k:v for k,v in original.items() if k!='record_fingerprint'})
        file=self.root/'reports'/('c'*32+'.json');file.write_text(json.dumps(original));raw=file.read_bytes()
        self.assertEqual(q.save_confirmation(grant,self.root),original)
        self.assertEqual(file.read_bytes(),raw)

    def test_tampered_evidence_is_rejected_without_assert_dependency(self):
        q.save_dashboard_report(self.report,self.root);file=self.root/'reports'/('a'*32+'.json')
        value=json.loads(file.read_text());value['remaining_seconds']=99999;file.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'integrity'):q.state(self.root)

if __name__=='__main__':unittest.main()
