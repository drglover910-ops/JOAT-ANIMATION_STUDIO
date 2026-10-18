"""Persist exact owner visual approval without canonical or production QC authority.
Embedded file version 1.0.1. Main writer only; original candidate remains immutable.
"""
FILE_VERSION='1.0.1'
import re
from PIL import Image
import joat_managed_generation as m

def save(project,mission,payload):
 required={'asset_key','request_id','image_sha256','owner_approval'}
 if set(payload) not in (required,required|{'delegated_review'}):raise ValueError('Exact frame approval fields required.')
 delegation=payload.get('delegated_review')
 if delegation is not None:
  fields={'schema','file_version','owner','owner_statement','project_id','scope','reviewer','decision','reviewed_image_sha256','review_notes','final_film_approval_delegated','spending_authorized'}
  if not isinstance(delegation,dict) or set(delegation)!=fields or delegation['schema']!='joat.delegated_still_review.v1' or delegation['file_version']!='1.0.0' or delegation['owner']!=m.OWNER or delegation['project_id']!=project or delegation['scope']!='current_project_scene_stills' or delegation['reviewer']!='Codex' or delegation['decision']!='approved' or delegation['reviewed_image_sha256']!=payload['image_sha256'] or delegation['final_film_approval_delegated'] is not False or delegation['spending_authorized'] is not False or not isinstance(delegation['owner_statement'],str) or not delegation['owner_statement'].strip() or not isinstance(delegation['review_notes'],str) or not delegation['review_notes'].strip():raise ValueError('Exact project-scoped delegated still review required.')
 expected_statement='Approve this frame via delegated scene-still review' if delegation is not None else 'Approve this frame'
 key=payload['asset_key'];identifier=payload['request_id'];approval=payload['owner_approval']
 if not isinstance(key,str) or not re.fullmatch('[A-Z0-9-]{1,96}',key) or not re.fullmatch('[a-f0-9]{32}',identifier):raise ValueError('Invalid source frame identifiers.')
 if not isinstance(approval,dict) or set(approval)!={'owner','approved','owner_statement','approved_at','scope'} or approval['owner']!=m.OWNER or approval['approved'] is not True or approval['scope']!='still_only' or approval['owner_statement']!=expected_statement or not isinstance(approval['approved_at'],str) or not approval['approved_at']:raise ValueError('Explicit exact still approval required.')
 if not re.fullmatch('[a-f0-9]{64}',str(payload['image_sha256'])):raise ValueError('Exact reviewed image hash required.')
 base=m.safe_path(m.ROOT/'production-projects'/m.valid_project(project)/'references'/key/identifier)
 image=m.safe_path(base/'candidate.png');review=m.read_json(m.safe_path(base/'candidate_review.json'));request=review.get('source_request',{})
 if review.get('schema')!='joat.project_reference_candidate.v1' or review.get('kind')!='shot_start_frame' or review.get('project_id')!=project or review.get('request_id')!=identifier or review.get('asset_key')!=key or review.get('plan_fingerprint')!=m.digest(request) or request.get('project_id')!=project or request.get('request_id')!=identifier or request.get('asset_key')!=key:raise ValueError('Source candidate integrity failed.')
 if review.get('owner_visual_approved') is not False or review.get('canonical_registration') is not False or review.get('production_qc_approved') is not False:raise ValueError('Preserve unapproved immutable source evidence.')
 if m.file_hash(image)!=payload['image_sha256'] or review.get('sha256')!=payload['image_sha256'] or image.stat().st_size!=review.get('size_bytes'):raise ValueError('Approval refers to a different image.')
 with Image.open(image) as im:
  im.load()
  if im.format!='PNG' or im.size!=(review.get('width'),review.get('height')):raise ValueError('Source image dimensions/format changed.')
 value=dict(schema='joat.project_frame_visual_approval.v1',file_version=FILE_VERSION,project_id=project,mission_fingerprint=mission,asset_key=key,source_request_id=identifier,image_sha256=payload['image_sha256'],candidate_plan_fingerprint=review['plan_fingerprint'],candidate_review_fingerprint=m.digest(review),image_bucket_path=str(image.relative_to(m.ROOT.parent)),owner_approval=approval,canonical_registration=False,production_qc_approved=False,gpu_called=False)
 if delegation is not None:
  value['delegated_review']=delegation
  value['approval_basis']='Owner-delegated agent scene-still review; owner did not personally perform this image review.'
 value['approval_fingerprint']=m.digest(value);target=base/'owner_visual_approval.json'
 if target.exists():
  if m.read_json(target)!=value:raise ValueError('Conflicting frame approval; original retained.')
 else:
  try:m.write_once(target,value)
  except FileExistsError:
   if m.read_json(target)!=value:raise ValueError('Concurrent conflicting frame approval; original retained.')
 if m.read_json(target)!=value:raise ValueError('Approval readback differs.')
 return dict(status='exact_frame_visual_approval_saved',gpu_called=False,approved_image_sha256=value['image_sha256'],approval_fingerprint=value['approval_fingerprint'],approval_bucket_path=str(target.relative_to(m.ROOT.parent)),production_qc_approved=False,canonical_registration=False)
