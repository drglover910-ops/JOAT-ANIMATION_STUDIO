"""Owner-confirmed quota and conservative local reservations. File version1.0.0.
Does not read Hugging Face billing or claim a live provider balance. No GPU calls.
"""
FILE_VERSION='1.0.0'
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
 v=json.loads(path.read_text());core=dict(v);given=core.pop('record_fingerprint');assert digest(core)==given;return v

def save_confirmation(grant,root=ROOT):
 identifier=grant['report_id']
 if len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier):raise ValueError('Invalid report identifier.')
 value=seal(dict(schema='joat.quota_owner_report.v1',file_version=FILE_VERSION,report_id=identifier,owner='Dezz-9-10',confirmed_at=grant['confirmed_at'],remaining_seconds=grant['included_seconds_available'],total_seconds=grant['included_seconds_total'],source=grant['source'],owner_statement=grant['owner_statement'],provider_live_balance=False,gpu_called=False))
 checked_time(value['confirmed_at']);write_once(Path(root)/'reports'/(identifier+'.json'),value);return value

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
 return dict(schema='joat.quota_recorded_state.v1',file_version=FILE_VERSION,last_owner_confirmation=latest,local_reserved_seconds=reserved,conservative_planning_seconds=max(0,latest['remaining_seconds']-reserved) if latest else None,reservations=reservations,provider_live_balance=False,gpu_called=False,note='Owner-reported allowance minus local allocation ceilings. Other Spaces may consume quota. Actual GPU usage and charges are unknown unless the provider reports them. Refreshing reads saved records only.')

def add_quota_ui():
 import gradio as gr
 import joat_managed_generation as m
 from typing import Optional
 def refresh(profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
  m.owner_token(profile,oauth,request);v=state()
  last=v['last_owner_confirmation']
  if not last:return 'No confirmed quota recorded yet. Enter the remaining included minutes shown by Hugging Face.',v
  text=f"Last confirmed: **{last['remaining_seconds']/60:g} of {last['total_seconds']/60:g} minutes remaining** ({last['confirmed_at']}).\n\nLocal reservations: **{v['local_reserved_seconds']/60:g} minutes**. Conservative planning allowance: **{v['conservative_planning_seconds']/60:g} minutes**.\n\nThis is a recorded estimate, not a live Hugging Face balance. No additional paid spending is authorized."
  return text,v
 def update(remaining:float,total:float,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
  m.owner_token(profile,oauth,request)
  if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (remaining,total)) or not 0<=remaining<=total<=1440 or total<=0:raise gr.Error('Enter the actual remaining and total included GPU minutes.')
  grant=dict(report_id=uuid.uuid4().hex,confirmed_at=now(),included_seconds_available=round(remaining*60),included_seconds_total=round(total*60),source='signed_in_owner_report',owner_statement='Owner entered the included quota displayed by Hugging Face.')
  m.mount_check('main');save_confirmation(grant);return refresh(profile,oauth,request)
 with gr.Tab('GPU Quota'):
  gr.Markdown('Track included GPU time. **This panel records your confirmation; it does not query Hugging Face billing or start a generation.**')
  gr.LoginButton();summary=gr.Markdown();detail=gr.JSON(label='Recorded usage evidence')
  remaining=gr.Number(label='Remaining included minutes shown by Hugging Face',value=24.1);total=gr.Number(label='Total daily included minutes',value=40)
  gr.Button('Save my confirmed quota — no GPU').click(update,[remaining,total],[summary,detail],api_name=False)
  gr.Button('Refresh recorded balance — no GPU').click(refresh,[],[summary,detail],api_name=False)
