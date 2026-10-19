"""Explicit model ordering and only reviewed canonical face crops. Version1.0.0."""
import copy,importlib.util,json,tempfile,unittest,sys
from pathlib import Path
from unittest.mock import patch
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'apps/main'))
asset_spec=importlib.util.spec_from_file_location('reference_input_assets',ROOT/'apps/reference/joat_job_assets.py');assets=importlib.util.module_from_spec(asset_spec);asset_spec.loader.exec_module(assets)
spec=importlib.util.spec_from_file_location('reference_source_order',ROOT/'apps/reference/joat_project_reference.py');reference=importlib.util.module_from_spec(spec)
with patch.dict(sys.modules,{'joat_job_assets':assets}):spec.loader.exec_module(reference)
class Tests(unittest.TestCase):
 def request(self):return json.loads((ROOT/'apps/main/joat_style001_reference_supplement.json').read_text())['requests'][-1]['request']
 def test_reviewed_single_view_retains_original_identity_parent_hash(self):
  q=self.request();reference.validate(q)
  self.assertEqual(q['sources'][0]['source_sha256'],'fd27d3bf68dfa6daaf12dbc6421a84c67fedb6656f492672f6f78a0a867f1c1f')
  self.assertNotEqual(q['sources'][0]['source_sha256'],q['sources'][0]['prepared_sha256'])
  self.assertEqual(reference.model_order(q),[2,0,1])
 def test_forged_crop_or_ambiguous_model_order_rejected(self):
  for change in ['crop','prepared_hash','old_protocol','duplicate_order','identity_first']:
   q=self.request()
   if change=='crop':q['sources'][0]['crop_bounds_pixels'][0]+=1
   if change=='prepared_hash':q['sources'][0]['prepared_sha256']='a'*64
   if change=='old_protocol':q['file_version']='1.0.4'
   if change=='duplicate_order':q['model_image_order']=[2,0,0]
   if change=='identity_first':q['model_image_order']=[0,1,2]
   with self.assertRaises(ValueError):reference.validate(q)
 def test_actual_generator_receives_all_images_in_declared_order(self):
  q=self.request();original=[Image.new('RGB',(2,2),color) for color in ['red','green','blue']];seen=[]
  def generate(images,prompt,**kwargs):
   seen.extend(im.getpixel((0,0)) for im in images);return Image.new('RGB',(576,1024))
  with tempfile.TemporaryDirectory() as d,patch.object(reference,'sources',return_value=original):
   review,image,report=reference.run(q,generate,root=Path(d),require_mount=lambda:None)
   self.assertEqual(seen,[(0,0,255),(255,0,0),(0,128,0)])
   self.assertEqual(review['source_request'],q)
   self.assertFalse(review['production_qc_approved'])
