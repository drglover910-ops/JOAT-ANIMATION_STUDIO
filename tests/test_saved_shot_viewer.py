"""Saved media cannot cross projects, change bytes or grant execution. Version1.0.0."""
import sys,json,tempfile,hashlib,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'apps/main'))
import joat_film_asset_viewer as viewer
class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)/'joat-studio';self.project=viewer.PROJECT;self.identifier='e'*32;self.base=self.root/'remote-generation/requests'/self.identifier;self.art=self.base/'artifacts';self.art.mkdir(parents=True)
  self.source={'production_ready':True,'generation_job':{'project_context':{'project_id':self.project,'shot_id':'SHOT-010','scene_id':'SCENE-005'}}};self.source['generation_job']['job_fingerprint']=viewer.m.digest(self.source['generation_job']);self.source['packet_fingerprint']=viewer.m.digest(self.source)
  self.video=self.art/'output.mp4';self.video.write_bytes(b'original native candidate bytes');self.sha=viewer.m.file_hash(self.video)
  self.result=dict(schema='joat.generation_result.v1',source_job_fingerprint=self.source['generation_job']['job_fingerprint'],status='completed',media_rendered=True,qc_approved=False,downstream_handoff=dict(ready_for_qc=True,ready_for_post=False,post_requires_qc_pass=True),media_evidence=dict(sha256=self.sha));self.result['result_fingerprint']=viewer.m.digest(self.result)
  self.write(self.art/'source_supervisor_packet.json',self.source);self.write(self.art/'generation_result.json',self.result);self.write(self.base/'request.json',{'project_id':self.project});self.write(self.base/'receipt.json',{'status':'completed','source_job_fingerprint':self.source['generation_job']['job_fingerprint']})
  self.index={'schema':'joat.remote_artifact_index.v1','result_status':'completed','source_job_fingerprint':self.source['generation_job']['job_fingerprint'],'files':[dict(filename=n,bucket_path='joat-studio/remote-generation/requests/'+self.identifier+'/artifacts/'+n,sha256=viewer.m.file_hash(self.art/n),size_bytes=(self.art/n).stat().st_size) for n in ['output.mp4','generation_result.json','source_supervisor_packet.json']]};self.write(self.base/'artifact_index.json',self.index)
 def write(self,p,v):p.write_text(json.dumps(v))
 def test_exact_saved_source_and_picture_are_returned_without_approval(self):
  p,e,s=viewer.verified_media(self.project,'native:'+self.identifier,self.root);self.assertEqual(p,self.video);self.assertEqual(s,'SHOT-010');self.assertFalse(e['qc_approved'])
 def test_other_project_and_arbitrary_server_path_cannot_be_loaded(self):
  for project,key in [('PROJECT-OTHER','native:'+self.identifier),(self.project,'../../secrets'),('../secrets','native:'+self.identifier)]:
   with self.assertRaises(ValueError):viewer.verified_media(project,key,self.root)
 def test_tampered_video_and_redirected_index_are_rejected(self):
  self.video.write_bytes(b'altered native candidate bytes')
  with self.assertRaises(ValueError):viewer.verified_media(self.project,'native:'+self.identifier,self.root)
  self.video.write_bytes(b'original native candidate bytes');self.index['files'][0]['bucket_path']='joat-studio/other-project/private.mp4';self.write(self.base/'artifact_index.json',self.index)
  with self.assertRaises(ValueError):viewer.verified_media(self.project,'native:'+self.identifier,self.root)
 def test_nonowner_is_rejected_before_any_storage_read(self):
  with patch.object(viewer.m,'owner_token',side_effect=ValueError('not-owner')),patch.object(viewer,'verified_media') as read:
   with self.assertRaises(ValueError):viewer.watch(self.project,'native:'+self.identifier,None,None,None)
   read.assert_not_called()
