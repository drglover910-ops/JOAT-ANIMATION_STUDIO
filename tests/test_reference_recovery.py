"""Only terminal failures without Reference Lab execution evidence can be reconciled. Version 1.0.0."""
import importlib.util,json,tempfile,types,unittest,sys
from pathlib import Path
from unittest.mock import patch
class Tests(unittest.TestCase):
 def exercise(self,*,remote=False,status='failed_or_unknown'):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);project='PROJECT-TEST';request={'request_id':'a'*32,'asset_key':'SCENE'};task='b'*32
   taskdir=root/'production-projects'/project/'tasks'/task;taskdir.mkdir(parents=True)
   failure={'request_id':task,'status':status,'stage':'frame_SCENE','error_type':'AppError'}
   (taskdir/'receipt.json').write_text(json.dumps(failure))
   folder=root/'gpu-quota'/'live-reference-reservations'/request['request_id'];folder.mkdir(parents=True)
   reservation={'request_id':request['request_id'],'request_fingerprint':'fp'}
   (folder/'reservation.json').write_text(json.dumps(reservation))
   if remote:(root/'production-projects'/project/'references'/'SCENE'/request['request_id']).mkdir(parents=True)
   def write(p,v):p.write_text(json.dumps(v))
   managed=types.SimpleNamespace(ROOT=root,safe_path=lambda p:p,read_json=lambda p:json.loads(p.read_text()))
   quota=types.SimpleNamespace(ROOT=root/'gpu-quota',read=lambda p:json.loads(p.read_text()),seal=lambda v:v,write_once=write)
   supplement=types.SimpleNamespace(registry=lambda:{'project_id':project,'requests':[{'request':request}]},digest=lambda v:'fp')
   with patch.dict(sys.modules,{'joat_managed_generation':managed,'joat_gpu_quota_panel':quota,'joat_reference_supplement':supplement}):
    spec=importlib.util.spec_from_file_location('recovery_test',Path(__file__).resolve().parents[1]/'apps/main/joat_reference_recovery.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    payload={'failed_task_id':task,'reference_request_id':request['request_id']}
    if remote or status!='failed_or_unknown':
     with self.assertRaises(ValueError):module.release(project,payload)
     self.assertTrue((folder/'reservation.json').exists())
    else:
     self.assertEqual(module.release(project,payload)['status'],'pre_gpu_failure_reconciled')
     self.assertFalse((folder/'reservation.json').exists())
     self.assertEqual(json.loads((folder/'pre_gpu_failure_reconciliation.json').read_text())['original_reservation'],reservation)
     self.assertTrue((taskdir/'receipt.json').exists())
     self.assertEqual(module.release(project,payload)['status'],'pre_gpu_failure_already_reconciled')
 def test_terminal_pre_gpu_failure_archived_and_idempotent(self):self.exercise()
 def test_reference_side_evidence_blocks_release(self):self.exercise(remote=True)
 def test_nonterminal_outcome_blocks_release(self):self.exercise(status='pending_or_unknown')
