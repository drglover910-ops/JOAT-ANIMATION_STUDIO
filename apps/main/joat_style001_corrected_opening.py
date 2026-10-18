"""Approved original-story opening after native-audio QC correction. File version1.0.0.
Owner-browser action only: exact CPU prepare/check, one durable grant, one render.
No startup execution, automatic retry, credit purchase, or creative/QC approval.
"""
FILE_VERSION = '1.0.0'
import json, os, tempfile, shutil, uuid
from pathlib import Path
from typing import Optional
import gradio as gr
import joat_managed_generation as m
from joat_style001_opening_grant import PROJECT, JOB, SUPERVISOR
PLAN = 'f6e5c397117e7b3cf5c3148f5d761e0f3695b981176abb0d6c6a4a6c7f12f6f3'
BUDGET = 420
CONTROL = 'Dezz-9-10/J.O.A.T.-Executive-Producer-Bot'
OWNER_STATEMENT = 'I already gave the go-ahead. We need not to stop until it is that time. This is already approved.'

def exact_plan(value):
    if m.digest(value) != PLAN:
        raise ValueError('The prepared plan differs from the audited original-script prompt correction.')
    p = value['parameters']
    if (p['seconds'], p['max_width'], p['max_height'], p['input_mode'], p['gen_budget']) != (5, 576, 1024, 'single image (i2v)', BUDGET):
        raise ValueError('Approved opening settings changed.')
    return value

def result_outputs(directory, receipt):
    outcome = None
    video = None
    index_file = directory/'artifact_index.json'
    if index_file.exists():
        index = m.read_json(index_file)
        outcome_file = directory/'artifacts'/'generation_result.json'
        entry = next((x for x in index.get('files', []) if x.get('filename') == 'generation_result.json'), None)
        if entry and outcome_file.exists():
            if m.file_hash(outcome_file) != entry['sha256']:
                raise ValueError('Saved generation result integrity failed.')
            outcome = m.read_json(outcome_file)
        entry = next((x for x in index.get('files', []) if x.get('filename') == 'output.mp4'), None)
        if entry:
            source = m.safe_path(directory/'artifacts'/'output.mp4')
            if source.stat().st_size != entry['size_bytes'] or m.file_hash(source) != entry['sha256']:
                raise ValueError('Saved MP4 integrity failed.')
            target = Path(tempfile.mkdtemp(prefix='joat-original-opening-'))/'STYLE001_CORRECTED_OPENING.mp4'
            shutil.copyfile(source, target)
            video = str(target)
    terminal = bool(outcome and (outcome.get('status') == 'completed' or outcome.get('submission_state') in ('not_submitted', 'response_received') or outcome.get('error_message', '').startswith('You have exceeded your Pro ZeroGPU quota')))
    if terminal and not (directory/'gpu_hold_restore.json').exists():
        try:
            api = m.HfApi(token=os.environ.get('JOAT_SPECIALIST_TOKEN', ''))
            if api.whoami().get('name') != m.OWNER:
                raise ValueError('Owner service credential required.')
            api.add_space_variable(CONTROL, key='JOAT_STUDIO_GPU_HOLD', value='true')
            restored = True
        except Exception:
            restored = False
        m.write_once(directory/'gpu_hold_restore.json', dict(file_version=FILE_VERSION, restored=restored, requires_operator_review=not restored, gpu_requested=False))
    note = 'Corrected original-story opening saved for independent visual/audio QC.' if video else 'Saved attempt status: '+str(receipt.get('status'))+'. No automatic retry.'
    return note, dict(receipt=receipt, generation_result=outcome), video, video

def run_approved(profile: Optional[gr.OAuthProfile], oauth: Optional[gr.OAuthToken], request: gr.Request):
    token = m.owner_token(profile, oauth, request)
    m.mount_check('main')
    from gradio.context import LocalContext
    from joat_remote_generation import source_for, prepared_path, signed, save_plan, grant, load_grant, run, PREFIX
    packet = source_for(PROJECT, JOB, SUPERVISOR)
    ledger = m.ROOT/'production-projects'/PROJECT/'opening-authorization'/PLAN/'native-prompt-qc-fix-1.0.0'
    context = LocalContext.request.set(request)
    try:
        if not (ledger/'grant.json').exists():
            # Any interrupted issuance remains reserved. It requires operator
            # recovery rather than silently issuing another authorization.
            if (ledger/'reservation.json').exists():
                raise ValueError('Opening authorization was reserved; inspect its saved state before continuing.')
            api = m.HfApi(token=os.environ.get('JOAT_SPECIALIST_TOKEN', ''))
            hold = api.get_space_variables(CONTROL).get('JOAT_STUDIO_GPU_HOLD')
            if hold is None or hold.value.lower() != 'false' or str(api.space_info(CONTROL).runtime.stage) != 'RUNNING':
                raise ValueError('Director is not released and ready. No GPU authorization was consumed.')
            check_id = uuid.uuid4().hex
            check_dir = m.ROOT/'remote-generation'/'requests'/check_id
            m.write_once(check_dir/'request.json', dict(file_version=FILE_VERSION, operation='check', project_id=PROJECT, source_job_fingerprint=JOB, plan_fingerprint=PLAN, gpu_requested=False))
            try:
                path = prepared_path(m.ROOT, packet, PLAN)
                if not path.exists():
                    response = m.proxy('executive', 'prepare', signed(packet, 'prepare'), token)
                    exact_plan(response['plan'])
                    if response.get('plan_fingerprint') != PLAN:
                        raise ValueError('Native prepare fingerprint differs.')
                    save_plan(packet, response)
                plan = exact_plan(m.read_json(path)['plan'])
                checked = m.proxy('executive', 'check', signed(packet, 'check', plan), token)
                if (checked.get('schema') != 'joat.render_connection_check.v1' or checked.get('status') != 'passed' or checked.get('gpu_called') is not False or checked.get('source_job_fingerprint') != JOB):
                    raise ValueError('Exact corrected opening connection check did not pass.')
                m.write_once(check_dir/'connection_check.json', checked)
                m.write_once(check_dir/'receipt.json', dict(file_version=FILE_VERSION, status='connection_passed', operation='check', plan_fingerprint=PLAN, gpu_requested=False))
            except Exception as exc:
                m.write_once(check_dir/'receipt.json', dict(file_version=FILE_VERSION, status='connection_failed', error_type=type(exc).__name__, gpu_requested=False))
                raise
            m.write_once(ledger/'reservation.json', dict(file_version=FILE_VERSION, authorization='owner_chat_2026-10-18_and_authenticated_browser_action', owner_statement=OWNER_STATEMENT, exact_original_story_preserved=True, plan_fingerprint=PLAN, source_job_fingerprint=JOB, connection_request_id=check_id, maximum_render_attempts=1, gpu_ceiling_seconds=BUDGET, credit_purchase_authorized=False, automatic_retry=False, further_shots_authorized_by_this_grant=False))
            issued = grant(packet, plan, True)
            m.write_once(ledger/'grant.json', issued)
        issued = m.read_json(ledger/'grant.json')
        identifier = issued['grant_id']
        directory = m.ROOT/'remote-generation'/'requests'/identifier
        # Completed results remain downloadable after the grant expires.
        if (directory/'receipt.json').exists():
            return result_outputs(directory, m.read_json(directory/'receipt.json'))
        verified = load_grant(identifier, packet, PLAN)
        if verified['gpu_ceiling_seconds'] != BUDGET:
            raise ValueError('Exact approved allocation required.')
        envelope = dict(schema='joat.remote_generation_request.v1', file_version=FILE_VERSION, request_id=identifier, operation='execute', project_id=PROJECT, source_job_fingerprint=JOB, source_supervisor_fingerprint=SUPERVISOR, plan_fingerprint=PLAN, grant_id=identifier)
        receipt = run(PREFIX+identifier, json.dumps(envelope))
        return result_outputs(directory, receipt)
    except Exception as exc:
        raise gr.Error('Corrected opening stopped safely. No automatic retry. '+m.safe_validation_message(exc, token)) from None
    finally:
        LocalContext.request.reset(context)

def add_ui():
    with gr.Accordion('Style001 — Approved original story', open=True):
        gr.Markdown('**Ready: corrected opening from your approved original90second story.** The story, cast, exact dialogue and timing remain locked. Production instructions stay outside native scene/audio text. This action checks the exact corrected plan, then renders one five-second opening with a420second allocation ceiling. It never purchases credits or retries a failed render. Speech intended for narration is added later in post; character dialogue remains native speech in its designated shots.')
        gr.LoginButton()
        note = gr.Markdown()
        result = gr.JSON(label='Saved generation result — independent QC required')
        video = gr.Video(label='Corrected opening candidate')
        download = gr.File(label='Download corrected opening MP4')
        gr.Button('Generate approved corrected opening — one attempt', variant='primary').click(run_approved, [], [note, result, video, download], api_visibility='private', concurrency_limit=1, trigger_mode='once')
    with gr.Accordion('Earlier opening candidate — QC corrections recorded', open=False):
        from joat_style001_browser_check import browser_view_saved
        note = gr.Markdown()
        result = gr.JSON(label='Earlier saved result')
        video = gr.Video(label='Earlier candidate — not QC approved')
        download = gr.File(label='Download earlier candidate')
        gr.Button('View earlier saved candidate — no GPU').click(browser_view_saved, [], [note, result, video, download], api_visibility='private', concurrency_limit=1, trigger_mode='once')
