"""Durable owner-approved remote generation. File version 1.0.11.
One exact plan, one remote attempt, 24-hour expiry. No retries or QC approval.
Private requests arrive through owner-managed Space secrets; artifacts stay in studio storage.
"""
FILE_VERSION='1.0.11'
import hashlib,hmac,json,os,re,threading,time,uuid
from pathlib import Path
from typing import Optional
import gradio as gr
import joat_managed_generation as m
PREFIX='JOAT_REMOTE_GENERATION_REQUEST_'
BASE=m.ROOT/'remote-generation'
OPERATIONS=('prepare','check','execute','status','resume','diagnose')

def hex_id(value,length):
 if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{'+str(length)+'}',value):raise ValueError('Invalid remote identifier.')
 return value

def location(root,*parts):return m.safe_path(Path(root).joinpath(*parts))
def source_for(project,job,supervisor,root=m.ROOT):
 project=m.valid_project(project);hex_id(job,64);hex_id(supervisor,64)
 packet=m.read_json(location(root,'approved-jobs',project,job,supervisor+'.json'))
 m.verify(packet,'packet_fingerprint');m.verify(packet['generation_job'],'job_fingerprint')
 if (packet['packet_fingerprint']!=supervisor or packet['generation_job']['job_fingerprint']!=job or
     packet['generation_job']['project_context']['project_id']!=project or packet.get('production_ready') is not True):
  raise ValueError('Approved source scope differs.')
 return packet

def prepared_path(root,packet,fp):
 hex_id(fp,64)
 return location(root,'remote-generation','plans',packet['generation_job']['project_context']['project_id'],packet['generation_job']['job_fingerprint'],fp+'.json')

def save_plan(packet,response,root=m.ROOT):
 if (response.get('schema')!='joat.managed_render_plan.v1' or response.get('gpu_called') is not False or
     response.get('source_job_fingerprint')!=packet['generation_job']['job_fingerprint'] or
     response.get('source_supervisor_fingerprint')!=packet['packet_fingerprint'] or
     m.digest(response.get('plan'))!=response.get('plan_fingerprint')):raise ValueError('Exact remote plan response differs.')
 path=prepared_path(root,packet,response['plan_fingerprint'])
 try:m.write_once(path,response)
 except FileExistsError:
  old=m.read_json(path)
  if old['plan']!=response['plan']:raise ValueError('Stored remote plan differs.')
 return path

def grant(packet,plan,approved,root=m.ROOT,now=None):
 from joat_project_lifecycle import assert_active
 assert_active(packet['generation_job']['project_context']['project_id'],root)
 from joat_character_speech_policy import require_character_speech
 require_character_speech(packet,root)
 if approved is not True:raise ValueError('Explicit remote approval is required.')
 m.scope(m.sign(packet,'check',plan),'check')
 # The plan itself is displayed/reviewed in the same retained browser state.
 budget=plan.get('parameters',{}).get('gen_budget')
 if type(budget) not in (int,float) or not 0<budget<=600:raise ValueError('Remote render requires an explicit ceiling of at most 600 seconds.')
 source_for(packet['generation_job']['project_context']['project_id'],packet['generation_job']['job_fingerprint'],packet['packet_fingerprint'],root)
 fp=m.digest(plan);save_plan(packet,dict(schema='joat.managed_render_plan.v1',gpu_called=False,plan=plan,plan_fingerprint=fp,source_job_fingerprint=packet['generation_job']['job_fingerprint'],source_supervisor_fingerprint=packet['packet_fingerprint']),root)
 identifier=uuid.uuid4().hex;issued=time.time() if now is None else now
 value=dict(schema='joat.remote_generation_grant.v1',file_version=FILE_VERSION,grant_id=identifier,owner=m.OWNER,
  project_id=packet['generation_job']['project_context']['project_id'],source_job_fingerprint=packet['generation_job']['job_fingerprint'],
  source_supervisor_fingerprint=packet['packet_fingerprint'],plan_fingerprint=fp,created_at_epoch=issued,expires_at_epoch=issued+86400,
  maximum_render_attempts=1,gpu_ceiling_seconds=budget,automatic_retry=False,production_qc_approved=False)
 value['grant_fingerprint']=m.digest(value)
 m.write_once(location(root,'remote-generation','grants',identifier,'grant.json'),value)
 return value

def load_grant(identifier,packet,fp,root=m.ROOT,now=None):
 hex_id(identifier,32)
 value=m.read_json(location(root,'remote-generation','grants',identifier,'grant.json'));m.verify(value,'grant_fingerprint')
 if (value.get('schema')!='joat.remote_generation_grant.v1' or value.get('owner')!=m.OWNER or value.get('maximum_render_attempts')!=1 or
     value.get('automatic_retry') is not False or value.get('source_job_fingerprint')!=packet['generation_job']['job_fingerprint'] or
     value.get('source_supervisor_fingerprint')!=packet['packet_fingerprint'] or value.get('project_id')!=packet['generation_job']['project_context']['project_id'] or value.get('plan_fingerprint')!=fp):
  raise ValueError('Remote approval does not bind this exact plan/source.')
 if (time.time() if now is None else now)>=value['expires_at_epoch']:raise ValueError('Remote approval expired.')
 revoked=location(root,'remote-generation','grants',identifier,'revoked.json')
 if revoked.exists():raise ValueError('Remote approval revoked.')
 return value

def signed(packet,phase,plan=None,execution_id=None):
 value=m.sign(packet,phase,plan,phase=='execute')
 if execution_id is not None:
  hex_id(execution_id,32);value.pop('signature');value['remote_execution_id']=execution_id
  value['signature']=hmac.new(os.environ['JOAT_DISPATCH_SIGNING_KEY'].encode(),m.stable(value).encode(),hashlib.sha256).hexdigest()
 return value

def report(value):
 # Owner-protected container logs contain only IDs/status, never tokens or media.
 safe={k:value.get(k) for k in ('schema','file_version','request_id','operation','status','stage','error_type','source_job_fingerprint','plan_fingerprint','grant_id','artifact_index_path','automatic_retry','gpu_requested','transport_diagnostics','error_frames') if k in value}
 print('JOAT_REMOTE_GENERATION '+m.stable(safe),flush=True)

def persist_outcome(output,packet,directory,root):
 result,video,result_file,source_file,approved_file=output
 entries=[]
 if result.get('schema') in ('joat.generation_result.v1','joat.render_failure.v1'):m.validate_outcome(result,packet,video)
 if source_file and m.read_json(source_file)!=packet:raise ValueError('Returned source differs.')
 if result_file and m.read_json(result_file)!=result:raise ValueError('Returned result differs.')
 for name,path in [('output.mp4',video),('generation_result.json',result_file),('source_supervisor_packet.json',source_file),('approved_final_result.json',approved_file)]:
  if not path:continue
  target=location(directory,'artifacts',name)
  if not target.exists():m.store_media(path,target)
  if m.file_hash(path)!=m.file_hash(target):raise ValueError('Recovered artifact differs.')
  entries.append(dict(filename=name,bucket_path=str(target.relative_to(Path(root).parent)),sha256=m.file_hash(target),size_bytes=target.stat().st_size))
 index=dict(schema='joat.remote_artifact_index.v1',file_version=FILE_VERSION,source_job_fingerprint=packet['generation_job']['job_fingerprint'],result_status=result.get('status'),result_schema=result.get('schema'),qc_approved=False,files=entries)
 target=location(directory,'artifact_index.json')
 if not target.exists():m.write_once(target,index)
 return result,str(target.relative_to(Path(root).parent))

def run(name,raw,root=m.ROOT,client_proxy=m.proxy,identity_api=m.HfApi,storage_check=m.mount_check):
 identifier=name[len(PREFIX):];hex_id(identifier,32)
 directory=location(root,'remote-generation','requests',identifier);receipt=directory/'receipt.json'
 if receipt.exists():value=m.read_json(receipt);report(value);return value
 marker=directory/'request.json'
 if marker.exists():
  value=dict(schema='joat.remote_generation_receipt.v1',file_version=FILE_VERSION,request_id=identifier,status='pending_or_unknown',automatic_retry=False,gpu_requested=None);report(value);return value
 stage='validate_request';value=None;claimed=False
 try:
  if not isinstance(raw,str) or len(raw.encode())>16384:raise ValueError('Oversized remote request.')
  value=json.loads(raw)
  required={'schema','file_version','request_id','operation','project_id','source_job_fingerprint','source_supervisor_fingerprint'}
  if set(value)-required-{'plan_fingerprint','grant_id','execution_id'} or not required<=set(value):raise ValueError('Invalid remote request fields.')
  if value['schema']!='joat.remote_generation_request.v1' or value['request_id']!=identifier or value['operation'] not in OPERATIONS:raise ValueError('Invalid remote operation.')
  storage_check('main');packet=source_for(value['project_id'],value['source_job_fingerprint'],value['source_supervisor_fingerprint'],root)
  token=os.environ.get('JOAT_SPECIALIST_TOKEN','')
  if not token or identity_api(token=token).whoami().get('name')!=m.OWNER:raise ValueError('Existing service credential is not verified owner.')
  operation=value['operation'];plan=None
  if operation in ('execute','resume'):
   from joat_character_speech_policy import require_character_speech
   require_character_speech(packet,root)
  if operation in ('prepare','check','execute','resume'):
   from joat_project_lifecycle import assert_active
   assert_active(value['project_id'],root)
  if operation!='prepare':
   prepared=m.read_json(prepared_path(root,packet,value.get('plan_fingerprint')));plan=prepared['plan']
   if m.digest(plan)!=value['plan_fingerprint']:raise ValueError('Stored plan integrity failed.')
  authorization=None
  if operation in ('execute','resume'):
   authorization=load_grant(value.get('grant_id'),packet,value['plan_fingerprint'],root)
   if plan['parameters']['gen_budget']!=authorization['gpu_ceiling_seconds']:raise ValueError('Approved GPU ceiling differs.')
   if operation=='resume':
    execution_id=hex_id(value.get('execution_id'),32)
    use=m.read_json(location(root,'remote-generation','grants',value['grant_id'],'use.json'))
    if use.get('request_id')!=execution_id or use.get('plan_fingerprint')!=value['plan_fingerprint']:raise ValueError('Recovery must use the original approved execution ID.')
  # Exclusive durable request marker prevents duplicate startup/task dispatch.
  m.write_once(marker,value);claimed=True
  if operation=='execute':
   stage='reserve_owner_grant'
   m.write_once(location(root,'remote-generation','grants',value['grant_id'],'use.json'),dict(request_id=identifier,plan_fingerprint=value['plan_fingerprint'],reserved_at_epoch=time.time(),automatic_retry=False))
  if operation=='diagnose':
   import httpx
   rows=[]
   for suffix in ('config','gradio_api/info'):
    for authenticated in (False,True):
     headers={'x-hf-authorization':'Bearer '+token} if authenticated else {}
     try:
      response=httpx.get(m.RUNTIME_URLS['executive']+'/'+suffix,headers=headers,timeout=15)
      rows.append(dict(endpoint=suffix,authenticated=authenticated,http_status=response.status_code,content_type=response.headers.get('content-type'),retry_after=response.headers.get('retry-after')))
     except Exception as exc:rows.append(dict(endpoint=suffix,authenticated=authenticated,error_type=type(exc).__name__))
   client=None
   try:
    import tempfile
    client=m.client_for('executive',token,tempfile.mkdtemp(prefix='joat-transport-diagnostic-'))
    rows.append(dict(endpoint='sdk_initialize',status='passed'))
   except Exception as exc:
    import traceback
    rows.append(dict(endpoint='sdk_initialize',error_type=type(exc).__name__,frames=[{'file':Path(f.filename).name,'function':f.name,'line':f.lineno} for f in traceback.extract_tb(exc.__traceback__)[-6:]]))
   finally:
    if client:client.close()
   result=dict(schema='joat.remote_generation_receipt.v1',file_version=FILE_VERSION,request_id=identifier,operation=operation,status='diagnosed',transport_diagnostics=rows,automatic_retry=False,gpu_requested=False)
   m.write_once(receipt,result);report(result);return result
  stage='signed_'+operation
  phase='execute' if operation=='resume' else operation
  execution_id=identifier if operation=='execute' else value.get('execution_id')
  response=client_proxy('executive',phase,signed(packet,phase,plan,execution_id),token)
  index=None
  if operation=='prepare':
   save_plan(packet,response,root);m.write_once(directory/'managed_plan.json',response);fp=response['plan_fingerprint'];status='prepared'
  elif operation=='check':
   if (response.get('schema')!='joat.render_connection_check.v1' or response.get('source_job_fingerprint')!=packet['generation_job']['job_fingerprint'] or response.get('gpu_called') is not False):raise ValueError('Connection check response differs from exact job.')
   m.write_once(directory/'connection_check.json',response);fp=value['plan_fingerprint'];status='connection_passed' if response.get('status')=='passed' and response.get('gpu_called') is False else 'connection_failed'
  else:
   outcome,index=persist_outcome(response,packet,directory,root);fp=value['plan_fingerprint'];status=outcome.get('status','unknown')
  result=dict(schema='joat.remote_generation_receipt.v1',file_version=FILE_VERSION,request_id=identifier,operation=operation,status=status,source_job_fingerprint=packet['generation_job']['job_fingerprint'],plan_fingerprint=fp,grant_id=value.get('grant_id'),artifact_index_path=index,automatic_retry=False,gpu_requested=operation in ('execute','resume'))
  m.write_once(receipt,result);report(result);return result
 except FileExistsError:
  # A previously reserved grant is never spent a second time.
  result=dict(schema='joat.remote_generation_receipt.v1',file_version=FILE_VERSION,request_id=identifier,status='already_reserved_no_retry',stage=stage,automatic_retry=False,gpu_requested=False)
 except Exception as exc:
  caught_error=exc
  import traceback
  print('JOAT_REMOTE_ERROR_TRACE '+m.stable({'request_id':identifier,'frames':[{'file':Path(f.filename).name,'function':f.name,'line':f.lineno} for f in traceback.extract_tb(exc.__traceback__)[-8:]]}),flush=True)
  result=dict(schema='joat.remote_generation_receipt.v1',file_version=FILE_VERSION,request_id=identifier,status='failed_or_unknown' if claimed else 'rejected',operation=value.get('operation') if isinstance(value,dict) else None,stage=stage,error_type=type(exc).__name__,error_frames=[{'file':Path(f.filename).name,'function':f.name,'line':f.lineno} for f in traceback.extract_tb(exc.__traceback__)[-6:]],automatic_retry=False,gpu_requested=bool(claimed and isinstance(value,dict) and value.get('operation') in ('execute','resume') and stage in ('signed_execute','signed_resume')))
 response=getattr(locals().get('caught_error'), 'response', None)
 if response is not None:
  status=getattr(response,'status_code',None)
  if isinstance(status,int):result['http_status']=status
  retry=response.headers.get('retry-after')
  if isinstance(retry,str) and retry.isdigit():result['retry_after_seconds']=int(retry)
 if response is not None:
  # Owner-only bounded diagnostics. Never retain authentication/cookie headers.
  from urllib.parse import urlsplit,urlunsplit
  from html import unescape
  endpoint=urlsplit(str(getattr(response,'url','')))
  body=getattr(response,'text','')
  body=re.sub(r'(?is)<(head|script|style)\b[^>]*>.*?</\1>',' ',body)
  body=re.sub(r'(?is)<[^>]*>',' ',body)
  body=unescape(re.sub(r'\s+',' ',body)).strip()
  token=os.environ.get('JOAT_SPECIALIST_TOKEN','')
  if token:body=body.replace(token,'[REDACTED]')
  body=re.sub(r'hf_[A-Za-z0-9]+|(?i:Bearer)\s+[^\s]+','[REDACTED]',body)
  selected={k:response.headers[k] for k in ('retry-after','ratelimit','ratelimit-policy','x-ratelimit-reset','x-ratelimit-remaining','content-type','x-request-id') if k in response.headers}
  result['transport_diagnostics']={'endpoint':urlunsplit((endpoint.scheme,endpoint.netloc,endpoint.path,'','')),'http_status':getattr(response,'status_code',None),'rate_limit_headers':selected,'server_message':body[:1800]}
 if claimed and not receipt.exists():m.write_once(receipt,result)
 report(result);return result

def start_remote_requests():
 if os.environ.get('SPACE_ID')!=m.SPACES['main']:return
 for name in sorted(os.environ):
  if name.startswith(PREFIX):threading.Thread(target=run,args=(name,os.environ[name]),daemon=True).start()

def add_remote_approval_ui(source,retained):
 def approve(file,state,confirmed,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
  m.owner_token(profile,oauth,request);m.mount_check('main')
  if not state:raise gr.Error('Prepare and review the exact render plan first.')
  packet,plan=state
  if m.read_json(file)!=packet:raise gr.Error('Source changed; prepare again.')
  try:return grant(packet,plan,confirmed),False
  except ValueError as exc:raise gr.Error(str(exc)) from None
 def revoke(identifier,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
  m.owner_token(profile,oauth,request);hex_id(identifier,32)
  path=location(m.ROOT,'remote-generation','grants',identifier)
  m.read_json(path/'grant.json')
  if not (path/'revoked.json').exists():m.write_once(path/'revoked.json',dict(owner=m.OWNER,revoked_at_epoch=time.time(),file_version=FILE_VERSION))
  return dict(status='revoked',grant_id=identifier,already_running_job_cancelled=False)
 with gr.Accordion('Remote generation approval',open=True):
  gr.Markdown('Approve ONE remote attempt of the displayed exact plan, valid for 24 hours. No automatic retries. Results remain private in studio storage and still require independent QC. Revoking prevents new dispatch; it does not cancel an already-running render.')
  approval=gr.Checkbox(label='I authorize one remote render of this exact plan, within its displayed GPU ceiling',value=False)
  shown=gr.JSON(label='Remote generation authorization receipt')
  gr.Button('Authorize one remote render (does not start GPU)').click(approve,[source,retained,approval],[shown,approval],api_visibility='private',concurrency_limit=1,trigger_mode='once')
  identifier=gr.Textbox(label='Remote grant ID to revoke')
  gr.Button('Revoke unused remote authorization (no GPU)').click(revoke,[identifier],shown,api_visibility='private',concurrency_limit=1)


def add_remote_control_ui():
 def load(project,job,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
  m.owner_token(profile,oauth,request);m.mount_check('main');m.valid_project(project);hex_id(job,64)
  directory=location(m.ROOT,'remote-generation','plans',project,job)
  files=list(directory.glob('*.json')) if directory.is_dir() else []
  if not files:raise gr.Error('No remote plan prepared for this job yet.')
  file=max(files,key=lambda x:x.stat().st_mtime_ns);m.safe_path(file);value=m.read_json(file)
  packet=source_for(project,job,value['source_supervisor_fingerprint'])
  if (m.digest(value['plan'])!=value['plan_fingerprint'] or value['source_job_fingerprint']!=job or value.get('gpu_called') is not False):raise gr.Error('Saved remote plan integrity failed.')
  return m.export(packet,'source_supervisor_packet.json'),(packet,value['plan']),value
 def check_saved(state,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
  token=m.owner_token(profile,oauth,request);m.mount_check('main')
  if not state:raise gr.Error('Load the saved exact plan first.')
  packet,plan=state
  from joat_project_lifecycle import assert_active
  assert_active(packet['generation_job']['project_context']['project_id'],m.ROOT)
  result=m.proxy('executive','check',signed(packet,'check',plan),token)
  if result.get('schema')!='joat.render_connection_check.v1' or result.get('gpu_called') is not False or result.get('source_job_fingerprint')!=packet['generation_job']['job_fingerprint']:raise gr.Error('Connection evidence differs from this exact job.')
  return result
 with gr.Tab('Remote Generation'):
  gr.Markdown('Prepared speaking shot: Kiana visibly says “One more message. And I’m late. Again.” Native synchronized character speech is being qualified; this authorizes one attempt only, not a finished-film QC pass.')
  gr.LoginButton()
  gr.Markdown('Load the exact plan prepared remotely, review it, and authorize one attempt. You do not need to press the Managed Generation Run button. No GPU runs until the remote request uses your approval.')
  project=gr.Textbox(label='Remote project',value='PROJECT-OTU-STORY-60S-001')
  job=gr.Textbox(label='Remote approved job fingerprint',value='2d0864c9d67b6a585adc0b06648f9456e05c07d256e4ffeb9ccb4079cf626e67')
  source=gr.File(visible=False,type='filepath');state=gr.State(None);plan=gr.JSON(label='Saved exact remote render plan')
  gr.Button('Load latest saved remote plan (no GPU)').click(load,[project,job],[source,state,plan],api_visibility='private',concurrency_limit=1)
  connection=gr.JSON(label='Saved-plan connection check — no GPU')
  gr.Button('Check saved plan connection (no GPU)').click(check_saved,[state],connection,api_visibility='private',concurrency_limit=1)
  add_remote_approval_ui(source,state)
