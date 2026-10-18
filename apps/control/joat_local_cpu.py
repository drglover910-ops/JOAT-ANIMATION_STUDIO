"""Bounded local CPU department processes, preserving native callbacks. File version1.0.3.
Internal IPC only. Platform delegation stays in memory; no automatic execution retries.
"""
FILE_VERSION='1.0.3'
import atexit,base64,hashlib,json,os,re,selectors,subprocess,sys,threading,time,uuid
from collections import OrderedDict
from pathlib import Path
ROOT=Path(__file__).parent
ROLES={'browser':'Browser-Worker-Bot','hugging_face':'Hugging-Face-Master-Bot','narration':'Narration-CPU','character':'Character-Asset-Master','environment':'Scene-Environment-Master','director':'Director-Creative-Intelligence','shot_camera':'Shot-Camera-Master','performance_action':'Performance-Action-Master','generation_supervisor':'Generation-Supervisor-Master','generation_worker':'Generation-Worker-Bot','quality_control':'Quality-Control-Bot','post_production':'Post-Production-Supervisor-Bot','editorial':'Editorial-Worker-Bot','sound':'Sound-Worker-Bot','music':'Music-Worker-Bot','compositing_vfx':'Compositing-VFX-Worker-Bot','color_finish':'Color-Finish-Worker-Bot','titles_graphics':'Titles-Graphics-Worker-Bot','voice_dialogue':'Voice-Dialogue-Worker-Bot','delivery_archive':'Delivery-Archive-Bot'}
REPOS={role:'Dezz-9-10/J.O.A.T.-'+name for role,name in ROLES.items()}
REPOS['narration']='Dezz-9-10/joat-narration'
HOSTS={repo:'https://'+re.sub('-+','-',re.sub('[^a-z0-9-]','-',repo.lower().replace('/','-')))+'.hf.space' for repo in REPOS.values()}
# Hugging Face removes dots from Space slugs; repo IDs remain logical identities.
def role_for(src):
 value=str(src).rstrip('/')
 for role,repo in REPOS.items():
  if value in (repo,HOSTS[repo]):return role
 return None

def enabled():return os.environ.get('JOAT_STUDIO_CONSOLIDATED_ENABLED','').lower()=='true'
def stable(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
_VERIFIED=False
def verify_bundle():
 global _VERIFIED
 if _VERIFIED:return
 manifest=json.loads((ROOT/'consolidated_manifest.json').read_text());core=dict(manifest);given=core.pop('manifest_fingerprint')
 if hashlib.sha256(stable(core).encode()).hexdigest()!=given:raise ValueError('Consolidated source manifest fingerprint mismatch.')
 indexed={item['path']:item for item in manifest['files']}
 for item in manifest['files']:
  path=ROOT/item['path']
  # Transport uses regular source objects; restore byte-exact original images only.
  if not path.exists() and item['path'].startswith('departments/') and path.suffix.lower() in ('.png','.jpg','.jpeg','.webp'):
   encoded=path.with_name(path.name+'.base64');entry=indexed.get(item['path']+'.base64')
   if entry is None or encoded.is_symlink() or not encoded.is_file() or hashlib.sha256(encoded.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('Pinned asset transport verification failed.')
   data=base64.b64decode(encoded.read_bytes(),validate=True)
   if len(data)!=item['size_bytes'] or hashlib.sha256(data).hexdigest()!=item['sha256']:raise ValueError('Restored canonical asset differs from its source.')
   if '..' in Path(item['path']).parts or not path.parent.resolve().is_relative_to(ROOT.resolve()):raise ValueError('Invalid canonical asset path.')
   with path.open('xb') as target:target.write(data)
  if '..' in Path(item['path']).parts or path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Installed department source differs from pinned manifest.')
 _VERIFIED=True
class LocalCPUError(RuntimeError):pass
class Pool:
 def __init__(self,max_workers=8):self.max_workers=max_workers;self.workers=OrderedDict();self.lock=threading.RLock()
 def stop(self,role):
  process=self.workers.pop(role,None)
  if process:
   try:process.stdin.close();process.wait(timeout=3)
   except Exception:process.kill();process.wait(timeout=5)
 def close(self):
  with self.lock:
   for role in list(self.workers):self.stop(role)
 def worker(self,role):
  verify_bundle()
  if role not in ROLES:raise ValueError('Unknown local department.')
  p=self.workers.get(role)
  if p is not None and p.poll() is not None:self.stop(role);p=None
  if p is None:
   while len(self.workers)>=self.max_workers:self.stop(next(iter(self.workers)))
   env=dict(os.environ);env.pop('JOAT_DISPATCH_SIGNING_KEY',None)
   # Only the Executive/Main retain dispatch-signing authority.
   for key in list(env):
    if key.startswith(('JOAT_PRODUCTION_TASK_','JOAT_CONSOLIDATION_CHECK_','JOAT_CAPABILITY_CHECK_')):env.pop(key)
   env['JOAT_CPU_CHILD_ROLE']=role;env['PYTHONUNBUFFERED']='1';env['GRADIO_ANALYTICS_ENABLED']='False';env['TOKENIZERS_PARALLELISM']='false'
   p=subprocess.Popen([sys.executable,'-u',str(ROOT/'joat_cpu_child.py'),role],cwd=str(ROOT/'departments'/role),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env=env,bufsize=0);self.workers[role]=p
  self.workers.move_to_end(role);return p
 def request(self,role,command,endpoint=None,args=None,kwargs=None,timeout=180):
  with self.lock:
   process=self.worker(role);identifier=uuid.uuid4().hex;request=dict(request_id=identifier,command=command,endpoint=endpoint,args=args or [],kwargs=kwargs or {})
   # Preserve only the platform's per-request IP delegation, never caller JSON.
   try:
    from gradio.context import LocalContext
    incoming=LocalContext.request.get(None);delegation=incoming.headers.get('x-ip-token') if incoming is not None else None
   except (ImportError,AttributeError):delegation=None
   if isinstance(delegation,str) and 0<len(delegation)<=8192:request['transport']={'x-ip-token':delegation}
   raw=(stable(request)+'\n').encode()
   if len(raw)>8*1024*1024:raise ValueError('Local department request exceeds8MiB.')
   try:
    process.stdin.write(raw);process.stdin.flush();ready=selectors.DefaultSelector();ready.register(process.stdout,selectors.EVENT_READ);buffer=bytearray();end=time.monotonic()+timeout
    while b'\n' not in buffer:
     if time.monotonic()>=end:raise TimeoutError('Local department outcome unknown; no automatic retry.')
     if not ready.select(min(1,max(0,end-time.monotonic()))):continue
     block=os.read(process.stdout.fileno(),65536)
     if not block:raise LocalCPUError('Local department stopped; inspect checkpoint before resuming.')
     buffer.extend(block)
     if len(buffer)>32*1024*1024:raise LocalCPUError('Local department response limit exceeded.')
    ready.close();response=json.loads(buffer.split(b'\n',1)[0])
    if response.get('request_id')!=identifier:raise LocalCPUError('Local IPC response identity mismatch.')
    if response.get('status')!='ok':raise LocalCPUError(response.get('error_type','Error')+': '+response.get('safe_error_message','Department action failed.'))
    return response
   except BaseException:
    self.stop(role);raise
POOL=Pool();atexit.register(POOL.close)
class ImmediateJob:
 def __init__(self,fn):self.fn=fn;self.done=False;self.value=None
 def result(self,timeout=None):
  if not self.done:self.value=self.fn(timeout);self.done=True
  return self.value
class LocalClient:
 def __init__(self,role):self.role=role;self.download_files=False
 def predict(self,*args,api_name=None,**kwargs):return POOL.request(self.role,'call',api_name,args,kwargs,timeout=3000)['result']
 def submit(self,*args,api_name=None,**kwargs):return ImmediateJob(lambda timeout:POOL.request(self.role,'call',api_name,args,kwargs,timeout=timeout or 3000)['result'])
 def view_api(self,return_format='dict',print_info=False,**kwargs):return POOL.request(self.role,'describe')['result']
 def close(self):pass
