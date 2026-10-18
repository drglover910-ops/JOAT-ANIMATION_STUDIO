"""Owner-reviewed Main→Executive signed CPU department handoff. File version 1.0.8.
Uses the existing Executive dispatch contract. No GPU/media execution route.
"""
FILE_VERSION = '1.0.8'
# Keep the existing immutable plan serialization so completed handoffs are reused.
PLAN_VERSION = '1.0.3'
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import time
from typing import Optional
import urllib.request
import uuid

import gradio as gr
from gradio_client import Client
from joat_production_ui import require_owner, login

MAIN = 'J.O.A.T. Main Assistant Bot'
EXECUTIVE = 'J.O.A.T. Executive Producer Bot'
SPACE = 'Dezz-9-10/J.O.A.T.-Executive-Producer-Bot'
BUCKET = 'Dezz-9-10/J.O.A.T.-Studio-storage'
ROOT = Path('/studio/joat-studio')
ROUTES = {
    'character': ('/packet', 'J.O.A.T.-Character-Asset-Master'),
    'environment': ('/build_packet_ui', 'J.O.A.T.-Scene-Environment-Master'),
    'director': ('/generate_director_ui', 'J.O.A.T.-Director-Creative-Intelligence'),
    'shot_camera': ('/build_packet_ui', 'J.O.A.T.-Shot-Camera-Master'),
    'performance_action': ('/build_packet_ui', 'J.O.A.T.-Performance-Action-Master'),
    'generation_supervisor': ('/build_job_ui', 'J.O.A.T.-Generation-Supervisor-Master'),
    'post_production': ('/build_packet_ui', 'J.O.A.T.-Post-Production-Supervisor-Bot'),
}
LOCK = threading.Lock()


def stable(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def seal(value, key):
    unsigned = dict(value); unsigned.pop(key, None)
    return dict(unsigned, **{key: hashlib.sha256(stable(unsigned).encode()).hexdigest()})


def verify(value, key):
    if not isinstance(value, dict) or value.get(key) != seal(value, key)[key]:
        raise ValueError('Invalid ' + key)


def prepare(project_id, role, arguments):
    if not isinstance(project_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', project_id):
        raise ValueError('Use one valid project ID.')
    if role not in ROUTES:
        raise ValueError('Only approved CPU Master/Supervisor routes are allowed.')
    if isinstance(arguments, str):
        if len(arguments.encode()) > 2 * 1024 * 1024:
            raise ValueError('Department arguments exceed 2 MB.')
        arguments = json.loads(arguments)
    if not isinstance(arguments, dict):
        raise ValueError('Department arguments must be a JSON object of exact API parameters.')
    if set(arguments) & {'api_name', 'fn_index', 'result_callbacks'}:
        raise ValueError('Department arguments cannot override the approved client route.')
    # Round-trip creates an immutable JSON-compatible snapshot.
    arguments = json.loads(stable(arguments))
    def check_context(value, depth=0, path=()):
        if depth > 40:
            raise ValueError('Department arguments are too deeply nested.')
        if isinstance(value, dict):
            # Native Performance provenance leaves canonical, reusable assets projectless.
            projectless_asset_reference = (len(path) >= 2 and path[-2] == 'upstream_references' and path[-1] in ('character', 'environment') and value.get('project_id') is None)
            if 'project_id' in value and value['project_id'] != project_id and not projectless_asset_reference:
                raise ValueError('Department arguments belong to another production project.')
            for key, item in value.items():
                if key.lower() in {'token', 'hf_token', 'access_token', 'oauth_token', 'api_key', 'password', 'secret', 'authorization', 'signing_key'}:
                    raise ValueError('Credentials must stay in secure Settings, not department arguments.')
                check_context(item, depth + 1, path + (key,))
        elif isinstance(value, list):
            for item in value: check_context(item, depth + 1, path + ("[]",))
        elif isinstance(value, str) and value.lstrip().startswith(('{', '[')):
            try: parsed = json.loads(value)
            except ValueError: return
            check_context(parsed, depth + 1, path)
    check_context(arguments)
    return seal({'schema': 'joat.executive_handoff_plan.v1', 'file_version': PLAN_VERSION,
                 'project_id': project_id, 'department_role': role,
                 'endpoint': ROUTES[role][0], 'expected_space': 'Dezz-9-10/' + ROUTES[role][1],
                 'arguments': arguments, 'gpu_called': False, 'automatic_retry': False,
                 'production_work_completed': False}, 'plan_fingerprint')


def readiness():
    return {'schema': 'joat.executive_handoff_readiness.v1', 'file_version': FILE_VERSION,
            'signing_key_present': len(os.environ.get('JOAT_DISPATCH_SIGNING_KEY', '')) >= 32,
            'specialist_token_present': bool(os.environ.get('JOAT_SPECIALIST_TOKEN', '')),
            'studio_mount_directory_present': Path('/studio').is_dir(),
            'secret_values_exposed': False, 'gpu_called': False,
            'note': 'Presence only. A signed preview and owner-approved live dispatch must still succeed.'}


def require_studio_mount():
    if os.environ.get('SPACE_ID') != 'Dezz-9-10/J.O.A.T.-Main-Assistant-Bot':
        raise ValueError('Run this owner handoff from the Main Assistant Space.')
    with urllib.request.urlopen('https://huggingface.co/api/spaces/Dezz-9-10/J.O.A.T.-Main-Assistant-Bot', timeout=30) as response:
        metadata = json.load(response)
    if not any(v.get('source') == BUCKET and v.get('mountPath') == '/studio' and v.get('readOnly') is False
               for v in metadata.get('runtime', {}).get('volumes', [])) or not Path('/studio').is_dir():
        raise ValueError('The private studio bucket must be mounted at /studio with read/write access.')


def signed_request(plan, live):
    verify(plan, 'plan_fingerprint')
    expected = prepare(plan['project_id'], plan['department_role'], plan['arguments'])
    if expected != plan:
        raise ValueError('Prepared handoff does not match the approved route and arguments.')
    secret = os.environ.get('JOAT_DISPATCH_SIGNING_KEY', '')
    if len(secret) < 32:
        raise ValueError('Main needs the existing Executive JOAT_DISPATCH_SIGNING_KEY in its secure Settings. Do not reset it or paste it into chat.')
    value = {'schema': 'joat.executive_producer_dispatch.v1', 'source_bot': MAIN,
             'target_bot': EXECUTIVE, 'authorized': True,
             'work_order_id': 'WO-' + str(uuid.uuid4()), 'project_id': plan['project_id'],
             'department_role': plan['department_role'], 'endpoint': plan['endpoint'],
             'arguments': plan['arguments'], 'nonce': uuid.uuid4().hex,
             'issued_at_epoch': time.time(), 'execute_live': live}
    value['signature'] = hmac.new(secret.encode(), stable(value).encode(), hashlib.sha256).hexdigest()
    return value


def create_client():
    token = os.environ.get('JOAT_SPECIALIST_TOKEN', '')
    if not token:
        raise ValueError('Existing JOAT_SPECIALIST_TOKEN is unavailable; no request was sent.')
    from joat_control_contract import create, HOST
    from gradio.context import LocalContext
    headers={'Authorization':'Bearer '+token}
    incoming=LocalContext.request.get(None)
    delegation=incoming.headers.get('x-ip-token') if incoming is not None else None
    if isinstance(delegation,str) and 0<len(delegation)<=8192:headers['x-ip-token']=delegation
    return create(HOST,token,headers,False)


def _preview_failure(exc, stage, request_made):
    # Exception text is inspected only for fixed server-validation messages;
    # neither arbitrary messages nor URLs/headers/signatures are returned.
    text = str(exc)
    known = {
        'Dispatch signature invalid.': ('signature_mismatch', 'Main and Executive signing keys may differ. Preserve Executive secrets; reconcile the existing secure bindings.'),
        'Dispatch signing key is not configured securely.': ('executive_signing_key_unavailable', 'Executive has no usable signing key. Check its secure configuration without exposing values.'),
        'Dispatch authorization expired or timestamp invalid.': ('signature_timestamp_rejected', 'The signed request timestamp was rejected. Check request latency and server clocks.'),
        'Dispatch source must be Main Assistant.': ('source_contract_rejected', 'Executive rejected the configured source identity.'),
        'Dispatch target must be Executive Producer.': ('target_contract_rejected', 'Executive rejected the configured target identity.'),
        'Endpoint does not match approved department route.': ('department_route_rejected', 'Executive rejected the endpoint for this department.'),
    }
    code, note = 'unclassified_preview_failure', 'Safe diagnostics only. No department execution was requested.'
    for message, detail in known.items():
        if message in text:
            code, note = detail
            break
    http_status = getattr(getattr(exc, 'response', None), 'status_code', None) or getattr(exc, 'code', None)
    if code == 'unclassified_preview_failure':
        if http_status == 429 or type(exc).__name__ == 'TooManyRequestsError':
            code, note = 'rate_limited', 'The connection was rate limited. No automatic retry and no department execution.'
        elif http_status in (401, 403):
            code, note = 'credential_or_access_rejected', 'The transport credential or Space access was rejected. Check existing credential permissions securely.'
        elif 'timeout' in type(exc).__name__.lower():
            code, note = 'connection_timeout', 'The preview connection timed out. No department execution was requested.'
        elif stage == 'connect_executive':
            code, note = 'executive_connection_unavailable', 'The client could not connect to Executive. Check its runtime and connection before another preview.'
        else:
            code, note = 'executive_preview_rejected', 'Executive did not return a validated preview. Error class is shown; no raw credential-bearing exception is exposed.'
    report = {'schema': 'joat.executive_handoff_preview_failure.v1', 'file_version': FILE_VERSION,
              'status': 'signed_preview_failed', 'stage': stage, 'error_code': code,
              'error_type': type(exc).__name__, 'request_made': request_made,
              'department_execution_requested': False, 'gpu_called': False,
              'automatic_retry': False, 'secret_values_exposed': False, 'note': note}
    if isinstance(http_status, int): report['http_status'] = http_status
    return report


def check_signed_preview(plan, client_factory=create_client):
    request = signed_request(plan, False)
    try: client = client_factory()
    except Exception as exc: return _preview_failure(exc, 'connect_executive', False)
    try: response = client.predict(stable(request), api_name='/dispatch_department')
    except Exception as exc: return _preview_failure(exc, 'executive_signed_preview', True)
    if (not isinstance(response, dict) or response.get('schema') != 'joat.executive_producer_dispatch_result.v1'
            or response.get('status') != 'validated_preview_only'
            or response.get('work_order_id') != request['work_order_id']
            or response.get('project_id') != plan['project_id']
            or response.get('department_role') != plan['department_role']
            or response.get('endpoint') != plan['endpoint']
            or response.get('downstream_execution_performed') is not False):
        raise ValueError('Executive did not validate this exact signed preview.')
    return dict(response, gpu_called=False, file_version=FILE_VERSION)


def _write_once(path, value):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Checkpoint path cannot contain symlinks.')
    path.parent.mkdir(parents=True, exist_ok=True)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Checkpoint path cannot contain symlinks.')
    raw=(json.dumps(value,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode()
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    if path.read_bytes() != raw:
        raise ValueError('Checkpoint readback failed.')


def execute(plan, approved, root=ROOT, mount_validator=require_studio_mount, client_factory=create_client, recovery_parent=None):
    if approved is not True:
        raise ValueError('Explicit owner approval of this exact prepared handoff is required.')
    request = signed_request(plan, True)
    mount_validator()
    directory = Path(root)/'missions'/plan['project_id']/'executive-handoffs'/plan['plan_fingerprint']
    if recovery_parent is not None:
        stored = read_checkpoint(plan, root=root, mount_validator=mount_validator)
        if stored != recovery_parent or not recoverable_unsubmitted_environment(stored):
            raise ValueError('Recovery is limited to the exact stored Environment failure confirmed before packet creation.')
        directory = directory/'connection-recovery'
    # Reserve before creating the network client. An uncertain call is never
    # automatically submitted twice, including after a process/Space restart.
    with LOCK:
        try: _write_once(directory/'reservation.json', {'schema':'joat.executive_handoff_reservation.v1',
                            'file_version':FILE_VERSION,'plan':plan,'work_order_id':request['work_order_id'],
                            'created_at_epoch':time.time(),'automatic_retry':False})
        except FileExistsError:
            raise ValueError('This exact handoff already has an attempt. Review its stored receipt; no repeat request was sent.') from None
    receipt={'schema':'joat.executive_handoff_receipt.v1','file_version':FILE_VERSION,
             'project_id':plan['project_id'],'plan_fingerprint':plan['plan_fingerprint'],
             'work_order_id':request['work_order_id'],'department_role':plan['department_role'],
             'gpu_called':False,'automatic_retry':False,'production_work_completed':False,
             'request_made':False,'status':'not_submitted','checkpoint_uri':
             'hf://buckets/'+BUCKET+'/joat-studio/missions/'+plan['project_id']+'/executive-handoffs/'+plan['plan_fingerprint']+'/receipt.json'}
    if recovery_parent is not None:
        receipt['recovery_of_receipt_fingerprint'] = recovery_parent['receipt_fingerprint']
        receipt['recovery_reason'] = 'confirmed_environment_failure_before_packet_creation'
        receipt['checkpoint_uri'] = 'hf://buckets/'+BUCKET+'/joat-studio/'+str(directory.relative_to(Path(root)))+'/receipt.json'
    try:
        client=client_factory()
        receipt['request_made']=True
        response=client.predict(stable(request),api_name='/dispatch_department')
        receipt['executive_response']=response
        verify(response,'result_fingerprint')
        if (response.get('schema')!='joat.executive_producer_dispatch_result.v1'
                or response.get('work_order_id')!=request['work_order_id']
                or response.get('project_id')!=plan['project_id']
                or response.get('department_role')!=plan['department_role']
                or response.get('endpoint')!=plan['endpoint']
                or response.get('repo_id')!=plan['expected_space']):
            raise ValueError('Executive response does not match the approved work order, project or route.')
        if response.get('status')=='api_call_returned' and response.get('downstream_execution_performed') is True:
            if 'department_response' not in response:
                raise ValueError('Executive returned no department artifact.')
            # Transport return alone is not creative approval or media completion.
            receipt.update(status='department_api_returned',department_artifact=response['department_response'],
                           department_validation_required=True,creative_qc_approved=False)
        else:
            receipt.update(status='failed_or_outcome_unknown',manual_reconciliation_required=True)
    except Exception as exc:
        # Keep diagnostic class, not arbitrary exception text that could contain
        # headers/credentials. Preserve any returned structured Executive receipt.
        receipt.update(status='failed_or_outcome_unknown' if receipt['request_made'] else 'not_submitted',
                       error_type=type(exc).__name__,manual_reconciliation_required=True)
    receipt=seal(receipt,'receipt_fingerprint')
    _write_once(directory/'receipt.json',receipt)
    return receipt


def read_checkpoint(plan, root=ROOT, mount_validator=require_studio_mount, recovery=False):
    verify(plan, 'plan_fingerprint')
    if prepare(plan['project_id'], plan['department_role'], plan['arguments']) != plan:
        raise ValueError('Invalid prepared handoff.')
    mount_validator()
    path = Path(root)/'missions'/plan['project_id']/'executive-handoffs'/plan['plan_fingerprint']/'receipt.json'
    if recovery:
        path = path.parent/'connection-recovery'/'receipt.json'
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Checkpoint path cannot contain symlinks.')
    if not path.is_file():
        raise ValueError('No receipt is available. If an attempt was reserved, reconcile its outcome before any new submission.')
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError('Oversized handoff receipt.')
    receipt = json.loads(path.read_text())
    verify(receipt, 'receipt_fingerprint')
    if receipt.get('plan_fingerprint') != plan['plan_fingerprint'] or receipt.get('project_id') != plan['project_id']:
        raise ValueError('Stored receipt does not match this prepared handoff.')
    return receipt


def add_executive_handoff_ui(audit=None):
    def status(profile: Optional[gr.OAuthProfile], request: gr.Request):
        require_owner(profile,request)
        return readiness()
    def plan_ui(project, role, raw, profile: Optional[gr.OAuthProfile], request: gr.Request):
        require_owner(profile,request)
        try: plan=prepare(project,role,raw)
        except (ValueError,TypeError) as exc: raise gr.Error(str(exc)) from None
        return plan,plan,False
    def preview(plan, profile: Optional[gr.OAuthProfile], request: gr.Request):
        require_owner(profile,request)
        try:return check_signed_preview(plan)
        except (ValueError,TypeError) as exc:raise gr.Error(str(exc)) from None
        except Exception:raise gr.Error('Signed preview connection failed; no department execution requested.') from None
    def run(plan, approved, profile: Optional[gr.OAuthProfile], request: gr.Request):
        require_owner(profile,request)
        try:receipt=execute(plan,approved)
        except (ValueError,TypeError) as exc:raise gr.Error(str(exc)) from None
        except Exception:raise gr.Error('Checkpoint/connection failed. Review existing checkpoint before another attempt.') from None
        if audit:audit('executive_department_handoff',{'project_id':receipt['project_id'],'receipt_fingerprint':receipt['receipt_fingerprint'],'status':receipt['status']})
        directory=Path(tempfile.mkdtemp(prefix='joat-executive-handoff-'))
        file=directory/'executive_handoff_receipt.json';file.write_text(json.dumps(receipt,indent=2))
        return receipt,str(file)
    def restore(plan, profile: Optional[gr.OAuthProfile], request: gr.Request):
        require_owner(profile,request)
        try:receipt=read_checkpoint(plan)
        except (ValueError,TypeError) as exc:raise gr.Error(str(exc)) from None
        except Exception:raise gr.Error('Checkpoint read failed; no department call was made.') from None
        directory=Path(tempfile.mkdtemp(prefix='joat-executive-readback-'))
        file=directory/'executive_handoff_receipt.json';file.write_text(json.dumps(receipt,indent=2))
        return receipt,str(file)
    with gr.Tab('Executive Department Handoff'):
        login()
        gr.Markdown('Owner-reviewed CPU packet handoff through Executive Producer. Existing signed security and supervisor routing remain required. Returned packets still need department validation and creative review; this does not render video or approve QC.')
        ready=gr.JSON(label='Connection requirements (secret values hidden)')
        gr.Button('Check connection requirements (no department call)').click(status,outputs=ready,api_visibility='private')
        project=gr.Textbox(label='Production project ID',value='PROJECT-001')
        role=gr.Dropdown(choices=list(ROUTES),value='character',label='Master or Supervisor department')
        raw=gr.Code(value='{}',language='json',label='Exact approved department API arguments JSON')
        retained=gr.State(None);shown=gr.JSON(label='Exact prepared handoff')
        confirmation=gr.Checkbox(label='I reviewed and approve this exact CPU department handoff',value=False)
        gr.Button('Prepare exact handoff (no department call)').click(plan_ui,[project,role,raw],[shown,retained,confirmation],api_visibility='private')
        checked=gr.JSON(label='Executive signed preview')
        gr.Button('Check signed preview (no department call)').click(preview,[retained],checked,api_visibility='private')
        receipt=gr.JSON(label='Department handoff receipt; not production QC')
        download=gr.File(label='Download executive_handoff_receipt.json')
        gr.Button('Send approved handoff through Executive Producer').click(run,[retained,confirmation],[receipt,download],api_visibility='private',concurrency_limit=1)
        gr.Button('Read existing handoff receipt (no department call)').click(restore,[retained],[receipt,download],api_visibility='private')
        for component in (project,role,raw):
            component.change(lambda:(None,None,False),outputs=[retained,shown,confirmation],api_visibility='private')


def recoverable_unsubmitted_environment(receipt):
 try:
  verify(receipt,'receipt_fingerprint')
  if (receipt.get('schema')=='joat.executive_handoff_receipt.v1'
      and receipt.get('department_role')=='environment'
      and receipt.get('status')=='not_submitted'
      and receipt.get('request_made') is False
      and receipt.get('gpu_called') is False
      and receipt.get('error_type')=='TooManyRequestsError'
      and isinstance(receipt.get('work_order_id'),str)
      and receipt['work_order_id'].startswith('WO-')):return True
  response=receipt['executive_response'];verify(response,'result_fingerprint')
  return (receipt.get('department_role')=='environment' and receipt.get('status')=='failed_or_outcome_unknown'
          and response.get('department_role')=='environment' and response.get('endpoint')=='/build_packet_ui'
          and response.get('work_order_id')==receipt.get('work_order_id')
          and response.get('project_id')==receipt.get('project_id')
          and response.get('status')=='dispatch_failed_or_outcome_unknown'
          and response.get('downstream_execution_performed') is False
          and ((response.get('error_type')=='ValueError'
                and str(response.get('error','')).startswith('Could not fetch config for https://'))
               or (response.get('error_type')=='AppError'
                   and response.get('error')=='Verified owner required for project environments.'
                   and response.get('endpoint_phase')=='predict'
                   and response.get('repo_id')=='Dezz-9-10/J.O.A.T.-Scene-Environment-Master'
                   and response.get('production_work_completed') is False)))
 except (ValueError,KeyError,TypeError):return False
