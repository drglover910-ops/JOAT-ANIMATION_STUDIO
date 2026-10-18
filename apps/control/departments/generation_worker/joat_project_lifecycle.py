"""Durable owner project cancellation; preserves assets and diagnostic evidence.
Embedded file version 1.0.0. No deletion, inference or automatic resume.
"""
FILE_VERSION='1.0.0'
import json,hashlib,re
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path('/studio/joat-studio')
def fingerprint(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def location(project,root):
    if not isinstance(project,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,127}',project):raise ValueError('Invalid project ID.')
    p=Path(root)/'production-projects'/project/'cancellation.json'
    if any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('Project lifecycle symlink denied.')
    return p
def cancelled(project,root=ROOT):
    p=location(project,root)
    if not p.exists():return None
    if not p.is_file() or p.stat().st_size>32768:raise ValueError('Invalid project cancellation record.')
    v=json.loads(p.read_text());core={k:x for k,x in v.items() if k!='cancellation_fingerprint'}
    if v.get('schema')!='joat.project_cancellation.v1' or v.get('project_id')!=project or v.get('owner')!='Dezz-9-10' or v.get('status')!='cancelled' or fingerprint(core)!=v.get('cancellation_fingerprint'):raise ValueError('Project cancellation integrity failed.')
    return v
def assert_active(project,root=ROOT):
    if cancelled(project,root) is not None:raise ValueError('This project is cancelled. Existing assets remain archived; use a new project for generation.')
def cancel(project,owner,statement,root=ROOT):
    if owner!='Dezz-9-10' or not isinstance(statement,str) or not 1<=len(statement)<=4000:raise ValueError('Explicit owner cancellation required.')
    old=cancelled(project,root)
    if old:return old
    v=dict(schema='joat.project_cancellation.v1',file_version=FILE_VERSION,project_id=project,owner=owner,status='cancelled',owner_statement=statement,cancelled_at=datetime.now(timezone.utc).isoformat(),existing_assets_preserved=True,automatic_resume=False,gpu_called=False)
    v['cancellation_fingerprint']=fingerprint(v);p=location(project,root);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(v,f,indent=2)
    if cancelled(project,root)!=v:raise ValueError('Cancellation readback differs.')
    return v
