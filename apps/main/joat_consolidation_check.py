"""One explicitly staged native CPU migration qualification. Embedded file version 1.0.0.
Uses existing owner/service/signing bindings, creates only migration test candidates.
Never runs a GPU or supplies creative/final approval. No automatic retry.
"""
FILE_VERSION='1.0.0'
import hashlib,json,os,re,tempfile,threading,time,uuid
from pathlib import Path

def stable(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def run(identifier,expected):
 stage='preflight';directory=Path('/studio/joat-studio/migrations/cpu-consolidation')/identifier
 receipt=dict(schema='joat.native_cpu_consolidation_check.v1',file_version=FILE_VERSION,check_id=identifier,expected_manifest_fingerprint=expected,gpu_called=False,creative_approval_created=False,existing_film_assets_changed=False,automatic_retry=False,steps=[])
 def record(name,**data):
  receipt['steps'].append(dict(step=name,**data));print('JOAT_CONSOLIDATION_CHECK '+stable(dict(check_id=identifier,stage=name,status='passed')),flush=True)
 try:
  if os.environ.get('SPACE_ID')!='Dezz-9-10/J.O.A.T.-Main-Assistant-Bot' or os.environ.get('JOAT_STUDIO_CONSOLIDATED_ENABLED','').lower()!='true':raise ValueError('Run from the enabled native Main Assistant.')
  directory.mkdir(parents=True,exist_ok=False)
  from huggingface_hub import HfApi
  token=os.environ.get('JOAT_SPECIALIST_TOKEN','')
  if not token or HfApi(token=token).whoami().get('name')!='Dezz-9-10':raise ValueError('Existing native service credential must verify as owner.')
  record('native_owner_credential_verified')
  from joat_runtime_client import NativeClient,HOST,RemoteDepartmentClient
  from gradio_client import handle_file
  import joat_executive_handoff as handoff
  handoff.require_studio_mount()
  controller=NativeClient(HOST,token=token,oauth_token=token,verbose=False,httpx_kwargs={'params':{'all_endpoints':'true'}})
  try:
   stage='controller_status';status=controller.predict(api_name='/cpu_consolidation_status')
   if status.get('manifest_fingerprint')!=expected or status.get('enabled') is not True or status.get('gpu_hold') is not True or status.get('department_count')!=20:raise ValueError('Exact consolidated deployment and GPU hold required.')
   record('controller_manifest_verified',status=status)
  finally:controller.close()
  stage='signed_native_handoff';project='PROJECT-CONSOLIDATION-'+identifier[:12].upper();plan=handoff.prepare(project,'character',dict(cid='CHAR-001',task='scene'))
  preview=handoff.check_signed_preview(plan)
  if preview.get('status')!='validated_preview_only':raise ValueError('Native signed preview failed.')
  signed=handoff.execute(plan,True)
  if signed.get('status')!='department_api_returned' or signed['department_artifact'].get('character_id')!='CHAR-001' or signed['department_artifact'].get('identity_locked') is not True:raise ValueError('Native signed department handoff failed.')
  (directory/'executive_handoff_receipt.json').write_text(json.dumps(signed,indent=2));record('actual_main_signed_dispatch',receipt_fingerprint=signed['receipt_fingerprint'],logical_role='character',creative_approved=False)
  stage='native_acceptance';counts=[]
  from joat_local_cpu import ROLES
  for role in ROLES:
   if role=='narration':continue
   endpoint='/test' if role=='character' else '/run_tests_ui' if role=='director' else '/acceptance_tests' if role in ('voice_dialogue','browser','hugging_face') else '/tests_ui'
   client=RemoteDepartmentClient(role,token=token,oauth_token=token,verbose=False)
   try:
    value=client.predict(api_name=endpoint)
    if isinstance(value,str):value=json.loads(value)
    if value.get('all_passed',value.get('passed',False)) is not True:raise ValueError('Original department acceptance failed: '+role)
    counts.append(dict(role=role,tests=value.get('test_count',len(value.get('tests',[])))))
   finally:client.close()
  record('all_original_department_acceptance',departments=counts)
  stage='authored_graphics_candidate'
  plan=dict(schema='joat.authored_graphics_plan.v1',file_version='1.0.0',project_id=project,shot_id='SHOT-001',mission_fingerprint=expected,duration_seconds=1,title='CPU migration check',subtitle='Private test candidate; not film production',rows=[['Booking','Illustrative migration fixture',True]],mode='booking',illustrative=True)
  plan['plan_fingerprint']=hashlib.sha256(stable(plan).encode()).hexdigest()
  graphics=RemoteDepartmentClient('titles_graphics',token=token,oauth_token=token,download_files=str(directory/'downloads'),verbose=False)
  try:candidate,video,report=graphics.predict(stable(plan),True,api_name='/create_authored_graphics')
  finally:graphics.close()
  if sha(video)!=candidate['media_evidence']['sha256'] or candidate['media_evidence']['decoded_frames']!=24:raise ValueError('Native authored media hash/full decode failed.')
  record('actual_cpu_media_download_verified',sha256=sha(video),decoded_frames=24)
  stage='independent_qc_rework'
  qc=RemoteDepartmentClient('quality_control',token=token,oauth_token=token,download_files=str(directory/'downloads'),verbose=False)
  try:review,qcfile=qc.predict(handle_file(report),handle_file(video),[],'Migration fixture; creative review intentionally not approved.',api_name='/inspect_authored_graphics')
  finally:qc.close()
  if review.get('decision')!='REWORK' or review.get('post_production_authorized') is not False:raise ValueError('Independent QC improperly approved unchecked requirements.')
  record('independent_qc_retained',decision=review['decision'],qc_fingerprint=review['qc_fingerprint'])
  stage='cpu_narration'
  import av
  voice=RemoteDepartmentClient('narration',token=token,oauth_token=token,download_files=str(directory/'downloads'),verbose=False)
  try:
   voices=[]
   for character,text in [('NARRATOR','Your next customer should not have to wait.'),('CHAR-002','I need my evenings back.'),('CHAR-001','Make it easy for customers to book.')]:
    start=time.monotonic();file=voice.predict(text,character,api_name='/generate')
    with av.open(file) as container:
     stream=container.streams.audio[0];samples=sum(frame.samples for frame in container.decode(stream));rate=stream.rate
    if not samples or rate!=24000:raise ValueError('CPU voice full decode failed.')
    voices.append(dict(character_id=character,sha256=sha(file),samples=samples,sample_rate=rate,elapsed_seconds=round(time.monotonic()-start,3),auditory_qc_approved=False))
  finally:voice.close()
  record('native_cpu_voice_qualification',voices=voices,gpu_called=False)
  receipt.update(status='passed',all_native_checks_passed=True)
 except Exception as exc:
  receipt.update(status='failed_or_unknown',failed_stage=stage,error_type=type(exc).__name__,automatic_retry=False)
 finally:
  if directory.is_dir():
   receipt['receipt_fingerprint']=hashlib.sha256(stable(receipt).encode()).hexdigest();target=directory/'receipt.json'
   if not target.exists():target.write_text(json.dumps(receipt,indent=2))
  print('JOAT_CONSOLIDATION_TERMINAL '+stable(receipt),flush=True)

def start_consolidation_checks():
 for name,value in list(os.environ.items()):
  if not name.startswith('JOAT_CONSOLIDATION_CHECK_'):continue
  identifier=name.removeprefix('JOAT_CONSOLIDATION_CHECK_')
  if not re.fullmatch('[a-f0-9]{32}',identifier) or not re.fullmatch('[a-f0-9]{64}',value):continue
  directory=Path('/studio/joat-studio/migrations/cpu-consolidation')/identifier
  if directory.exists():continue
  threading.Thread(target=run,args=(identifier,value),daemon=True,name='joat-cpu-migration-check').start()
