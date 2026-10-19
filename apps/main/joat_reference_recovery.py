"""Reconcile only a terminal reference failure proven to precede GPU work.
File version: 1.0.2. Preserve original failure and archived reservation evidence.
"""
FILE_VERSION='1.0.2'
import json,re
from pathlib import Path
import joat_managed_generation as m

def release(project,payload):
 if set(payload)!={'failed_task_id','reference_request_id'}:raise ValueError('Exact failed-task and reference identifiers required.')
 for value in payload.values():
  if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{32}',value):raise ValueError('Invalid recovery identifier.')
 from joat_reference_supplement import registry,digest
 entries=[x for x in registry()['requests'] if x['request']['request_id']==payload['reference_request_id']]
 if len(entries)!=1 or registry()['project_id']!=project:raise ValueError('Recovery must match an exact supplemental reference.')
 request=entries[0]['request'];root=m.safe_path(m.ROOT/'production-projects'/project)
 receipt=m.read_json(root/'tasks'/payload['failed_task_id']/'receipt.json')
 pre_mount=(receipt.get('stage')=='frame_'+request['asset_key'] and receipt.get('error_type')=='AppError')
 pre_dispatch=(receipt.get('stage')=='reference_api_connection' and receipt.get('error_type')=='ValueError' and receipt.get('safe_error_message')=='Different quota record already retained.')
 if receipt.get('request_id')!=payload['failed_task_id'] or receipt.get('status')!='failed_or_unknown' or not (pre_mount or pre_dispatch):raise ValueError('An explicit terminal pre-GPU failure is required.')
 # The Reference Lab persists its reservation before source loading or GPU allocation.
 # A terminal response plus absence of that reservation proves this call never reached GPU work.
 remote=m.safe_path(root/'references'/request['asset_key']/request['request_id'])
 if remote.exists():raise ValueError('Reference-side execution evidence exists; cannot release or retry.')
 from joat_gpu_quota_panel import ROOT,read,write_once,seal
 folder=m.safe_path(ROOT/'live-reference-reservations'/request['request_id']);archive=folder/'pre_gpu_failure_reconciliation.json';source=folder/'reservation.json'
 if archive.exists() and read(archive).get('failed_task_id')!=payload['failed_task_id']:
  archive=folder/'pre_gpu_failures'/(payload['failed_task_id']+'.json')
 if archive.exists():
  stored=read(archive)
  if stored.get('failed_task_id')!=payload['failed_task_id']:raise ValueError('Recovery differs from original terminal failure.')
  if source.exists():raise ValueError('Reservation exists after reconciliation; inspect instead of releasing again.')
  return dict(status='pre_gpu_failure_already_reconciled',gpu_called=False)
 reservation=read(source)
 if reservation.get('request_id')!=request['request_id'] or reservation.get('request_fingerprint')!=digest(request):raise ValueError('Reservation differs from exact source.')
 evidence=seal(dict(schema='joat.pre_gpu_failure_reconciliation.v1',file_version=FILE_VERSION,project_id=project,failed_task_id=payload['failed_task_id'],reference_request_id=request['request_id'],original_reservation=reservation,terminal_failure=receipt,reference_side_directory_absent=True,gpu_called=False,paid_authority_usd=0))
 write_once(archive,evidence)
 if read(archive)!=evidence or read(source)!=reservation or remote.exists():raise ValueError('Recovery evidence changed; keep the reservation.')
 source.unlink()
 return dict(status='pre_gpu_failure_reconciled',gpu_called=False,original_failure_retained=True,reservation_archived=True)
