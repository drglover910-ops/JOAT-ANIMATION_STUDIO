"""Actual capability guard and both Worker entry paths. File version1.0.1."""
import ast,copy,importlib.util,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]/'apps'
spec=importlib.util.spec_from_file_location('joat_studio_capabilities',ROOT/'control/joat_studio_capabilities.py');cap=importlib.util.module_from_spec(spec);spec.loader.exec_module(cap)
PLAN=json.loads((ROOT.parent/'tests/fixtures/verified_opening_plan_v1.0.0.json').read_text())['evidence']['plan']
class ReachedConnection(Exception):pass
class Tests(unittest.TestCase):
 def test_exact420_and_legacy600_pass(self):
  for budget in (420,600,45,420.0):
   p=copy.deepcopy(PLAN['parameters']);p['gen_budget']=budget;self.assertFalse(cap.guard_render_parameters(p)['gpu_called'])
 def test_invalid_ceiling_before_connection(self):
  for budget in (True,False,0,44,601,900,420.5,float('inf'),float('nan'),'420',None):
   p=copy.deepcopy(PLAN['parameters']);p['gen_budget']=budget
   with self.assertRaises(ValueError):cap.guard_render_parameters(p)
 def test_unqualified_features_still_blocked(self):
  for field,value in [('identity_ref_image','image'),('motion_control_type','depth'),('scene_chain_enabled',True),('input_mode','multi-reference (MSR)')]:
   p=copy.deepcopy(PLAN['parameters']);p[field]=value
   with self.assertRaises(ValueError):cap.guard_render_parameters(p)
 def test_both_actual_worker_entrypoints_run_guard(self):
  tree=ast.parse((ROOT/'control/departments/generation_worker/joat_render_bridge.py').read_text())
  for name in ('check_render_connection','_execute_render'):
   fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name==name)
   calls=[]
   def connection():calls.append(True);raise ReachedConnection()
   ns={'prepare_plan':lambda *a:PLAN,'_assert_renderer_connection_ready':connection}
   exec(compile(ast.Module(body=[fn],type_ignores=[]),'<actual-worker>','exec'),ns)
   with patch.dict(sys.modules,{'joat_studio_capabilities':cap}):
    args=(None,{},PLAN,'unused')+(({},) if name=='_execute_render' else ())
    with self.assertRaises(ReachedConnection):ns[name](*args)
    self.assertEqual(calls,[True]);calls.clear()
    bad=copy.deepcopy(PLAN);bad['parameters']['gen_budget']=900;ns['prepare_plan']=lambda *a:bad
    args=(None,{},bad,'unused')+(({},) if name=='_execute_render' else ())
    with self.assertRaises(ValueError):ns[name](*args)
    self.assertEqual(calls,[])
if __name__=='__main__':unittest.main()
