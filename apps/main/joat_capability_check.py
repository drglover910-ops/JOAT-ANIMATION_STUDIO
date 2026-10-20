"""Native CPU-only shared knowledge qualification. Embedded file version1.0.5.
Existing owner bindings only; no generation, purchases or creative approval.
"""
FILE_VERSION='1.0.5'
import os,json,hashlib,re,sys,threading
from pathlib import Path

def start_capability_checks():
 for name,value in list(os.environ.items()):
  if not name.startswith('JOAT_CAPABILITY_CHECK_'):continue
  identifier=name.removeprefix('JOAT_CAPABILITY_CHECK_')
  if not re.fullmatch('[a-f0-9]{32}',identifier) or not re.fullmatch('[a-f0-9]{64}',value):continue
  root=Path('/studio/joat-studio/migrations/capabilities')/identifier
  if root.exists():continue
  threading.Thread(target=run,args=(identifier,value,root),daemon=True,name='joat-capability-check').start()

def run(identifier,expected,root):
 receipt=dict(schema='joat.native_capability_check.v1',file_version=FILE_VERSION,check_id=identifier,expected_registry_fingerprint=expected,steps=[],gpu_called=False,provider_inference_called=False,creative_approval_granted=False,automatic_retry=False);stage='native_owner'
 def step(name,**data):receipt['steps'].append(dict(step=name,**data));print('JOAT_CAPABILITY_CHECK '+json.dumps(dict(check_id=identifier,stage=name,status='passed')),flush=True)
 try:
  if os.environ.get('SPACE_ID')!='Dezz-9-10/J.O.A.T.-Main-Assistant-Bot':raise ValueError('Native Main required.')
  root.mkdir(parents=True,exist_ok=False)
  from huggingface_hub import HfApi
  token=os.environ.get('JOAT_SPECIALIST_TOKEN','')
  if not token or HfApi(token=token).whoami().get('name')!='Dezz-9-10':raise ValueError('Native owner binding unavailable.')
  step('native_owner_verified')
  stage='main_registry_and_prompt'
  from joat_studio_capabilities import registry,context,plan_project
  if registry()['registry_fingerprint']!=expected:raise ValueError('Main registry differs from staged revision.')
  main=sys.modules['__main__'];prompt=main.build_system_prompt(dict(domain='studio',selected_bot='Executive',selected_status='ready',live_execution_connected=True),dict(required=True,type='creative',reason='existing approval workflow'))
  if expected not in prompt or 'motion_control' not in prompt:raise ValueError('Actual Main system prompt lacks capability knowledge.')
  step('main_actual_system_prompt_verified')
  from joat_runtime_client import NativeClient,RemoteDepartmentClient,HOST
  stage='controller_pinned_contract'
  from joat_control_contract import create
  controller=create(HOST,token,{'Authorization':'Bearer '+token},False)
  step('authenticated_revision_pinned_controller_contract')
  try:
   stage='controller_knowledge';status=controller.predict(api_name='/cpu_consolidation_status');catalogue=controller.predict('',api_name='/studio_capability_catalogue')
   if status.get('gpu_hold') is not True or status.get('studio_capability_registry_fingerprint')!=expected or catalogue.get('registry_fingerprint')!=expected or len(catalogue.get('features',[]))!=30:raise ValueError('Controller registry/hold mismatch.')
   stage='studio_knowledge_transfer'
   guidance=controller.predict('GPU costs current film checkpoint','director','PROJECT-OTU-STYLE001-90S-001','STYLE001',api_name='/studio_production_knowledge')
   required={'studio-interface-ownership','gpu-accounting-and-routing','style001-finish-checkpoint'}
   if not required<={r['id'] for r in guidance.get('lessons',[])} or guidance.get('execution_authorized') is not False or guidance.get('qc_approved') is not False:raise ValueError('Scoped Studio knowledge transfer not verified.')
   from joat_production_knowledge import retrieve
   for role in ['main','executive','director','generation_worker','quality_control']:
    local=retrieve('GPU costs current film checkpoint',role=role,project_id='PROJECT-OTU-STYLE001-90S-001',style_id='STYLE001')
    if not required<={r['id'] for r in local.get('lessons',[])}:raise ValueError('Main shared guidance incomplete.')
   step('studio_scoped_knowledge_transfer_verified',knowledge_version=guidance['file_version'])
   step('controller_bundle_manifest',manifest_fingerprint=status.get('manifest_fingerprint'))
   stage='planning_constraints';request=dict(project_id='PROJECT-CAPABILITY-CHECK',intent='Plan a scene using existing approved references.',format='short_drama',locks={'art_style':'Match approved references'},required_features=['identity_portrait','motion_control'])
   planned=controller.predict(json.dumps(request),api_name='/plan_studio_capabilities')
   if planned.get('status')!='needs_feature_qualification' or planned.get('execution_authorized') is not False or planned.get('creative_approved') is not False:raise ValueError('Planning granted unsupported authority.')
   step('shared_registry_and_incompatible_feature_plan',registry_fingerprint=expected)
   stage='existing_executive_security'
   for endpoint in ['/acceptance_tests','/dispatch_tests']:
    report=controller.predict(api_name=endpoint)
    if report.get('all_passed') is not True:raise ValueError('Executive native acceptance/security failed.')
   step('native_executive_acceptance_and_signing_preserved')
   stage='owner_evidence';evidence=controller.predict(5,api_name='/studio_technique_evidence')
   if evidence.get('registry_fingerprint')!=expected or evidence.get('creative_approval_granted') is not False:raise ValueError('Evidence library changed approval scope.')
   step('owner_only_existing_evidence_library',observations=len(evidence.get('observations',[])),records_scanned=evidence.get('records_scanned'))
  finally:controller.close()
  stage='native_department_handshake'
  for role in ['director','generation_supervisor','generation_worker','quality_control','delivery_archive']:
   stage='native_department_handshake:'+role
   client=RemoteDepartmentClient(role,token=token,oauth_token=token,verbose=False)
   try:
    desc=client.view_api()
    if desc.get('studio_capability_registry_fingerprint')!=expected:raise ValueError('Department registry handshake failed.')
    knowledge=desc.get('production_knowledge',{})
    if knowledge.get('role')!=role or knowledge.get('execution_authorized') is not False or not any(r.get('id')=='role-'+role for r in knowledge.get('lessons',[])):raise ValueError('Department reviewed knowledge handshake failed.')
   finally:client.close()
  step('native_department_registry_handshakes')
  stage='main_acceptance'
  tests=main.tests_ui()
  if tests.get('all_passed') is not True:
   receipt['failed_acceptance_checks']=[dict(test=x.get('test'),passed=x.get('pass')) for x in tests.get('tests',[]) if x.get('pass') is False]
   raise ValueError('Main acceptance regression failed.')
  step('main_knowledge_and_acceptance',tests=tests.get('test_count',len(tests.get('tests',[]))))
  receipt['status']='passed'
 except Exception as exc:receipt.update(status='failed_or_unknown',failed_stage=stage,error_type=type(exc).__name__)
 finally:
  receipt['receipt_fingerprint']=hashlib.sha256(json.dumps(receipt,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
  if root.is_dir() and not (root/'receipt.json').exists():(root/'receipt.json').write_text(json.dumps(receipt,indent=2))
  print('JOAT_CAPABILITY_TERMINAL '+json.dumps(receipt),flush=True)
