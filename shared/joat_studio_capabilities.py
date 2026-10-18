"""Shared pinned production knowledge and fail-closed feature checks. File version1.0.3.
CPU planning only. Never grants creative approval, changes settings or submits inference.
"""
FILE_VERSION='1.0.3'
import copy,hashlib,json,math,re
from pathlib import Path
ROOT=Path(__file__).parent

def stable(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def digest(v):return hashlib.sha256(stable(v).encode()).hexdigest()
def registry():
 value=json.loads((ROOT/'joat_studio_capabilities.json').read_text());core=dict(value);given=core.pop('registry_fingerprint',None)
 if digest(core)!=given or value.get('schema')!='joat.studio_capability_registry.v1':raise ValueError('Studio capability registry integrity failed.')
 return value

def catalogue(query=''):
 value=registry();query=str(query or '').strip().lower()
 return dict(schema='joat.studio_capability_catalogue.v1',file_version=FILE_VERSION,registry_fingerprint=value['registry_fingerprint'],renderer_space=value['renderer_space'],renderer_revision=value['renderer_revision'],features=[f for f in value['features'] if not query or query in stable(f).lower()],techniques=value['techniques'],policy=value['production_policy'],project_templates=value['project_templates'],gpu_called=False,execution_authorized=False)

def context(compact=False):
 r=registry();intro='STUDIO TOOL KNOWLEDGE — pinned registry '+r['registry_fingerprint']+'. Current renderer app '+r['renderer_app_version']+'. This is capability evidence, never execution or creative approval. '
 rules=('Preserve locked references, identity, wardrobe, locations, style and exact scripts. Reuse approved assets and completed audio/graphics. GPU quota is shared; CPU narration, joining and supplied soundtrack work save quota. Each Scene Builder clip and writer/enhancer request can consume separate GPU time. No feature guarantees exact identity, lip sync or lyrics. Standalone text-only input is not exposed here. Separate identity portrait cannot combine with motion control or internal scene chaining. MSR is hidden. Advanced features need specific qualification; do not activate them automatically. Existing independent QC, owner authorization and GPU hold remain authoritative. Long dramas need segmented continuity/assembly qualification; current timeline assembly accepts at most32 source clips per run. A private server is a future deployment target, not an existing service or purchase authorization.')
 if compact:return intro+rules
 lines=['\n'+f['id']+' — '+f['name']+': '+f['status']+'; '+f['description'][:130]+'; '+f['limits'][:150] for f in r['features']]
 return intro+rules+''.join(lines)+'\nCapabilities are available through studio_capability_catalogue and plan_studio_capabilities (CPU-only). Use approved Director plans and the existing supervised render route for execution; never treat a planning reply as a submitted render. Native UI Economy+ default is separate from our fixed approved composed-I2V settings.'

def plan_project(request):
 if not isinstance(request,dict) or set(request)-{'project_id','intent','format','locks','required_features','clip_count'}:raise ValueError('Use the exact capability planning fields.')
 if len(stable(request).encode())>128*1024:raise ValueError('Capability planning input exceeds128KiB.')
 project=request.get('project_id','');intent=request.get('intent','')
 if not isinstance(project,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}',project):raise ValueError('A valid project ID is required.')
 if not isinstance(intent,str) or not intent.strip() or len(intent)>16000:raise ValueError('Use1–16000 characters describing the intended production.')
 r=registry();format=request.get('format','product_commercial')
 if format not in r['content_formats']:raise ValueError('Unsupported production format.')
 locks=request.get('locks',{})
 if not isinstance(locks,dict) or set(locks)-{'art_style','characters','wardrobe','locations','aspect_ratio','script_fingerprint','mission_fingerprint'}:raise ValueError('Use named creative locks, not renderer overrides or credentials.')
 # JSON-compatible copy is evidence only; it cannot replace actual approved packets.
 if any(not isinstance(v,(str,list,dict)) for v in locks.values()):raise ValueError('Invalid creative lock value.')
 required=request.get('required_features',[])
 if not isinstance(required,list) or len(required)>30 or any(not isinstance(v,str) for v in required) or len(set(required))!=len(required):raise ValueError('Use distinct known capability IDs.')
 known={f['id']:f for f in r['features']}
 if set(required)-set(known):raise ValueError('Unknown capability ID; no fallback or automatic activation.')
 clips=request.get('clip_count')
 if clips is not None and (type(clips) is not int or not 1<=clips<=1000):raise ValueError('Use a known shot count from1–1000, or omit it.')
 issues=[]
 if format=='long_drama' or (clips is not None and clips>32):issues.append(dict(code='segmented_long_form_qualification_required',detail='Existing timeline assembly supports at most32 source clips per run; longer productions need a reviewed segmented workflow and continuity qualification.'))
 for id in required:
  f=known[id]
  if not f['automatic_activation_allowed']:issues.append(dict(code='qualification_or_separate_workflow_required',feature=id,status=f['status'],detail=f['limits']))
 if 'identity_portrait' in required and ('motion_control' in required or 'experiments' in required):issues.append(dict(code='incompatible_identity_sampling_combination',detail='Separate identity portrait and motion/internal scene-chain sampling cannot be combined in this path.'))
 suggestions=['image_to_video','camera_prompting','native_audio','cpu_join','soundtrack_mixer','diagnostics','export']
 if re.search(r'\b(continue|continuation|extend|ending pose|end frame)\b',intent,re.I):suggestions.append('continuation' if re.search('continu|extend',intent,re.I) else 'end_keyframe')
 stages=['reuse approved canonical/project references, finished voices and graphics','Director locks story, shot actions, camera, wardrobe, locations and style','validate exact source packet, composed first frame and renderer plan','generate only missing approved footage after quota and owner gates','independent technical, identity, performance and audio QC','CPU editorial, sound, graphics, color and timeline assembly','owner final master review, durable delivery and readback']
 value=dict(schema='joat.studio_capability_plan.v1',file_version=FILE_VERSION,project_id=project,format=format,intent=intent,registry_fingerprint=r['registry_fingerprint'],renderer_revision=r['renderer_revision'],creative_lock_snapshot=copy.deepcopy(locks),request_fingerprint=digest(request),required_features=required,suggested_features=suggestions,qualification_requirements=issues,stages=stages,cost_policy=dict(prefer_existing_media=True,narration='qualified CPU candidate provider; auditory QC still required',graphics_and_post='CPU',new_actor_motion_and_reference_images='GPU inference',known_clip_count=clips,scene_builder_gpu_calls_if_used=clips if clips is not None else None,reservation_is_not_actual_usage=True,writer_or_enhancer_calls_not_required_for_already_approved_script=True),status='needs_feature_qualification' if issues else 'planning_only_ready_for_existing_approval_workflow',locked_decisions_modified=False,creative_approved=False,execution_authorized=False,gpu_called=False,automatic_retry=False,private_server_status=r['private_deployment']['status'])
 value['plan_fingerprint']=digest(value);return value

def guard_render_parameters(parameters):
 if not isinstance(parameters,dict):raise ValueError('Exact renderer parameters required.')
 registry() # Source knowledge must verify before any inference authorization can proceed.
 p=parameters;advanced=[]
 if p.get('identity_ref_image'):advanced.append('identity_portrait')
 if p.get('input_mode','single image (i2v)')!='single image (i2v)':advanced.append('msr')
 if p.get('motion_control_type','off')!='off':advanced.append('motion_control')
 for field,id in [('kf_last_image','end_keyframe'),('kf_mid_enabled','mid_keyframes'),('audio_ref_enabled','audio_reference'),('user_loras_text','custom_loras'),('prompt_relay_enabled','experiments'),('scene_chain_enabled','experiments'),('kv_enabled','experiments')]:
  if p.get(field):advanced.append(id)
 if p.get('identity_ref_image') and (p.get('motion_control_type','off')!='off' or p.get('scene_chain_enabled')):raise ValueError('Capability policy: identity portrait conflicts with this motion/internal-chain path. No inference submitted.')
 if advanced:raise ValueError('Capability policy: unqualified render features require a reviewed integration before production: '+', '.join(sorted(set(advanced)))+'. No inference submitted.')
 for field in ('seconds','max_width','max_height','gen_budget'):
  value=p.get(field)
  if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError('Finite explicit render setting required: '+field)
 if any(type(p[k]) is not int or p[k]<=0 or p[k]%32 for k in ('max_width','max_height')):raise ValueError('Reviewed output dimensions must be positive integers on the32-pixel model grid.')
 if not 0<p['seconds']<=40:raise ValueError('Reviewed duration must remain within40seconds.')
 if p['gen_budget'] != int(p['gen_budget']) or not 45 <= p['gen_budget'] <= 600:raise ValueError('Explicit integer GPU allocation must be45–600seconds; exact plan and owner grant remain required.')
 return dict(schema='joat.capability_render_guard.v1',file_version=FILE_VERSION,registry_fingerprint=registry()['registry_fingerprint'],status='compatible_with_existing_controlled_lane',gpu_called=False,creative_approval_granted=False)

def observations(root=Path('/studio/joat-studio'),limit=20):
 """Read existing durable results as a growing evidence library; never self-certify QC.
 No new index writes or media inference. Hash/technical observations are not visual PASS.
 """
 if type(limit) is not int or not 1<=limit<=50:raise ValueError('Use1–50 observations.')
 base=Path(root)/'generation-attempts';items=[];scanned=0;bytes_hashed=0
 if base.is_dir() and not base.is_symlink():
  import itertools
  for file in itertools.islice(base.rglob('result.json'),1000):
   scanned+=1
   if any(p.is_symlink() for p in (file,*file.parents)) or not file.resolve().is_relative_to(Path(root).resolve()) or file.stat().st_size>2*1024**2:continue
   try:
    result=json.loads(file.read_text());core=dict(result);given=core.pop('result_fingerprint',None)
    if not given or digest(core)!=given:continue
    evidence=result.get('media_evidence',{});media=file.parent/'output.mp4'
    if result.get('media_rendered') is not True or result.get('status')!='completed' or evidence.get('video_fully_decoded') is not True or not media.is_file() or media.is_symlink() or media.stat().st_size>100*1024**2:continue
    if bytes_hashed+media.stat().st_size>500*1024**2:break
    h=hashlib.sha256()
    with media.open('rb') as f:
     for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    bytes_hashed+=media.stat().st_size
    if h.hexdigest()!=evidence.get('sha256'):continue
    params=result.get('render_provenance',{}).get('parameters',{})
    items.append(dict(result_fingerprint=given,source_job_fingerprint=result.get('source_job_fingerprint'),media_sha256=evidence['sha256'],renderer_revision=result.get('render_provenance',{}).get('renderer_revision'),technical_observation=dict(width=evidence.get('width'),height=evidence.get('height'),duration_seconds=evidence.get('duration_seconds'),fps=evidence.get('fps')),settings_observation={k:params.get(k) for k in ('input_mode','skip_refine','seconds','max_width','max_height','gen_budget')},status='verified_saved_technical_observation',creative_qc_granted=False,automatic_technique_qualification=False))
    if len(items)>=limit:break
   except (OSError,ValueError,TypeError):continue
 return dict(schema='joat.studio_technique_observations.v1',file_version=FILE_VERSION,registry_fingerprint=registry()['registry_fingerprint'],records_scanned=scanned,observations=items,source='existing durable generation results; no duplicate index',media_redecoded_by_index=False,gpu_called=False,creative_approval_granted=False)
