"""Additive, owner-gated production tabs. File version: 1.0.6.

Existing bot APIs and authority stay intact.
"""
import json
import tempfile
from pathlib import Path
from typing import Optional

import gradio as gr

from joat_post_media import (DEPARTMENTS, read_json, write_json, execute_department,
                            archive_delivery, assemble_timeline, audio_evidence, seal, file_hash)
from joat_post_pipeline import prepare_post, execute_post, final_review

FILE_VERSION = '1.0.6'

OWNER = 'Dezz-9-10'


def bearer_header(request):
    if request is None:
        return ''
    # Current Gradio clients use x-hf-authorization; older clients use authorization.
    return request.headers.get('x-hf-authorization', '') or request.headers.get('authorization', '')


def require_owner(profile, request):
    if profile is not None and profile.username == OWNER:
        return OWNER
    # Authenticated server-to-server calls use the HF bearer header, never a JSON token input.
    header = bearer_header(request)
    if header.lower().startswith('bearer '):
        from huggingface_hub import HfApi
        try:
            if HfApi(token=header[7:]).whoami()['name'] == OWNER:
                return OWNER
        except Exception:
            pass
    raise gr.Error('Sign in as Dezz-9-10 to run production media actions.')


def owner_token(profile, oauth, request):
    require_owner(profile, request)
    if oauth is not None and oauth.token:
        return oauth.token
    header = bearer_header(request)
    if header.lower().startswith('bearer '):
        return header[7:]
    raise gr.Error('Owner OAuth token unavailable; sign in again.')


def approved(value):
    if value is not True:
        raise gr.Error('Review the exact plan and explicitly approve this action first.')


def safe_call(function, *args):
    try:
        return function(*args)
    except (ValueError, RuntimeError) as error:
        raise gr.Error(str(error)) from None
    except Exception:
        raise gr.Error('Production media action failed; no completed result was registered.') from None


def add_specialist_ui(role):
    def execute(order_file: str, source: str, auxiliary: str, owner_approved: bool,
                profile: Optional[gr.OAuthProfile], request: gr.Request):
        require_owner(profile, request);approved(owner_approved)
        return safe_call(execute_department, role, read_json(order_file), source, auxiliary)
    with gr.Tab('Production Media'):
        gr.Markdown('Execute an owner-approved Post Supervisor order against actual media. Final QC is separate.')
        login()
        order = gr.File(label='Exact Post Supervisor work order JSON', type='filepath', file_types=['.json'])
        video = gr.File(label='Authorized input MP4', type='filepath', file_types=['.mp4'])
        auxiliary = gr.File(label='Optional approved audio or PNG overlay', type='filepath')
        confirmation = gr.Checkbox(label='I reviewed this exact work order and authorize its technical operation', value=False)
        result = gr.JSON(label='Verified department result');output = gr.Video(label='Actual output');result_file = gr.File(label='Exact result JSON')
        gr.Button('Execute approved media operation').click(execute, [order, video, auxiliary, confirmation],
            [result, output, result_file], api_name='execute_production_media', api_visibility='undocumented', concurrency_limit=1, trigger_mode='once')
        for component in (order, video, auxiliary):
            component.change(lambda: False, outputs=confirmation, api_visibility='private')


def login():
    import os
    if os.environ.get('SPACE_ID'):
        gr.LoginButton()
    else:
        gr.Markdown('Owner OAuth is available on the Hugging Face deployment.')


def add_post_ui(main_assistant=False):
    def prepare(qc_file: str, source: str, operations: str):
        plan = safe_call(prepare_post, read_json(qc_file), json.loads(operations), source)
        directory = tempfile.mkdtemp(prefix='joat-plan-')
        return plan, (plan, source), False, write_json(directory, 'approved_post_plan.json', plan)

    def describe_extras(paths: list[str]):
        return False, [{'filename': Path(p).name, 'sha256': file_hash(p)} for p in (paths or [])]

    def execute(retained, extras: list[str], owner_approved: bool,
                profile: Optional[gr.OAuthProfile], oauth: Optional[gr.OAuthToken], request: gr.Request):
        token = owner_token(profile, oauth, request);approved(owner_approved)
        if not retained:
            raise gr.Error('Prepare the exact Post plan first.')
        plan, source = retained
        result, output, file = safe_call(execute_post, plan, source, extras, token)
        return result, output, file

    # A separate file-based receiver is used by Main Assistant. It has the same owner checks.
    def receive(plan_file: str, source: str, extras: list[str], owner_approved: bool,
                profile: Optional[gr.OAuthProfile], oauth: Optional[gr.OAuthToken], request: gr.Request):
        token = owner_token(profile, oauth, request);approved(owner_approved)
        return safe_call(execute_post, read_json(plan_file), source, extras, token)

    def main_execute(retained, extras: list[str], owner_approved: bool,
                     profile: Optional[gr.OAuthProfile], oauth: Optional[gr.OAuthToken], request: gr.Request):
        token = owner_token(profile, oauth, request);approved(owner_approved)
        if not retained:
            raise gr.Error('Prepare the exact Post plan first.')
        from gradio_client import Client, handle_file
        from joat_post_media import verify, inspect_video
        plan, source = retained
        directory = tempfile.mkdtemp(prefix='joat-main-post-')
        file = write_json(directory, 'approved_post_plan.json', plan)
        client = None
        try:
            client = Client('Dezz-9-10/J.O.A.T.-Post-Production-Supervisor-Bot', token=token, oauth_token=token, verbose=False, download_files=directory)
            result, video, result_file = client.submit(handle_file(file), handle_file(source),
                [handle_file(p) for p in (extras or [])], True, api_name='/execute_post_plan').result(timeout=2700)
            if isinstance(video, (tuple, list)):
                video = video[0]
            verify(result, 'result_fingerprint')
            if result.get('source_post_packet_fingerprint') != plan['plan_fingerprint'] or result.get('delivery_authorized') is not False:
                raise ValueError('Post response does not match retained plan or skipped final QC')
            evidence = inspect_video(video, result['final_master']['specification'])
            if evidence['sha256'] != result['final_master']['sha256']:
                raise ValueError('Downloaded Post master does not match result')
            return result, video, result_file
        except Exception:
            raise gr.Error('Main → Post handoff failed or timed out. No automatic retry; inspect department outputs before resuming.') from None
        finally:
            if client:
                client.close()

    with gr.Tab('Production Orchestration' if main_assistant else 'Actual Post Production'):
        gr.Markdown('Owner approves six explicit technical operations. Source QC must have inspected actual bytes. Final picture/audio review is required afterward.')
        if main_assistant:
            gr.Markdown('This path starts with a QC-approved shot. Idea → approved Master packets and automated generation remain separate gated steps; it does not bypass the Executive Producer.')
        login()
        qc_file = gr.File(label='Exact production QC PASS JSON', type='filepath', file_types=['.json'])
        source = gr.File(label='QC-approved original MP4', type='filepath', file_types=['.mp4'])
        operations = gr.Code(label='Technical operations: explicit preserve or supported department action', language='json',
                             value=json.dumps({d: {'kind': 'preserve'} for d in DEPARTMENTS}, indent=2))
        extras = gr.File(label='Optional hash-approved audio / PNG files', type='filepath', file_count='multiple')
        extra_hashes = gr.JSON(label='Uploaded auxiliary hashes to use in the explicit technical operations')
        plan_view = gr.JSON(label='Exact technical plan');state = gr.State()
        confirmation = gr.Checkbox(label='I reviewed all six operations and approve this exact plan', value=False)
        plan_file = gr.File(label='Exact plan JSON')
        gr.Button('Prepare plan (no media processing)').click(prepare, [qc_file, source, operations],
            [plan_view, state, confirmation, plan_file], api_name='prepare_production_post', api_visibility='private')
        result = gr.JSON();video = gr.Video();result_file = gr.File(label='Exact Post result JSON')
        gr.Button('Run approved Post6 handoffs').click(main_execute if main_assistant else execute,
            [state, extras, confirmation], [result, video, result_file], api_name='run_production_post',
            api_visibility='private', concurrency_limit=1, trigger_mode='once')
        if not main_assistant:
            hidden_plan = gr.File(visible=False);hidden_source = gr.File(visible=False)
            hidden_extras = gr.File(file_count='multiple', visible=False);hidden_approved = gr.Checkbox(visible=False)
            gr.Button(visible=False).click(receive, [hidden_plan, hidden_source, hidden_extras, hidden_approved],
                [result, video, result_file], api_name='execute_post_plan', api_visibility='undocumented', concurrency_limit=1)
        for component in (qc_file, source, operations):
            component.change(lambda: (None, False, None, None), outputs=[state, confirmation, plan_view, plan_file], api_visibility='private')
        extras.change(describe_extras, inputs=extras, outputs=[confirmation, extra_hashes], api_visibility='private')


    return {'qc_file': qc_file, 'source': source, 'result_file': result_file, 'video': video}

def add_final_review_ui():
    def inspect(result_file: str, media: str, reviewed: list[str], profile: Optional[gr.OAuthProfile], request: gr.Request):
        require_owner(profile, request)
        result = safe_call(final_review, read_json(result_file), media,
                           {k: k in (reviewed or []) for k in ('picture', 'audio', 'titles', 'continuity')}, OWNER)
        directory = tempfile.mkdtemp(prefix='joat-final-qc-')
        return result, write_json(directory, 'final_review_result.json', result)
    with gr.Tab('Final Master Review'):
        login()
        file = gr.File(label='Exact Post or timeline result JSON', type='filepath', file_types=['.json'])
        media = gr.File(label='Actual final master MP4', type='filepath', file_types=['.mp4'])
        gr.Markdown('Watch/listen to the entire final master before confirming picture, audio, titles and continuity. Technical decoding is automatic.')
        reviewed = gr.CheckboxGroup(['picture', 'audio', 'titles', 'continuity'], value=[], label='Independent final review')
        output = gr.JSON();packet = gr.File(label='Exact final-reviewed result JSON')
        gr.Button('Record final PASS or REJECT').click(inspect, [file, media, reviewed], [output, packet],
            api_name='review_final_master', api_visibility='undocumented', concurrency_limit=1)
        for component in (file, media):
            component.change(lambda: [], outputs=reviewed, api_visibility='private')


def add_timeline_ui():
    def assemble(media: list[str], results: list[str], owner_approved: bool, profile: Optional[gr.OAuthProfile], request: gr.Request):
        require_owner(profile, request);approved(owner_approved)
        return safe_call(assemble_timeline, media, [read_json(p) for p in (results or [])])
    with gr.Tab('Timeline Assembly'):
        login()
        gr.Markdown('Upload shots and matching final-PASS result files in the same explicit order. No transitions, retiming or creative normalization are inserted. Review the assembled master again afterward.')
        media = gr.File(label='Final-PASS MP4 shots in timeline order', file_count='multiple', type='filepath', file_types=['.mp4'])
        packets = gr.File(label='Matching final-PASS result JSON files in same order', file_count='multiple', type='filepath', file_types=['.json'])
        confirmation = gr.Checkbox(label='I approve this exact shot order and full-shot assembly', value=False)
        result = gr.JSON();video = gr.Video();file = gr.File()
        gr.Button('Assemble actual timeline MP4').click(assemble, [media, packets, confirmation], [result, video, file],
            api_name='assemble_production_timeline', api_visibility='private', concurrency_limit=1)
        for component in (media, packets):
            component.change(lambda: False, outputs=confirmation, api_visibility='private')


def add_delivery_ui():
    def deliver(result_file: str, source: str, profile: Optional[gr.OAuthProfile], request: gr.Request):
        require_owner(profile, request)
        return safe_call(archive_delivery, read_json(result_file), source)
    with gr.Tab('Actual MP4 Delivery'):
        login()
        gr.Markdown('Validates the actual final-PASS master and packages it with provenance. Save the MP4 to Files on your iPad. Space temporary storage is not a durable archive.')
        result = gr.File(label='Exact final-PASS result JSON', type='filepath', file_types=['.json'])
        video = gr.File(label='Actual approved final MP4', type='filepath', file_types=['.mp4'])
        status = gr.JSON();master = gr.File(label='Download finished MP4');archive = gr.File(label='Optional provenance ZIP');manifest = gr.File(label='Delivery manifest JSON')
        gr.Button('Verify and prepare final delivery').click(deliver, [result, video], [status, master, archive, manifest],
            api_name='deliver_actual_master', api_visibility='private', concurrency_limit=1)


def add_voice_ui(bot):
    def prepare(job_file: str, recording: str):
        job = read_json(job_file);bot.validate_job(job)
        from joat_post_media import verify
        if job.get('job_fingerprint'):
            verify(job, 'job_fingerprint')
        evidence = safe_call(audio_evidence, recording)
        durations = [line.get('target_duration_seconds') for line in job['dialogue']]
        if all(d is not None for d in durations) and evidence['duration_seconds'] > sum(float(d) for d in durations) + 0.1:
            raise gr.Error('Recording exceeds the EP dialogue timing budget.')
        binding = seal({'schema': 'joat.voice_recording_binding.v1', 'original_ep_job': job,
                        'original_ep_job_sha256': __import__('hashlib').sha256(json.dumps(job, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest(),
                        'audio': evidence, 'owner_review_required': True}, 'packet_fingerprint')
        return binding, (binding, recording), False

    def register(retained, verified: bool, profile: Optional[gr.OAuthProfile], request: gr.Request):
        require_owner(profile, request);approved(verified)
        if not retained:
            raise gr.Error('Prepare the recording binding first.')
        binding, recording = retained
        from joat_post_media import verify
        verify(binding, 'packet_fingerprint')
        job = binding['original_ep_job'];bot.validate_job(job)
        evidence = safe_call(audio_evidence, recording)
        if evidence != binding['audio']:
            raise gr.Error('Recording changed after preparation.')
        # Provider-less fallback is a real owner-reviewed recording, never a TTS claim.
        result = seal({'schema': 'joat.voice_dialogue_result.v1', 'app_version': '1.0.1',
                       'job_id': job['job_id'], 'project_id': job['project_id'], 'status': 'completed',
                       'source_job': job, 'recording_binding': binding, 'audio': evidence, 'owner_reviewed_dialogue_and_voice': True,
                       'provider_generated_here': False, 'delivery_authorized': False}, 'result_fingerprint')
        directory = tempfile.mkdtemp(prefix='joat-voice-')
        return result, recording, write_json(directory, 'verified_voice_result.json', result)
    with gr.Tab('Actual Approved Dialogue Audio'):
        login()
        gr.Markdown('Register an actual recording against an unchanged EP-authorized voice job. This does not generate a voice. A live voice provider is still required for automatic speech generation.')
        job = gr.File(label='Original EP voice job JSON', type='filepath', file_types=['.json'])
        audio = gr.File(label='Actual approved dialogue recording', type='filepath')
        binding = gr.JSON(label='Exact source job and recording binding');state = gr.State()
        confirmed = gr.Checkbox(label='I listened and verified the locked dialogue, speaker, voice identity, performance and timing', value=False)
        gr.Button('Prepare source and audio binding').click(prepare, [job, audio], [binding, state, confirmed],
            api_name='prepare_dialogue_recording', api_visibility='private')
        result = gr.JSON();output = gr.Audio();file = gr.File()
        gr.Button('Validate and register real dialogue audio').click(register, [state, confirmed], [result, output, file],
            api_name='register_approved_dialogue_audio', api_visibility='private', concurrency_limit=1)
        for component in (job, audio):
            component.change(lambda: (None, None, False), outputs=[state, binding, confirmed], api_visibility='private')
