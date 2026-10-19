"""Locked portrait graphics preserve earlier authored plan compatibility. Version1.0.0."""
import copy,importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('style001_native_graphics',ROOT/'apps/main/joat_authored_graphics.py');graphics=importlib.util.module_from_spec(spec);spec.loader.exec_module(graphics)
class Tests(unittest.TestCase):
 def plan(self):
  p={'schema':'joat.authored_graphics_plan.v1','file_version':'1.0.1','project_id':'PROJECT-OTU-STYLE001-90S-001','shot_id':'SHOT-012','mission_fingerprint':'2a881aa9651cd9058fd3f9ddaf199f1c2cbfc849b82caf511b1bcd661921868d','duration_seconds':6,'title':'A simpler way to get booked.','subtitle':'Customer, calendar, confirmation and business workflow','rows':[['Appointments confirmed','Customer receives confirmation',True],['Reminders sent','Appointment reminder scheduled',True],['Customers informed','Business dashboard updated',True]],'mode':'style001_workflow','illustrative':True}
  p['plan_fingerprint']=graphics.digest(p);return p
 def test_portrait_scene_scope_and_visible_labels_cannot_be_silently_replaced(self):
  self.assertEqual(graphics.validate(self.plan())['shot_id'],'SHOT-012')
  for key,value in [('title','Unrelated promotion'),('duration_seconds',5),('shot_id','SHOT-013'),('project_id','PROJECT-OTHER')]:
   p=self.plan();p[key]=value;p['plan_fingerprint']=graphics.digest({k:v for k,v in p.items() if k!='plan_fingerprint'})
   with self.assertRaises(ValueError):graphics.validate(p)
 def test_legacy_landscape_plan_stays_valid_without_new_data_version(self):
  p=self.plan();p.update(file_version='1.0.0',project_id='PROJECT-OLD',shot_id='SHOT-001',mode='booking',duration_seconds=6,title='Book an appointment')
  p['plan_fingerprint']=graphics.digest({k:v for k,v in p.items() if k!='plan_fingerprint'})
  self.assertEqual(graphics.validate(p)['file_version'],'1.0.0')
