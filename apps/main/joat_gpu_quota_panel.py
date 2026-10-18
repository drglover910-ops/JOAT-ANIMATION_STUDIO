"""Owner-confirmed quota and conservative local reservations. File version1.0.1.
Does not read Hugging Face billing or claim a live provider balance. No GPU calls.
"""
FILE_VERSION='1.0.1'
import json,hashlib,uuid,math
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path('/studio/joat-studio/gpu-quota')
def now():return datetime.now(timezone.utc).isoformat()
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def checked_time(value):
 t=datetime.fromisoformat(value.replace('Z','+00:00'))
 if t.tzinfo is None:raise ValueError('Quota confirmation must include timezone.')
 return t

def write_once(path,value):
 path=Path(path)
 if any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('Invalid quota storage path.')
 path.parent.mkdir(parents=True,exist_ok=True)
 if path.exists():
  if json.loads(path.read_text())!=value:raise ValueError('Different quota record already retained.')
  return
 with path.open('x') as f:json.dump(value,f,indent=2)
def seal(value):value=dict(value);value['record_fingerprint']=digest(value);return value
def read(path):
 if path.is_symlink() or path.stat().st_size>32768:raise ValueError('Invalid quota record.')
 v=json.loads(path.read_text());core=dict(v);given=core.pop('record_fingerprint')
 if digest(core)!=given:raise ValueError('Quota record integrity failed.')
 return v

def save_confirmation(grant,root=ROOT):
 identifier=grant['report_id']
 if len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier):raise ValueError('Invalid report identifier.')
 value=seal(dict(schema='joat.quota_owner_report.v1',file_version=FILE_VERSION,report_id=identifier,owner='Dezz-9-10',confirmed_at=grant['confirmed_at'],remaining_seconds=grant['included_seconds_available'],total_seconds=grant['included_seconds_total'],source=grant['source'],owner_statement=grant['owner_statement'],provider_live_balance=False,gpu_called=False))
 checked_time(value['confirmed_at']);path=Path(root)/'reports'/(identifier+'.json')
 if path.exists():
  old=read(path)
  if any(old.get(k)!=value.get(k) for k in ('owner','report_id','confirmed_at','remaining_seconds','total_seconds','source','owner_statement')):raise ValueError('Quota confirmation differs from its retained source.')
  return old
 write_once(path,value);return value

def save_dashboard_report(report,root=ROOT):
 """Persist an explicit owner dashboard observation; never label it a live API read."""
 fields={'schema','file_version','report_id','owner','confirmed_at','display_mode','displayed_minutes','total_minutes','credits_balance_usd','inference_usage_display','owner_statement'}
 if not isinstance(report,dict) or set(report)!=fields or report['schema']!='joat.quota_dashboard_report.v1' or report['owner']!='Dezz-9-10' or report['file_version']!='1.0.0':raise ValueError('Exact owner dashboard report required.')
 identifier=report['report_id']
 if not isinstance(identifier,str) or len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier):raise ValueError('Invalid report identifier.')
 used,total,credits=report['displayed_minutes'],report['total_minutes'],report['credits_balance_usd']
 if any(type(v) not in (int,float) or not math.isfinite(v) for v in (used,total,credits)) or not 0<=used<=total<=1440 or total<=0 or not 0<=credits<=100000:raise ValueError('Invalid displayed usage or credit balance.')
 if report['display_mode'] not in ('used','remaining'):raise ValueError('Specify whether the counter shows used or remaining minutes.')
 if not isinstance(report['inference_usage_display'],str) or len(report['inference_usage_display'])>128 or not isinstance(report['owner_statement'],str) or not report['owner_statement'].strip() or len(report['owner_statement'])>4000:raise ValueError('Preserve bounded original dashboard labels.')
 stamp=checked_time(report['confirmed_at'])
 if (stamp-datetime.now(timezone.utc)).total_seconds()>30:raise ValueError('Quota report cannot be future-dated.')
 remaining=total-used if report['display_mode']=='used' else used
 value=seal(dict(schema='joat.quota_owner_report.v1',file_version=FILE_VERSION,report_id=identifier,owner='Dezz-9-10',confirmed_at=report['confirmed_at'],remaining_seconds=round(remaining*60),total_seconds=round(total*60),source='owner_chat_report',owner_statement=report['owner_statement'],dashboard_display={'mode':report['display_mode'],'minutes':used,'total_minutes':total},credits_balance_usd=credits,inference_usage_display=report['inference_usage_display'],credits_spending_authorized_usd=0,provider_live_balance=False,gpu_called=False))
 write_once(Path(root)/'reports'/(identifier+'.json'),value);return value

def start_dashboard_reports():
 """Privileged owner-staged CPU intake; no browser credentials or inference calls."""
 import os,threading
 for key,raw in list(os.environ.items()):
  if not key.startswith('JOAT_QUOTA_DASHBOARD_REPORT_'):continue
  def run(name=key,text=raw):
   try:
    import joat_managed_generation as m
    if os.environ.get('SPACE_ID')!='Dezz-9-10/J.O.A.T.-Main-Assistant-Bot' or len(text.encode())>8192:raise ValueError('Native bounded Main report required.')
    report=json.loads(text)
    if report.get('report_id')!=name.removeprefix('JOAT_QUOTA_DASHBOARD_REPORT_'):raise ValueError('Report identifier differs from staged owner input.')
    token=os.environ.get('JOAT_SPECIALIST_TOKEN','')
    if not token or m.HfApi(token=token).whoami().get('name')!='Dezz-9-10':raise ValueError('Existing owner service identity required.')
    m.mount_check('main');value=save_dashboard_report(report)
    print('JOAT_QUOTA_DASHBOARD '+json.dumps({'report_id':value['report_id'],'status':'owner_report_saved','provider_live_balance':False,'gpu_called':False}),flush=True)
   except Exception as exc:print('JOAT_QUOTA_DASHBOARD '+json.dumps({'status':'stopped_for_review','error_type':type(exc).__name__,'gpu_called':False}),flush=True)
  threading.Thread(target=run,daemon=True,name='joat-quota-owner-report').start()

def reserve(request,grant,root=ROOT):
 report=save_confirmation(grant,root);value=seal(dict(schema='joat.quota_local_reservation.v1',file_version=FILE_VERSION,request_id=request['request_id'],request_fingerprint=digest(request),report_id=report['report_id'],reserved_at=now(),ceiling_seconds=request['gpu_ceiling_seconds'],status='submitted_or_unknown',actual_provider_gpu_seconds=None,actual_provider_charge_usd=None,paid_spending_authorized_usd=0))
 path=Path(root)/'reservations'/(request['request_id']+'.json')
 if path.exists():raise ValueError('Reference quota is already reserved; inspect original request, no automatic retry.')
 write_once(path,value);return value

def state(root=ROOT):
 root=Path(root);reports=[read(p) for p in (root/'reports').glob('*.json')];latest=max(reports,key=lambda r:checked_time(r['confirmed_at'])) if reports else None
 reservations=[read(p) for p in (root/'reservations').glob('*.json')]
 active=[r for r in reservations if latest and checked_time(r['reserved_at'])>=checked_time(latest['confirmed_at'])]
 reserved=sum(r['ceiling_seconds'] for r in active)
 age=max(0,(datetime.now(timezone.utc)-checked_time(latest['confirmed_at'])).total_seconds()) if latest else None
 fresh=age is not None and age<=900
 return dict(schema='joat.quota_recorded_state.v1',file_version=FILE_VERSION,last_owner_confirmation=latest,report_age_seconds=age,report_fresh=fresh,refresh_required=not fresh,local_reserved_seconds=reserved,conservative_planning_seconds=max(0,latest['remaining_seconds']-reserved) if latest and fresh else None,reservations=reservations,credits_balance_usd=latest.get('credits_balance_usd') if latest else None,credits_spending_authorized_usd=0,provider_live_balance=False,browser_reader_connected=False,gpu_called=False,note='Owner-reported allowance minus tracked reference allocation ceilings, not a complete account-wide usage ledger. Other Spaces and untracked video calls may consume quota. No provider balance, reset timestamp or actual invoice is inferred. Reports older than15minutes cannot supply a current planning allowance; refresh reads saved records only.')

def add_quota_ui():
 import gradio as gr
 import joat_managed_generation as m
 from typing import Optional
 def refresh(profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
  m.owner_token(profile,oauth,request);v=state()
  last=v['last_owner_confirmation']
  if not last:return 'No confirmed quota recorded yet. Enter the remaining included minutes shown by Hugging Face.',v
  allowance=f"{v['conservative_planning_seconds']/60:g} minutes" if v['report_fresh'] else 'STALE — a fresh observation is required'
  credit=f"${v['credits_balance_usd']:.2f}" if v['credits_balance_usd'] is not None else 'not reported'
  text=f"Owner-reported: **{last['remaining_seconds']/60:g} of {last['total_seconds']/60:g} minutes remaining** ({last['confirmed_at']}).\n\nReported credits: **{credit}**. Paid spending authorized: **$0**.\n\nTracked reference reservations: **{v['local_reserved_seconds']/60:g} minutes**. Planning allowance: **{allowance}**.\n\nThis is recorded evidence, not a live account balance. Other Spaces and untracked video calls can consume quota. Refresh does not read the Hugging Face screen."
  return text,v
 def update(remaining:float,total:float,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
  m.owner_token(profile,oauth,request)
  if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (remaining,total)) or not 0<=remaining<=total<=1440 or total<=0:raise gr.Error('Enter the actual remaining and total included GPU minutes.')
  grant=dict(report_id=uuid.uuid4().hex,confirmed_at=now(),included_seconds_available=round(remaining*60),included_seconds_total=round(total*60),source='signed_in_owner_report',owner_statement='Owner entered the included quota displayed by Hugging Face.')
  m.mount_check('main');save_confirmation(grant);return refresh(profile,oauth,request)
 with gr.Tab('GPU Quota'):
  gr.Markdown('Track included GPU time. **This panel records your confirmation; it does not query Hugging Face billing or start a generation.**')
  gr.LoginButton();summary=gr.Markdown();detail=gr.JSON(label='Recorded usage evidence')
  remaining=gr.Number(label='Remaining included minutes shown by Hugging Face',value=None);total=gr.Number(label='Total daily included minutes',value=40)
  gr.Button('Save my confirmed quota — no GPU').click(update,[remaining,total],[summary,detail],api_name=False)
  gr.Button('Refresh recorded balance — no GPU').click(refresh,[],[summary,detail],api_name=False)
