"""Exact supplemental scope and live zero-credit admission. File version: 1.0.0."""
import copy,importlib.util,json,os,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
FILE_VERSION='1.0.0'
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'apps/main'))
import joat_reference_supplement as s
import joat_gpu_quota_panel as quota
import joat_provider_quota as provider

class ReferenceSupplementTests(unittest.TestCase):
    def setUp(self):
        self.mission=json.loads((ROOT/'tests/fixtures/style001_mission.json').read_text())
        self.request=s.registry()['requests'][0]['request']
        self.payload={'requests':[self.request],'additional_reference_scope':{'registry_sha256':s.REGISTRY_SHA256,'original_mission_changed':False},
          'spending_approval':{'schema':'joat.included_quota_only_execution.v1','file_version':'1.0.0','owner':'Dezz-9-10',
          'request_id':self.request['request_id'],'request_fingerprint':s.digest(self.request),'maximum_usd':0,
          'maximum_attempts':1,'gpu_seconds_ceiling':600,'gpu_size':'large','credit_purchase_authorized':False}}

    def test_exact_supplement_preserves_original_one_reference_scope(self):
        original=copy.deepcopy(self.mission)
        self.assertEqual(s.authorize(self.mission,self.payload),[self.request])
        self.assertEqual(self.mission,original)
        self.assertEqual(self.mission['reference_preparation']['maximum_candidate_requests'],1)

    def test_changed_scene_original_mission_or_scope_rejected(self):
        for change in ('prompt','mission','scope','budget'):
            mission=copy.deepcopy(self.mission);payload=copy.deepcopy(self.payload)
            if change=='prompt':payload['requests'][0]['prompt']+=' change scene'
            elif change=='mission':mission['target_duration_seconds']=60
            elif change=='scope':payload['additional_reference_scope']['original_mission_changed']=True
            else:payload['spending_approval']['maximum_usd']=1
            with self.assertRaises(ValueError):s.authorize(mission,payload)

    def test_old_authorizer_accepts_supplement_without_expanding_original_allowance(self):
        import joat_canonical_project_references as original
        self.assertEqual(original.authorize(self.mission,self.payload),[self.request])
        with self.assertRaises(ValueError):original.authorize(self.mission,{'requests':[self.request],'spending_approval':self.payload['spending_approval']})

    def test_one_candidate_at_a_time(self):
        payload=copy.deepcopy(self.payload);payload['requests']*=2
        with self.assertRaises(ValueError):s.authorize(self.mission,payload)

    def test_live_provider_denial_or_low_allowance_does_not_reserve(self):
        with tempfile.TemporaryDirectory() as d,patch.object(quota,'ROOT',Path(d)),patch.object(provider,'read_quota') as read:
            for result in ({'provider_live_balance':False},{'provider_live_balance':True,'remaining_seconds':719}):
                read.return_value=result
                with self.assertRaises(ValueError):s.reserve(self.request,self.payload)
            self.assertFalse(list(Path(d).rglob('reservation.json')))

    def test_live_reservations_are_idempotent_and_pending_ceiling_is_not_reused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);managed=types.ModuleType('joat_managed_generation');managed.ROOT=root/'studio'
            with patch.object(quota,'ROOT',root/'quota'),patch.object(provider,'read_quota',return_value={'provider_live_balance':True,'remaining_seconds':1200}),patch.dict(sys.modules,{'joat_managed_generation':managed}):
                s.reserve(self.request,self.payload)
                with self.assertRaises(ValueError):s.reserve(self.request,self.payload)
                another=s.registry()['requests'][1]['request']
                with self.assertRaisesRegex(ValueError,'headroom'):s.reserve(another,self.payload)
                s.settle(self.request,{'sha256':'a'*64})
                s.reserve(another,self.payload)
                self.assertEqual(len(list((root/'quota').rglob('reservation.json'))),2)

if __name__=='__main__':unittest.main()
