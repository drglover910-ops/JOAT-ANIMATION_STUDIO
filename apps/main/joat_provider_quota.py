"""Read documented account quota without scheduling GPU work. File version: 1.0.1."""
FILE_VERSION='1.0.1'
import json,math,os,re,threading,uuid
from datetime import datetime,timezone
from pathlib import Path
import httpx
from huggingface_hub import HfApi

ENDPOINT='https://huggingface.co/api/spaces/zero-gpu/quota'
OWNER='Dezz-9-10'
ROOT=Path('/studio/joat-studio/gpu-quota/provider-observations')

def read_quota(token,*,client=None):
    if not token:raise ValueError('Owner authentication required.')
    identity=HfApi(token=token).whoami();name=identity.get('name')
    if name!=OWNER:raise ValueError('Quota account differs from studio owner.')
    access=identity.get('auth',{}).get('accessToken',{});permissions=set()
    def collect(value):
        if isinstance(value,dict):
            for key,child in value.items():
                if key=='permissions' and isinstance(child,list):permissions.update(p for p in child if isinstance(p,str))
                else:collect(child)
        elif isinstance(value,list):
            for child in value:collect(child)
    collect(access.get('fineGrained',{}))
    label=str(access.get('displayName',''))[:120].replace(token,'[REDACTED]')
    label=re.sub(r'hf_[A-Za-z0-9]+','[REDACTED]',label)
    auth={'token_label':label,'token_role':access.get('role'),
          'billing_read_permission':access.get('role') in ('read','write') or 'user.billing.read' in permissions}
    result={'schema':'joat.provider_quota_observation.v1','file_version':FILE_VERSION,
            'observation_id':uuid.uuid4().hex,'owner':OWNER,
            'observed_at':datetime.now(timezone.utc).isoformat(),'endpoint':ENDPOINT,
            'provider_live_balance':False,'gpu_called':False,'credits_spending_authorized_usd':0,'auth_scope':auth}
    def fetch(c):return c.get(ENDPOINT,headers={'Authorization':'Bearer '+token},timeout=20,follow_redirects=False)
    if client is None:
        with httpx.Client() as c:response=fetch(c)
    else:response=fetch(client)
    result['http_status']=response.status_code
    if response.status_code!=200:
        return dict(result,status='account_quota_access_denied' if response.status_code in (401,403) else 'quota_unavailable',
                    remaining_seconds=None,total_seconds=None,reset_at=None)
    value=response.json()
    for key in ('base','current'):
        if type(value.get(key)) not in (int,float) or not math.isfinite(value[key]):raise ValueError('Unexpected quota response.')
    if not 0<=value['current']<=value['base']<=86400 or value['base']<=0:raise ValueError('Unexpected quota limits.')
    reset=value.get('resetsAt')
    if reset is not None:
        if not isinstance(reset,str) or datetime.fromisoformat(reset.replace('Z','+00:00')).tzinfo is None:raise ValueError('Invalid quota reset timestamp.')
    paid=value.get('overquotaUsed')
    if paid is not None and (type(paid) not in (int,float) or not math.isfinite(paid) or paid<0):raise ValueError('Invalid overquota observation.')
    return dict(result,status='provider_quota_verified',provider_live_balance=True,
                remaining_seconds=value['current'],total_seconds=value['base'],reset_at=reset,
                overquota_used_seconds=paid,credits_balance_usd=None)

def start_provider_checks():
    if os.environ.get('SPACE_ID')!='Dezz-9-10/J.O.A.T.-Main-Assistant-Bot':return
    for key,value in list(os.environ.items()):
        if not key.startswith('JOAT_PROVIDER_QUOTA_CHECK_') or value!=FILE_VERSION:continue
        identifier=key.removeprefix('JOAT_PROVIDER_QUOTA_CHECK_')
        if not re.fullmatch('[a-f0-9]{32}',identifier):continue
        def run(id=identifier):
            from joat_gpu_quota_panel import write_once,seal
            target=ROOT/id/'receipt.json'
            if target.exists():return
            receipt={'schema':'joat.provider_quota_access_check.v1','file_version':FILE_VERSION,
                     'check_id':id,'probes':[],'gpu_called':False,'automatic_retry':False}
            try:
                import joat_managed_generation as m
                m.mount_check('main');seen=set()
                for binding in ('JOAT_SPECIALIST_TOKEN','HF_TOKEN'):
                    token=os.environ.get(binding,'')
                    if not token or token in seen:continue
                    seen.add(token)
                    try:
                        result=read_quota(token)
                        receipt['probes'].append(dict(binding=binding,observation=result))
                        if result['provider_live_balance']:
                            write_once(ROOT/result['observation_id']/'observation.json',seal(result));break
                    except Exception as exc:receipt['probes'].append(dict(binding=binding,status='probe_failed',error_type=type(exc).__name__))
                receipt['status']='live_quota_available' if any(p.get('observation',{}).get('provider_live_balance') for p in receipt['probes']) else 'existing_credentials_cannot_read_quota'
            except Exception as exc:receipt.update(status='check_failed',error_type=type(exc).__name__)
            write_once(target,seal(receipt))
            print('JOAT_PROVIDER_QUOTA '+json.dumps({'check_id':id,'status':receipt['status'],'gpu_called':False}),flush=True)
        threading.Thread(target=run,daemon=True,name='joat-provider-quota-check').start()
