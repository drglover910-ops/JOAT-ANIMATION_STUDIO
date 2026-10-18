"""Owner-reviewed Main→Executive→Supervisor→Worker generation. File version 1.0.14.
Existing renderer/creative locks remain authoritative. No automatic render retries.
"""
FILE_VERSION='1.0.14'
import hashlib,hmac,json,math,os,re,shutil,tempfile,threading,time,uuid
from pathlib import Path
from typing import Optional
import urllib.request
import gradio as gr
from gradio_client import Client
from huggingface_hub import HfApi
OWNER='Dezz-9-10'
SPACES={role:'Dezz-9-10/'+name for role,name in {
 'main':'J.O.A.T.-Main-Assistant-Bot','executive':'J.O.A.T.-Executive-Producer-Bot',
 'supervisor':'J.O.A.T.-Generation-Supervisor-Master','worker':'J.O.A.T.-Generation-Worker-Bot'}.items()}
NEXT={'executive':'supervisor','supervisor':'worker'}
ROOT=Path('/studio/joat-studio');BUCKET='Dezz-9-10/J.O.A.T.-Studio-storage';LOCK=threading.Lock()
PHASES=('prepare','check','execute','status','reuse')


def stable(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def digest(value):return hashlib.sha256(stable(value).encode()).hexdigest()
def verify(value,field):
 if not isinstance(value,dict):raise ValueError('Expected a fingerprinted object.')
 unsigned=dict(value);given=unsigned.pop(field,None)
 if not given or digest(unsigned)!=given:raise ValueError('Invalid '+field)
def read_json(path):
 path=Path(path)
 if not path.is_file() or path.stat().st_size>2*1024*1024:raise ValueError('Missing or oversized packet file.')
 return json.loads(path.read_text())
def file_hash(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def export(value,name):
 p=Path(tempfile.mkdtemp(prefix='joat-managed-'))/name;p.write_text(json.dumps(value,ensure_ascii=False,indent=2));return str(p)
def valid_project(project):
 if not isinstance(project,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}',project):raise ValueError('Invalid project ID.')
 return project


def owner_token(profile,oauth,request):
 token=getattr(oauth,'token',None)
 if not token and request is not None:
  header=request.headers.get('x-hf-authorization','') or request.headers.get('authorization','')
  if header.lower().startswith('bearer '):token=header[7:]
 if not token:raise gr.Error('Owner token unavailable; sign in as Dezz-9-10.')
 # Verify the token itself, including when a browser profile is present.
 try:identity=HfApi(token=token).whoami().get('name')
 except Exception:raise gr.Error('Owner credential could not be verified; no generation request sent.') from None
 if identity!=OWNER:raise gr.Error('Sign in as Dezz-9-10 for managed generation.')
 return token


def mount_check(role):
 if os.environ.get('SPACE_ID')!=SPACES[role]:raise ValueError('Wrong managed-generation runtime.')
 token=os.environ.get('JOAT_SPECIALIST_TOKEN','')
 if not token:raise ValueError('Existing owner credential is required for private studio metadata.')
 metadata_request=urllib.request.Request('https://huggingface.co/api/spaces/'+SPACES[role],headers={'Authorization':'Bearer '+token})
 with urllib.request.urlopen(metadata_request,timeout=30) as response:metadata=json.load(response)
 if not any(v.get('source')==BUCKET and v.get('mountPath')=='/studio' and v.get('readOnly') is False
            for v in metadata.get('runtime',{}).get('volumes',[])) or not Path('/studio').is_dir():
  raise ValueError('Private studio read/write mount is required for generation checkpoints.')


def scope(value,phase):
 if not isinstance(value,dict) or value.get('schema')!='joat.managed_generation_request.v1' or value.get('phase')!=phase:
  raise ValueError('Invalid managed generation request.')
 packet=value.get('packet');verify(packet,'packet_fingerprint');job=packet.get('generation_job');verify(job,'job_fingerprint')
 if packet.get('production_ready') is not True or job.get('job_type')!='video' or job.get('engine')!='ltx':
  raise ValueError('An approved existing LTX Supervisor packet is required.')
 project=valid_project(job.get('project_context',{}).get('project_id'))
 if value.get('project_id')!=project:raise ValueError('Managed request project differs from the approved job.')
 if phase!='prepare':
  plan=value.get('plan')
  if (not isinstance(plan,dict) or digest(plan)!=value.get('plan_fingerprint')
      or plan.get('source_job_fingerprint')!=job['job_fingerprint']
      or plan.get('source_supervisor_fingerprint')!=packet['packet_fingerprint']):
   raise ValueError('Managed request changed the reviewed render plan.')
 if phase=='execute' and value.get('owner_approved') is not True:raise ValueError('Explicit approval of this exact render is required.')
 return packet,job,project


def sign(packet,phase,plan=None,approved=False):
 key=os.environ.get('JOAT_DISPATCH_SIGNING_KEY','')
 if len(key)<32:raise ValueError('Existing Main signing-key binding is unavailable. Do not reset Executive secrets.')
 value={'schema':'joat.managed_generation_request.v1','file_version':FILE_VERSION,'source_bot':'J.O.A.T. Main Assistant Bot',
        'target_bot':'J.O.A.T. Executive Producer Bot','phase':phase,'packet':packet,
        'project_id':packet['generation_job']['project_context']['project_id'],
        'nonce':uuid.uuid4().hex,'issued_at_epoch':time.time(),'owner_approved':approved}
 if plan is not None:value.update(plan=plan,plan_fingerprint=digest(plan))
 scope(value,phase);value['signature']=hmac.new(key.encode(),stable(value).encode(),hashlib.sha256).hexdigest()
 return value


def validate_executive(value,phase):
 scope(value,phase)
 if value.get('source_bot')!='J.O.A.T. Main Assistant Bot' or value.get('target_bot')!='J.O.A.T. Executive Producer Bot':
  raise ValueError('Wrong signed managed-generation source or target.')
 issued=value.get('issued_at_epoch')
 if type(issued) not in (int,float) or not math.isfinite(issued) or abs(time.time()-issued)>300:raise ValueError('Managed signature timestamp expired.')
 if not isinstance(value.get('nonce'),str) or len(value['nonce'])<16:raise ValueError('Unique managed nonce required.')
 key=os.environ.get('JOAT_DISPATCH_SIGNING_KEY','')
 if len(key)<32:raise ValueError('Existing Executive signing key is unavailable.')
 unsigned=dict(value);supplied=unsigned.pop('signature',None)
 expected=hmac.new(key.encode(),stable(unsigned).encode(),hashlib.sha256).hexdigest()
 if not isinstance(supplied,str) or not hmac.compare_digest(expected,supplied):raise ValueError('Managed signature invalid.')


RUNTIME_URLS={
 'main':'https://dezz-9-10-j-o-a-t-main-assistant-bot.hf.space',
 'executive':'https://dezz-9-10-j-o-a-t-executive-producer-bot.hf.space',
 'supervisor':'https://dezz-9-10-j-o-a-t-generation-supervisor-master.hf.space',
 'worker':'https://dezz-9-10-j-o-a-t-generation-worker-bot.hf.space'}

def client_for(role,token,directory):
 transport=os.environ.get('JOAT_SPECIALIST_TOKEN') or token
 if transport!=token:
  try:identity=HfApi(token=transport).whoami().get('name')
  except Exception:raise ValueError('Existing specialist transport credential could not be verified.') from None
  if identity!=OWNER:raise ValueError('Existing specialist transport credential is not the studio owner.')
 # Every incoming caller was independently owner-verified. Main's exact HMAC
 # survives forwarding; each outgoing hop uses its existing scoped service token.
 headers={'Authorization':'Bearer '+transport,'x-hf-authorization':'Bearer '+transport}
 from gradio.context import LocalContext
 incoming=LocalContext.request.get(None)
 delegation=incoming.headers.get('x-ip-token') if incoming is not None else None
 if isinstance(delegation,str) and 0<len(delegation)<=8192:headers['x-ip-token']=delegation
 if role=='executive':
  from joat_control_contract import create
  return create(RUNTIME_URLS[role],transport,headers,directory)
 return Client(RUNTIME_URLS[role],token=transport,oauth_token=transport,headers=headers,verbose=False,download_files=directory)
def proxy(role,phase,value,token,client_factory=client_for):
 directory=tempfile.mkdtemp(prefix='joat-managed-proxy-');client=None
 try:
  from gradio_client.utils import TooManyRequestsError
  try:
   client=client_factory(role,token,directory)
  except TooManyRequestsError:
   # Only SDK construction failed: no submit() has run. One bounded CPU
   # metadata reconnect is safe; never retry a submitted API/GPU request.
   print('JOAT_MANAGED_METADATA_RECONNECT '+stable({'role':role,'phase':phase,'api_submission_made':False,'retry_after_seconds':60,'maximum_reconnections':1}),flush=True)
   time.sleep(60)
   client=client_factory(role,token,directory)
  if phase in ('prepare','check'):client.download_files=False
  return client.submit(stable(value),api_name='/managed_'+phase).result(timeout=3000)
 finally:
  if client:client.close()


def safe_path(path):
 path=Path(path)
 if any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('Checkpoint paths cannot contain symlinks.')
 return path

def write_once(path,value):
 path=safe_path(path);path.parent.mkdir(parents=True,exist_ok=True);safe_path(path)
 raw=(json.dumps(value,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode()
 with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 if path.read_bytes()!=raw:raise ValueError('Checkpoint readback failed.')

def store_media(source,target):
 source=Path(source);target=safe_path(target);target.parent.mkdir(parents=True,exist_ok=True);safe_path(target)
 with source.open('rb') as src,target.open('xb') as dst:
  shutil.copyfileobj(src,dst);dst.flush();os.fsync(dst.fileno())
 if file_hash(source)!=file_hash(target):raise ValueError('Stored media readback failed.')

def cached_delivery(packet,root):
 job=packet['generation_job'];project=valid_project(job['project_context']['project_id'])
 directory=safe_path(Path(root)/'deliveries'/project)
 if not directory.exists():return None
 for file in sorted(directory.glob('*/approved_final_result.json')):
  safe_path(file);result=read_json(file);verify(result,'result_fingerprint')
  if result.get('source_job_fingerprint')!=job['job_fingerprint']:continue
  qc=result.get('final_qc',{});master=file.parent/'JOAT_final_master.mp4';safe_path(master)
  if (result.get('delivery_authorized') is not True or qc.get('decision')!='PASS' or qc.get('reviewer')!=OWNER
      or set(qc.get('checks',{}))!={'picture','audio','titles','continuity'} or not all(v is True for v in qc['checks'].values())):continue
  if result.get('project_context',{}).get('project_id')!=project or not master.is_file():continue
  expected=result.get('final_master',{}).get('sha256')
  if file_hash(master)!=expected or qc.get('asset_sha256')!=expected:raise ValueError('Existing approved archive integrity failed.')
  return result,master
 return None


def attempt_dir(packet,plan,root):
 return safe_path(Path(root)/'generation-attempts'/valid_project(packet['generation_job']['project_context']['project_id'])/
                  packet['generation_job']['job_fingerprint']/digest(plan))

def validate_outcome(result,packet,video=None):
 if not isinstance(result,dict) or result.get('source_job_fingerprint')!=packet['generation_job']['job_fingerprint']:
  raise ValueError('Generation outcome belongs to another job.')
 if result.get('schema')=='joat.generation_result.v1':
  verify(result,'result_fingerprint')
  handoff=result.get('downstream_handoff',{})
  if (result.get('status')!='completed' or result.get('media_rendered') is not True or result.get('qc_approved') is True
      or handoff.get('ready_for_qc') is not True or handoff.get('ready_for_post') is not False
      or handoff.get('post_requires_qc_pass') is not True):
   raise ValueError('Generation cannot claim independent QC or incomplete success.')
  expected=result.get('media_evidence',{}).get('sha256')
  if not expected or not video or file_hash(video)!=expected:raise ValueError('Generation media differs from its evidence.')
 elif result.get('schema')=='joat.render_failure.v1':
  if result.get('status')!='render_failed' or result.get('qc_approved') is True or result.get('automatic_retry') is not False:
   raise ValueError('Invalid failure outcome.')
  expected=(result.get('media_evidence') or {}).get('sha256')
  if video and expected and file_hash(video)!=expected:raise ValueError('Diagnostic media differs from its evidence.')
 else:raise ValueError('Unknown generation outcome schema.')

def existing_attempt(packet,plan,root):
 directory=attempt_dir(packet,plan,root);receipt=directory/'result.json'
 if not receipt.exists():
  return ({'schema':'joat.managed_generation_status.v1','file_version':FILE_VERSION,'status':'pending_or_unknown' if (directory/'reservation.json').exists() else 'not_submitted',
           'gpu_called':None if (directory/'reservation.json').exists() else False,'automatic_retry':False,'source_job_fingerprint':packet['generation_job']['job_fingerprint']},None,None,None,None)
 safe_path(receipt);result=read_json(receipt)
 source=read_json(directory/'source_supervisor_packet.json');verify(source,'packet_fingerprint')
 if source!=packet:raise ValueError('Stored generation attempt source differs from the job.')
 master=directory/'output.mp4';safe_path(master)
 validate_outcome(result,packet,master if master.exists() else None)
 directory_export=Path(tempfile.mkdtemp(prefix='joat-managed-resume-'))
 result_file=directory_export/'generation_result.json';result_file.write_text(json.dumps(result,indent=2))
 source_file=directory_export/'source_supervisor_packet.json';source_file.write_text(json.dumps(source,indent=2))
 video=None
 if master.exists():
  safe_path(master)
  expected=(result.get('media_evidence') or {}).get('sha256')
  if expected and file_hash(master)!=expected:raise ValueError('Stored generation media integrity failed.')
  video=str(directory_export/'output.mp4');shutil.copyfile(master,video)
 return result,video,str(result_file),str(source_file),None


def worker_action(worker,value,phase,token,root=ROOT,storage_check=mount_check,native=None):
 packet,job,project=scope(value,phase);worker.validate_supervisor_packet(packet)
 storage_check('worker')
 if native is None:
  from joat_render_bridge import prepare_plan,check_render_connection,execute_render,render_failure_report
  native=(prepare_plan,check_render_connection,execute_render,render_failure_report)
 prepare,check,execute,failure=native
 if phase=='prepare':
  plan=prepare(worker,packet)
  cached=cached_delivery(packet,root)
  return {'schema':'joat.managed_render_plan.v1','file_version':FILE_VERSION,'project_id':project,
          'source_job_fingerprint':job['job_fingerprint'],'source_supervisor_fingerprint':packet['packet_fingerprint'],
          'plan':plan,'plan_fingerprint':digest(plan),'gpu_called':False,
          'approved_delivery_available':cached is not None,'automatic_retry':False}
 if phase=='check':return check(worker,packet,value['plan'],token)
 if phase=='status':return existing_attempt(packet,value['plan'],root)
 if phase=='reuse':
  cached=cached_delivery(packet,root)
  if cached is None:
   return ({'schema':'joat.managed_generation_reuse.v1','file_version':FILE_VERSION,'status':'no_approved_delivery_available','source_job_fingerprint':job['job_fingerprint'],'gpu_called':False,'automatic_retry':False},None,None,None,None)
  result,master=cached;directory=Path(tempfile.mkdtemp(prefix='joat-managed-readonly-cache-'));video=directory/'approved_master.mp4';shutil.copyfile(master,video)
  approved=directory/'approved_final_result.json';approved.write_text(json.dumps(result,indent=2))
  return ({'schema':'joat.managed_generation_reuse.v1','file_version':FILE_VERSION,'status':'approved_delivery_reused','source_job_fingerprint':job['job_fingerprint'],'gpu_called':False,'automatic_retry':False,'final_result_fingerprint':result['result_fingerprint'],'master_sha256':result['final_master']['sha256'],'note':'Read-only reuse of an independently approved final master. No render fallback exists.'},str(video),None,None,str(approved))

 if value['plan']!=prepare(worker,packet):raise ValueError('Actual render plan changed; prepare and review again.')
 cached=cached_delivery(packet,root)
 if cached is not None:
  result,master=cached;directory=Path(tempfile.mkdtemp(prefix='joat-managed-cache-'));video=directory/'approved_master.mp4';shutil.copyfile(master,video)
  approved=directory/'approved_final_result.json';approved.write_text(json.dumps(result,indent=2))
  report={'schema':'joat.managed_generation_reuse.v1','file_version':FILE_VERSION,'status':'approved_delivery_reused',
          'source_job_fingerprint':job['job_fingerprint'],'gpu_called':False,'automatic_retry':False,
          'final_result_fingerprint':result['result_fingerprint'],'master_sha256':result['final_master']['sha256'],
          'note':'Existing independently approved final master reused; this is not a new raw generation result.'}
  return report,str(video),None,None,str(approved)
 directory=attempt_dir(packet,value['plan'],root)
 with LOCK:
  if (directory/'reservation.json').exists():return existing_attempt(packet,value['plan'],root)
  write_once(directory/'reservation.json',{'schema':'joat.managed_generation_reservation.v1','file_version':FILE_VERSION,
       'source_job_fingerprint':job['job_fingerprint'],'plan_fingerprint':value['plan_fingerprint'],
       'owner_approved':True,'reserved_at_epoch':time.time(),'automatic_retry':False})
  write_once(directory/'source_supervisor_packet.json',packet)
 try:result,video,result_file,source_file=execute(worker,packet,value['plan'],token)
 except Exception as exc:
  result=failure(exc,packet,token);video,result_file,source_file=getattr(exc,'render_failure_assets',(None,None,None))
 validate_outcome(result,packet,video)
 if video is not None:store_media(video,directory/'output.mp4')
 write_once(directory/'result.json',result)
 return existing_attempt(packet,value['plan'],root)


def safe_validation_message(exc,token):
 message=str(exc)
 for hidden in (token,os.environ.get('JOAT_DISPATCH_SIGNING_KEY',''),os.environ.get('JOAT_SPECIALIST_TOKEN','')):
  if hidden:message=message.replace(hidden,'[redacted]')
 message=re.sub(r'hf_[A-Za-z0-9]+','[redacted]',message)
 message=re.sub(r'https?://\S+','[url]',message)
 return message[:300]


def add_managed_generation_api(role,worker=None,root=ROOT,storage_check=mount_check,client_factory=client_for,native=None):
 if role not in ('executive','supervisor','worker'):raise ValueError('Unknown managed API role.')
 def handler(phase,payload,profile,oauth,request):
  token=owner_token(profile,oauth,request)
  if not isinstance(payload,str) or len(payload.encode())>2*1024*1024:raise gr.Error('Missing or oversized managed payload.')
  if role in NEXT and os.environ.get('JOAT_DISPATCH_ENABLED','false').lower()!='true':
   raise gr.Error('Existing JOAT_DISPATCH_ENABLED flag disables managed forwarding in '+role+'. No downstream request sent.')
  stage='decode_and_scope'
  try:
   value=json.loads(payload);scope(value,phase)
   if role=='executive':
    stage='verify_main_signature';validate_executive(value,phase)
   if role in NEXT:
    stage='forward_'+NEXT[role];return proxy(NEXT[role],phase,value,token,client_factory)
   stage='worker_validation_or_operation'
   return worker_action(worker,value,phase,token,root,storage_check,native)
  except (ValueError,KeyError,TypeError) as exc:
   message=safe_validation_message(exc,token)
   print('JOAT_MANAGED_VALIDATION '+stable({'role':role,'phase':phase,'stage':stage,'error_type':type(exc).__name__,'safe_message':message[:300],'gpu_requested_by_phase':phase=='execute'}),flush=True)
   raise gr.Error('Managed request or checkpoint validation failed. No automatic retry; recheck the exact plan/source.') from None
  except Exception:raise gr.Error('Managed '+phase+' connection failed or outcome is unknown. No automatic retry; use status recovery before another render.') from None
 # Different phases deliberately expose different output contracts.
 for phase in PHASES:
  # Bind the phase without making it an API parameter.
  def bind(phase):
   def action(payload:str,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
    return handler(phase,payload,profile,oauth,request)
   return action
  payload=gr.Textbox(visible=False)
  outputs=[gr.JSON(visible=False)] if phase in ('prepare','check') else [gr.JSON(visible=False),gr.File(visible=False),gr.File(visible=False),gr.File(visible=False),gr.File(visible=False)]
  gr.Button(visible=False).click(bind(phase),[payload],outputs,api_name='managed_'+phase,api_visibility='public',concurrency_limit=1)


def add_managed_generation_ui(media_controls,audit=None):
 def current_packet(file,retained):
  if not retained:raise gr.Error('Prepare the render plan first.')
  packet,plan=retained
  if read_json(file)!=packet:raise gr.Error('The uploaded source changed; prepare and review its plan again.')
  return packet,plan
 def prepare_ui(file,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
  token=owner_token(profile,oauth,request);packet=read_json(file);value=sign(packet,'prepare')
  response=proxy('executive','prepare',value,token)
  if (response.get('schema')!='joat.managed_render_plan.v1' or response.get('source_job_fingerprint')!=packet['generation_job']['job_fingerprint']
      or response.get('source_supervisor_fingerprint')!=packet['packet_fingerprint'] or digest(response.get('plan'))!=response.get('plan_fingerprint')
      or response.get('gpu_called') is not False):raise gr.Error('Managed plan response does not match this exact job.')
  return response,(packet,response['plan']),False
 def check_ui(file,retained,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
  token=owner_token(profile,oauth,request)
  packet,plan=current_packet(file,retained);return proxy('executive','check',sign(packet,'check',plan),token)
 def execute_ui(file,retained,approved,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
  token=owner_token(profile,oauth,request)
  if approved is not True:raise gr.Error('Review and explicitly approve the displayed render/GPU ceiling first.')
  packet,plan=current_packet(file,retained);output=proxy('executive','execute',sign(packet,'execute',plan,True),token)
  return present(output,packet)
 def reuse_ui(file,retained,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
  token=owner_token(profile,oauth,request);packet,plan=current_packet(file,retained)
  return present(proxy('executive','reuse',sign(packet,'reuse',plan),token),packet)
 def status_ui(file,retained,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
  token=owner_token(profile,oauth,request)
  packet,plan=current_packet(file,retained);return present(proxy('executive','status',sign(packet,'status',plan),token),packet)
 def present(output,packet):
  result,video,result_file,source_file,approved_file=output
  generation_result=generation_source=generation_video=final_result=final_video=None
  if result.get('schema')=='joat.generation_result.v1':
   validate_outcome(result,packet,video)
   if read_json(result_file)!=result or read_json(source_file)!=packet:raise gr.Error('Downloaded generation packets changed the source/evidence.')
   generation_result,generation_source,generation_video=result_file,source_file,video
  elif result.get('status')=='approved_delivery_reused':
   approved=read_json(approved_file);verify(approved,'result_fingerprint')
   qc=approved.get('final_qc',{})
   if (approved.get('source_job_fingerprint')!=packet['generation_job']['job_fingerprint'] or approved.get('delivery_authorized') is not True
       or qc.get('decision')!='PASS' or qc.get('reviewer')!=OWNER
       or set(qc.get('checks',{}))!={'picture','audio','titles','continuity'} or not all(v is True for v in qc['checks'].values())
       or qc.get('asset_sha256')!=approved['final_master']['sha256']
       or file_hash(video)!=approved['final_master']['sha256']):raise gr.Error('Cached final master does not bind this exact approved job.')
   final_result,final_video=approved_file,video
  if audit:audit('managed_generation_outcome',{'source_job_fingerprint':packet['generation_job']['job_fingerprint'],'schema':result.get('schema'),'status':result.get('status')})
  return result,video,result_file,source_file,approved_file,generation_result,generation_source,generation_video,final_result,final_video,False
 def saved_sources(project,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
  owner_token(profile,oauth,request);project=valid_project(project)
  directory=safe_path(ROOT/'approved-jobs'/project);choices=[]
  if directory.is_dir():
   for file in sorted(directory.glob('*/*.json')):
    safe_path(file);packet=read_json(file);verify(packet,'packet_fingerprint');job=packet['generation_job'];verify(job,'job_fingerprint')
    if job['project_context']['project_id']!=project or packet.get('production_ready') is not True:raise gr.Error('Stored source scope mismatch.')
    key=str(file.relative_to(directory));context=job['project_context']
    choices.append((context.get('scene_id','')+' / '+context.get('shot_id','')+' / '+job['job_fingerprint'][:12],key))
  return gr.update(choices=choices,value=choices[-1][1] if choices else None)
 def load_saved(project,selected,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
  owner_token(profile,oauth,request);project=valid_project(project)
  if not isinstance(selected,str) or not re.fullmatch(r'[a-f0-9]{64}/[a-f0-9]{64}\.json',selected):raise gr.Error('Select a saved approved source first.')
  file=safe_path(ROOT/'approved-jobs'/project/selected);packet=read_json(file)
  verify(packet,'packet_fingerprint');verify(packet['generation_job'],'job_fingerprint')
  if packet['generation_job']['project_context']['project_id']!=project or packet.get('production_ready') is not True:raise gr.Error('Stored source scope mismatch.')
  return export(packet,'source_supervisor_packet.json'),None,None,False
 with gr.Tab('Managed Generation'):
  gr.LoginButton()
  gr.Markdown('Use an approved original Generation Supervisor packet. Main delegates through Executive → Generation Supervisor → Worker. Plan/connection/status checks use no GPU. Rendering requires explicit approval of the displayed plan and reservation ceiling. Existing approved deliveries are reused; uncertain attempts are never automatically repeated.')
  source=gr.File(label='Approved original Supervisor packet JSON',type='filepath',file_types=['.json'])
  shown=gr.JSON(label='Exact managed render plan and cache availability');retained=gr.State(None)
  project=gr.Textbox(label='Saved approved source project',value='PROJECT-001')
  saved=gr.Dropdown(label='Saved approved source job',choices=[],value=None)
  approval=gr.Checkbox(label='I approve this exact render plan and its GPU reservation ceiling; reuse an existing approved result when available',value=False)
  gr.Button('Refresh saved approved jobs (no GPU)').click(saved_sources,[project],saved,api_visibility='private',concurrency_limit=1)
  gr.Button('Load selected approved source (no GPU)').click(load_saved,[project,saved],[source,retained,shown,approval],api_visibility='private',concurrency_limit=1)
  gr.Button('Prepare supervised render plan (no GPU)').click(prepare_ui,[source],[shown,retained,approval],api_visibility='private',concurrency_limit=1)
  connection=gr.JSON(label='Renderer connection check or status')
  gr.Button('Check supervised renderer connection (no GPU)').click(check_ui,[source,retained],connection,api_visibility='private',concurrency_limit=1)
  from joat_remote_generation import add_remote_approval_ui
  add_remote_approval_ui(source,retained)
  result=gr.JSON(label='Generation outcome; independent QC still required');video=gr.Video()
  generated_file=gr.File(label='generation_result.json');original_file=gr.File(label='source_supervisor_packet.json');cached_file=gr.File(label='Existing approved final result, if reused')
  targets=[result,video,generated_file,original_file,cached_file,media_controls['generation'],media_controls['supervisor'],media_controls['original'],media_controls['approved_result'],media_controls['approved_media'],approval]
  gr.Button('Run one approved supervised render or reuse approved delivery').click(execute_ui,[source,retained,approval],targets,api_visibility='private',concurrency_limit=1,trigger_mode='once')
  gr.Button('Recover existing attempt status (no new GPU request)').click(status_ui,[source,retained],targets,api_visibility='private',concurrency_limit=1)
  gr.Button('Reuse approved delivery only (no GPU; no render fallback)').click(reuse_ui,[source,retained],targets,api_visibility='private',concurrency_limit=1)
  # Manual uploads invalidate the reviewed plan. Saved-source loading already
 # clears it explicitly; its programmatic change event must not erase a newly
 # prepared plan after a delayed browser event.
 source.upload(lambda:(None,None,False),outputs=[retained,shown,approval],api_visibility='private')
 source.clear(lambda:(None,None,False),outputs=[retained,shown,approval],api_visibility='private')
 # Clear stale managed media for both manual and programmatic source changes.
 # This callback never clears the newly prepared plan or grants approval.
 source.change(lambda:(None,None,None,None,None),outputs=[result,video,generated_file,original_file,cached_file],api_visibility='private')


def add_managed_main_cpu_api():
 """Owner-only API entry points for Main's signed, CPU-only generation checks."""
 def prepare(raw_packet:str,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
  token=owner_token(profile,oauth,request)
  if len(raw_packet.encode())>2*1024*1024:raise gr.Error('Oversized source packet.')
  packet=json.loads(raw_packet);value=sign(packet,'prepare')
  result=proxy('executive','prepare',value,token)
  if (result.get('schema')!='joat.managed_render_plan.v1' or result.get('gpu_called') is not False
      or result.get('source_job_fingerprint')!=packet['generation_job']['job_fingerprint']
      or result.get('source_supervisor_fingerprint')!=packet['packet_fingerprint']
      or digest(result.get('plan'))!=result.get('plan_fingerprint')):
   raise gr.Error('CPU-only Main plan response failed exact source validation.')
  return result
 def check(raw_packet:str,raw_plan:str,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
  token=owner_token(profile,oauth,request)
  if max(len(raw_packet.encode()),len(raw_plan.encode()))>2*1024*1024:raise gr.Error('Oversized CPU check payload.')
  packet=json.loads(raw_packet);plan=json.loads(raw_plan)
  result=proxy('executive','check',sign(packet,'check',plan),token)
  if (result.get('schema')!='joat.render_connection_check.v1' or result.get('status')!='passed'
      or result.get('gpu_called') is not False
      or result.get('source_job_fingerprint')!=packet['generation_job']['job_fingerprint']):
   raise gr.Error('CPU-only Main renderer check did not pass for this exact source job.')
  return result
 packet=gr.Textbox(visible=False);plan=gr.Textbox(visible=False);output=gr.JSON(visible=False)
 gr.Button(visible=False).click(prepare,[packet],output,api_name='managed_prepare_from_packet',api_visibility='public',concurrency_limit=1)
 gr.Button(visible=False).click(check,[packet,plan],output,api_name='managed_check_from_plan',api_visibility='public',concurrency_limit=1)
