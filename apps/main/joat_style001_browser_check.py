"""Owner-browser preflight and one granted opening render. File version1.0.6.
Preflight uses no GPU. Rendering uses an existing exact one-attempt grant.
Platform-issued per-request delegation stays only in memory. No new grants/retries.
"""
FILE_VERSION = '1.0.6'
import json, uuid
from pathlib import Path
from typing import Optional
import gradio as gr
import joat_managed_generation as m
from joat_style001_opening_grant import PROJECT, JOB, SUPERVISOR, REVISED_PLAN

def browser_check(profile: Optional[gr.OAuthProfile], oauth: Optional[gr.OAuthToken], request: gr.Request):
    token = m.owner_token(profile, oauth, request)
    m.mount_check('main')
    from joat_remote_generation import source_for, prepared_path, signed, save_plan
    from gradio.context import LocalContext
    packet = source_for(PROJECT, JOB, SUPERVISOR)
    identifier = uuid.uuid4().hex
    directory = m.ROOT/'remote-generation'/'requests'/identifier
    envelope = dict(schema='joat.remote_generation_request.v1', file_version=FILE_VERSION,
                    request_id=identifier, operation='check', project_id=PROJECT,
                    source_job_fingerprint=JOB, source_supervisor_fingerprint=SUPERVISOR,
                    plan_fingerprint=REVISED_PLAN)
    m.write_once(directory/'request.json', envelope)
    context = LocalContext.request.set(request)
    try:
        plan_path = prepared_path(m.ROOT, packet, REVISED_PLAN)
        if not plan_path.exists():
            prepared = m.proxy('executive', 'prepare', signed(packet, 'prepare'), token)
            if prepared.get('plan_fingerprint') != REVISED_PLAN:
                raise ValueError('Prepared opening differs from the audited allocation-only plan.')
            save_plan(packet, prepared)
        plan = m.read_json(plan_path)['plan']
        if m.digest(plan) != REVISED_PLAN or plan['parameters']['gen_budget'] != 420:
            raise ValueError('The exact audited420second opening plan is unavailable.')
        result = m.proxy('executive', 'check', signed(packet, 'check', plan), token)
        if result.get('schema') != 'joat.render_connection_check.v1' or result.get('status') != 'passed' or result.get('gpu_called') is not False or result.get('source_job_fingerprint') != JOB:
            raise ValueError('Opening CPU preflight did not pass its exact source checks.')
        m.write_once(directory/'connection_check.json', result)
        receipt = dict(schema='joat.remote_generation_receipt.v1', file_version=FILE_VERSION,
                       request_id=identifier, operation='check', status='connection_passed',
                       plan_fingerprint=REVISED_PLAN, gpu_requested=False, automatic_retry=False)
        m.write_once(directory/'receipt.json', receipt)
        return 'Passed. The result is saved for Codex to read. No GPU generation started.', receipt
    except Exception as exc:
        receipt = dict(schema='joat.remote_generation_receipt.v1', file_version=FILE_VERSION,
                       request_id=identifier, operation='check', status='connection_failed',
                       error_type=type(exc).__name__, gpu_requested=False, automatic_retry=False)
        m.write_once(directory/'receipt.json', receipt)
        raise gr.Error('Opening connection check failed; its receipt is saved. No GPU generation requested. '+m.safe_validation_message(exc, token)) from None
    finally:
        LocalContext.request.reset(context)

def browser_render(profile: Optional[gr.OAuthProfile], oauth: Optional[gr.OAuthToken], request: gr.Request):
    m.owner_token(profile, oauth, request)
    m.mount_check('main')
    from joat_remote_generation import source_for, load_grant, run, PREFIX
    from gradio.context import LocalContext
    packet = source_for(PROJECT, JOB, SUPERVISOR)
    ledger = m.ROOT/'production-projects'/PROJECT/'opening-authorization'/REVISED_PLAN
    grant_path = ledger/'guard-fix-1.0.2'/'grant.json'
    grant = m.read_json(grant_path if grant_path.exists() else ledger/'grant.json')
    verified = load_grant(grant['grant_id'], packet, REVISED_PLAN)
    if verified['gpu_ceiling_seconds'] != 420:
        raise gr.Error('The exact420second opening authorization is unavailable.')
    # The grant ID is the execution ID. Every click reaches the same durable
    # attempt; an in-progress or unknown result is never submitted again.
    identifier = grant['grant_id']
    directory = m.ROOT/'remote-generation'/'requests'/identifier
    if not (directory/'request.json').exists():
        import os
        api = m.HfApi(token=os.environ.get('JOAT_SPECIALIST_TOKEN', ''))
        control = 'Dezz-9-10/J.O.A.T.-Executive-Producer-Bot'
        hold = api.get_space_variables(control).get('JOAT_STUDIO_GPU_HOLD')
        if hold is None or hold.value.lower() != 'false' or str(api.space_info(control).runtime.stage) != 'RUNNING':
            raise gr.Error('Director is not released and ready yet. No attempt was consumed; wait for Codex to finish readiness checks.')
    envelope = dict(schema='joat.remote_generation_request.v1', file_version=FILE_VERSION,
                    request_id=identifier, operation='execute', project_id=PROJECT,
                    source_job_fingerprint=JOB, source_supervisor_fingerprint=SUPERVISOR,
                    plan_fingerprint=REVISED_PLAN, grant_id=identifier)
    context = LocalContext.request.set(request)
    try:
        receipt = run(PREFIX+identifier, json.dumps(envelope))
    finally:
        LocalContext.request.reset(context)
    output = None
    outcome = None
    index_path = directory/'artifact_index.json'
    safe_terminal = receipt.get('status') == 'rejected' and receipt.get('gpu_requested') is False
    if index_path.exists():
        index = m.read_json(index_path)
        result_path = directory/'artifacts'/'generation_result.json'
        outcome = m.read_json(result_path) if result_path.exists() else None
        if outcome:
            safe_terminal = (outcome.get('schema') == 'joat.generation_result.v1' and outcome.get('status') == 'completed') or (outcome.get('submission_state') == 'not_submitted' and outcome.get('render_outcome') == 'not_submitted') or outcome.get('submission_state') == 'response_received' or outcome.get('error_message', '').startswith('You have exceeded your Pro ZeroGPU quota')
        entry = next((v for v in index.get('files', []) if v.get('filename') == 'output.mp4'), None)
        if entry:
            import tempfile, shutil
            video = m.safe_path(directory/'artifacts'/'output.mp4')
            if m.file_hash(video) != entry['sha256']:
                raise gr.Error('Saved opening media integrity differs; no new render requested.')
            target = Path(tempfile.mkdtemp(prefix='joat-style001-opening-'))/'STYLE001_OPENING_CANDIDATE.mp4'
            shutil.copyfile(video, target)
            output = str(target)
    # Restore the temporary GPU hold only after a known terminal outcome.
    # An uncertain submitted task remains untouched for status recovery.
    if safe_terminal and not (directory/'gpu_hold_restore.json').exists():
        import os
        try:
            api = m.HfApi(token=os.environ.get('JOAT_SPECIALIST_TOKEN', ''))
            if api.whoami().get('name') != m.OWNER:
                raise ValueError('Owner service credential required for hold restoration.')
            api.add_space_variable('Dezz-9-10/J.O.A.T.-Executive-Producer-Bot', key='JOAT_STUDIO_GPU_HOLD', value='true')
            m.write_once(directory/'gpu_hold_restore.json', dict(file_version=FILE_VERSION, restored=True, gpu_called=False))
        except Exception:
            # Preserve a successful video even if the separate Hub setting call
            # fails. Codex can inspect this record and restore the hold directly.
            m.write_once(directory/'gpu_hold_restore.json', dict(file_version=FILE_VERSION, restored=False, requires_operator_review=True, gpu_called=False))
    note = 'Opening candidate saved. Final visual/audio QC is still required.' if output else 'Attempt status saved: '+str(receipt.get('status'))+'. No automatic retry.'
    return note, dict(receipt=receipt, generation_result=outcome), output, output



FAILED_GUARD_ATTEMPT = 'aa86c063a9a44153bfd5d0cf8165ee01'
FAILED_GUARD_MESSAGE = 'Preserve the current reviewed duration and600-second allocation ceiling; new limits need qualification.'

def browser_render_corrected(profile: Optional[gr.OAuthProfile], oauth: Optional[gr.OAuthToken], request: gr.Request):
    """An explicit owner click replaces only the proven pre-submission failure.
    No startup/automatic retry, no uncertain-job recovery, one immutable replacement.
    """
    m.owner_token(profile, oauth, request)
    m.mount_check('main')
    from joat_remote_generation import source_for, prepared_path, grant as issue_grant
    ledger = m.ROOT/'production-projects'/PROJECT/'opening-authorization'/REVISED_PLAN
    recovery = ledger/'guard-fix-1.0.2'
    if not (recovery/'grant.json').exists():
        old = m.ROOT/'remote-generation'/'requests'/FAILED_GUARD_ATTEMPT
        previous_request = m.read_json(old/'request.json')
        result_path = old/'artifacts'/'generation_result.json'
        outcome = m.read_json(result_path)
        index = m.read_json(old/'artifact_index.json')
        entries = [v for v in index.get('files', []) if v.get('filename') == 'generation_result.json']
        if len(entries) != 1 or entries[0]['sha256'] != m.file_hash(result_path):
            raise gr.Error('Prior failure evidence failed integrity checks; no new authorization issued.')
        if previous_request.get('request_id') != FAILED_GUARD_ATTEMPT or previous_request.get('grant_id') != FAILED_GUARD_ATTEMPT or previous_request.get('plan_fingerprint') != REVISED_PLAN or outcome.get('source_job_fingerprint') != JOB or outcome.get('schema') != 'joat.render_failure.v1' or outcome.get('status') != 'render_failed' or outcome.get('stage') != 'validate_locked_plan' or outcome.get('submission_state') != 'not_submitted' or outcome.get('render_outcome') != 'not_submitted' or outcome.get('error_type') != 'ValueError' or outcome.get('error_message') != FAILED_GUARD_MESSAGE:
            raise gr.Error('Only this confirmed pre-submission guard failure can be replaced. No retry authorized.')
        import os
        api = m.HfApi(token=os.environ.get('JOAT_SPECIALIST_TOKEN', ''))
        control = 'Dezz-9-10/J.O.A.T.-Executive-Producer-Bot'
        hold = api.get_space_variables(control).get('JOAT_STUDIO_GPU_HOLD')
        if hold is None or hold.value.lower() != 'false' or str(api.space_info(control).runtime.stage) != 'RUNNING':
            raise gr.Error('Director is not released and ready. No replacement attempt was consumed.')
        packet = source_for(PROJECT, JOB, SUPERVISOR)
        plan = m.read_json(prepared_path(m.ROOT, packet, REVISED_PLAN))['plan']
        if m.digest(plan) != REVISED_PLAN or plan['parameters']['gen_budget'] != 420:
            raise gr.Error('Exact approved420second plan required.')
        # Exclusive reservation remains if issuance crashes. Never mint another grant.
        m.write_once(recovery/'reservation.json', dict(file_version=FILE_VERSION, owner=m.OWNER, authorization='explicit_owner_browser_click', supersedes_not_submitted_attempt=FAILED_GUARD_ATTEMPT, prior_failure_sha256=entries[0]['sha256'], plan_fingerprint=REVISED_PLAN, maximum_render_attempts=1, automatic_retry=False, credit_purchase_authorized=False))
        issued = issue_grant(packet, plan, True)
        m.write_once(recovery/'grant.json', issued)
    return browser_render(profile, oauth, request)



def browser_view_saved(profile: Optional[gr.OAuthProfile], oauth: Optional[gr.OAuthToken], request: gr.Request):
    m.owner_token(profile, oauth, request)
    m.mount_check('main')
    ledger = m.ROOT/'production-projects'/PROJECT/'opening-authorization'/REVISED_PLAN/'guard-fix-1.0.2'
    grant = m.read_json(ledger/'grant.json')
    directory = m.ROOT/'remote-generation'/'requests'/grant['grant_id']
    receipt = m.read_json(directory/'receipt.json')
    if receipt.get('status') != 'completed' or receipt.get('plan_fingerprint') != REVISED_PLAN:
        raise gr.Error('The completed opening is unavailable. No generation requested.')
    return browser_render(profile, oauth, request)


def add_ui():
    with gr.Accordion('Style001 Opening', open=True):
        gr.Markdown('**Opening rendered; creative QC needs corrections.** This saved candidate has an abrupt cut and unintended spoken production instructions. The prompt correction is prepared; another GPU attempt requires separate approval. View or download this candidate below. This button retrieves the saved result and never starts a new attempt.')
        gr.LoginButton()
        render_note = gr.Markdown()
        render_result = gr.JSON(label='Opening render result — awaiting QC')
        video = gr.Video(label='Opening candidate — awaiting visual/audio QC')
        download = gr.File(label='Download opening MP4')
        gr.Button('View saved opening — corrections needed', variant='primary').click(browser_view_saved, [], [render_note, render_result, video, download], api_visibility='private', concurrency_limit=1, trigger_mode='once')
        with gr.Accordion('Connection diagnostics — no GPU', open=False):
            gr.Markdown('Optional connection diagnostic. The approved opening already passed this check; this button does not render a video.')
            note = gr.Markdown()
            evidence = gr.JSON(label='Saved opening connection receipt — no GPU')
            gr.Button('Check approved opening connection — no GPU').click(browser_check, [], [note, evidence], api_visibility='private', concurrency_limit=1, trigger_mode='once')
