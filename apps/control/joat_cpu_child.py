"""Isolated native department loader and callback IPC. File version1.0.2."""
FILE_VERSION='1.0.2'
import contextlib,importlib,inspect,io,json,os,re,resource,sys,time,typing
from pathlib import Path
ROOT=Path(__file__).parent;role=sys.argv[1]
sys.path.insert(0,str(ROOT));from joat_local_cpu import ROLES,stable
if role not in ROLES or os.environ.get('JOAT_CPU_CHILD_ROLE')!=role:raise SystemExit('Invalid local runtime role.')
DEPT=ROOT/'departments'/role;sys.path.insert(0,str(DEPT))
class BoundedSink(io.TextIOBase):
 def write(self,s):return len(s)
sink=BoundedSink()
def safe_error(exc):
 value=str(exc)
 if CURRENT_DELEGATION:value=value.replace(CURRENT_DELEGATION,'[REDACTED]')
 for key,secret in os.environ.items():
  if re.search('token|secret|password|_key',key,re.I) and len(secret)>7:value=value.replace(secret,'[REDACTED]')
 value=re.sub(r'hf_[A-Za-z0-9]+|(?i:Bearer)\s+[^\s\"\']+','[REDACTED]',value)
 return value[:1200]
CURRENT_DELEGATION=None
bootstrap_error=None
try:
 with contextlib.redirect_stdout(sink),contextlib.redirect_stderr(sink):
  import gradio as gr
  from starlette.requests import Request
  from joat_runtime_client import install
  install(local=True)
  app=importlib.import_module('app');blocks=app.build_app() if hasattr(app,'build_app') else app.demo;functions={('/'+f.api_name.lstrip('/')):f for f in blocks.fns.values() if f.api_name and f.api_visibility!='private'}
except Exception as exc:bootstrap_error=type(exc).__name__+': '+safe_error(exc)

def auth_type(annotation,kind):return annotation==kind or kind in typing.get_args(annotation)
def normalize(value):
 if isinstance(value,Path):return str(value)
 if isinstance(value,tuple):return [normalize(v) for v in value]
 if isinstance(value,list):return [normalize(v) for v in value]
 if isinstance(value,dict):
  if value.get('meta',{}).get('_type')=='gradio.FileData' and isinstance(value.get('path'),str):return value['path']
  return {k:normalize(v) for k,v in value.items()}
 return value

def call(endpoint,args,kwargs):
 if endpoint not in functions:raise ValueError('Endpoint is not a native public department contract.')
 # The migration never uses GPU to prove CPU consolidation. Runtime release is explicit.
 gpu_endpoints={'/render_ui','/render_remote','/managed_execute','/execute_remote_generation'}
 cpu_worker_endpoints={'/validate_ui','/execution_ui','/failure_ui','/tests_ui','/managed_prepare','/managed_check','/managed_status','/managed_reuse','/remote_prepare','/remote_status','/remote_check'}
 if (endpoint in gpu_endpoints or (role=='generation_worker' and endpoint not in cpu_worker_endpoints)) and os.environ.get('JOAT_STUDIO_GPU_HOLD','true').lower()=='true':raise ValueError('GPU production is on quota hold; no request was submitted.')
 f=functions[endpoint].fn;signature=inspect.signature(f);hints=typing.get_type_hints(f);parameters=list(signature.parameters.values());public=[p for p in parameters if not any(auth_type(hints.get(p.name),t) for t in (gr.OAuthProfile,gr.OAuthToken,gr.Request))]
 if len(args)>len(public) or set(kwargs)-{p.name for p in public}:raise ValueError('Department arguments do not match the exact public API.')
 values=dict(zip([p.name for p in public],normalize(args)))
 if set(values)&set(kwargs):raise ValueError('Duplicate positional and named inputs.')
 values.update(normalize(kwargs));token=os.environ.get('JOAT_SPECIALIST_TOKEN','')
 headers=[(b'authorization',('Bearer '+token).encode())]
 if CURRENT_DELEGATION:headers.append((b'x-ip-token',CURRENT_DELEGATION.encode()))
 request=Request({'type':'http','method':'POST','path':'/local-cpu','headers':headers})
 for p in parameters:
  hint=hints.get(p.name)
  if auth_type(hint,gr.OAuthProfile):values[p.name]=None
  elif auth_type(hint,gr.OAuthToken):values[p.name]=gr.OAuthToken(token=token,scope='read-repos',expires_at=time.time()+300) if token else None
  elif auth_type(hint,gr.Request):values[p.name]=gr.Request(request=request)
 signature.bind(**values)
 from gradio.context import LocalContext
 context=LocalContext.request.set(gr.Request(request=request))
 try:return normalize(f(**values))
 finally:LocalContext.request.reset(context)

def describe():
 result={}
 for name,block in functions.items():
  sig=inspect.signature(block.fn);hints=typing.get_type_hints(block.fn);params=[]
  for p in sig.parameters.values():
   if any(auth_type(hints.get(p.name),t) for t in (gr.OAuthProfile,gr.OAuthToken,gr.Request)):continue
   params.append(dict(parameter_name=p.name,parameter_has_default=p.default is not inspect.Parameter.empty,parameter_default=None if p.default is inspect.Parameter.empty else p.default))
  result[name]=dict(parameters=params,file_input_indices=[i for i,c in enumerate(block.inputs) if isinstance(c,(gr.File,gr.Video,gr.Audio,gr.Image,gr.Gallery))],file_output_indices=[i for i,c in enumerate(block.outputs) if isinstance(c,(gr.File,gr.Video,gr.Audio,gr.Image,gr.Gallery))],output_count=len(block.outputs))
 from joat_studio_capabilities import registry
 return dict(named_endpoints=result,unnamed_endpoints={},studio_capability_registry_fingerprint=registry()['registry_fingerprint'],feature_selection_authority='Main Assistant and Executive; native worker contracts remain authoritative')
for raw in sys.stdin.buffer:
 identifier=None;started=time.monotonic()
 try:
  if len(raw)>8*1024*1024:raise ValueError('Request exceeds8MiB.')
  request=json.loads(raw);identifier=request['request_id'];delegation=request.get('transport',{}).get('x-ip-token')
  CURRENT_DELEGATION=delegation if isinstance(delegation,str) and 0<len(delegation)<=8192 else None
  if bootstrap_error is not None:raise RuntimeError('Native department startup failed: '+bootstrap_error)
  with contextlib.redirect_stdout(sink),contextlib.redirect_stderr(sink):
   if request['command']=='describe':result=describe()
   elif request['command']=='call':result=call(request['endpoint'],request['args'],request['kwargs'])
   else:raise ValueError('Unsupported local command.')
  response=dict(request_id=identifier,status='ok',result=result,logical_department=role,physical_execution_space=os.environ.get('SPACE_ID'),elapsed_seconds=round(time.monotonic()-started,4),peak_rss_mib=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2))
 except Exception as exc:response=dict(request_id=identifier,status='failed_or_unknown',error_type=type(exc).__name__,safe_error_message=safe_error(exc),automatic_retry=False)
 CURRENT_DELEGATION=None
 sys.stdout.write(stable(response)+'\n');sys.stdout.flush()
