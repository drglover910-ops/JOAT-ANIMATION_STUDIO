"""Owner-approved rendering; joat_render_bridge.py file version1.0.21."""
FILE_VERSION = "1.0.21"
import hashlib
import json
import math
from pathlib import Path
import tempfile
import urllib.request
from PIL import Image, ImageOps

from joat_media_tools import inspect_video, file_hash
from joat_prompt_compiler import compile_approved_scene
from joat_approved_reference import reference_entry, load_approved_frame
from joat_job_frame_binding import load_binding, reference_from_binding

ROOT = Path(__file__).resolve().parent
CONTRACT = json.loads((ROOT / 'renderer_contract.json').read_text())
CATALOG = json.loads((ROOT / 'asset_catalog.json').read_text())
DIMENSIONS = {'16:9': (1024, 576), '9:16': (576, 1024), '1:1': (768, 768), '4:3': (1024, 768), '21:9': (1344, 576)}


def stable(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def verify_fingerprint(value, field):
    core = dict(value)
    expected = core.pop(field, None)
    if not expected or expected != hashlib.sha256(stable(core).encode()).hexdigest():
        raise ValueError('Invalid ' + field)


def _reference(role, packet, path):
    if role == 'environment' and packet.get('project_scope') is not None:
        from joat_project_environments import reference
        return reference(packet, path, packet['project_scope']['project_id'])
    entry = CATALOG.get(role + ':' + str(path))
    if not entry or entry.get('sha256') not in packet.get('source_asset_hashes', {}).values():
        raise ValueError('Reference is absent from the immutable approved asset hashes: ' + role)
    return dict(entry)


def prepare_plan(worker, packet):
    verify_fingerprint(packet, 'packet_fingerprint')
    job = packet['generation_job']
    verify_fingerprint(job, 'job_fingerprint')
    worker.validate_supervisor_packet(packet)
    from joat_project_lifecycle import assert_active
    assert_active(job['project_context']['project_id'])
    from joat_character_speech_policy import require_character_speech
    require_character_speech(packet)
    if job['job_type'] != 'video' or job['engine'] != 'ltx':
        raise ValueError('This bridge supports the existing approved LTX video route only')
    spec = job['generation_specification']
    seconds = float(spec['duration_seconds'])
    if not math.isfinite(seconds) or not 1 <= seconds <= 12:
        raise ValueError('Initial controlled renderer supports approved shots of 1–12 seconds')
    if spec['aspect_ratio'] not in DIMENSIONS:
        raise ValueError('Approved aspect is not supported')
    prompt_contract = job['prompt_contract']
    for role in ('character', 'environment', 'director', 'shot_camera', 'performance_action'):
        key = 'performance_action_packet' if role == 'performance_action' else role + '_packet'
        if job.get('immutable_upstream_snapshot', {}).get(role) != prompt_contract.get(key):
            raise ValueError('Locked prompt and upstream snapshot differ')
        upstream = prompt_contract[key]
        if upstream.get('packet_fingerprint'):
            if role == 'shot_camera':
                # Camera's existing documented hash excludes created_at as well.
                core = dict(upstream);expected = core.pop('packet_fingerprint')
                core.pop('created_at', None)
                if expected != hashlib.sha256(stable(core).encode()).hexdigest():
                    raise ValueError('Invalid Camera packet fingerprint')
            else:
                verify_fingerprint(upstream, 'packet_fingerprint')
        elif role not in ('character', 'director'):
            raise ValueError('Original fingerprinted upstream packet required: ' + role)
    character = prompt_contract['character_packet']
    environment = prompt_contract['environment_packet']
    if environment.get('project_scope') is not None and environment['project_scope'].get('project_id') != job['project_context']['project_id']:
        raise ValueError('Project environment cannot be used by a different project')
    char_anchor = _reference('character', character, character.get('identity_lock_asset'))
    supporting = character.get('supporting_reference_assets', [])
    references = {
        'image_path': char_anchor,
        'identity_ref_image': char_anchor,
        'msr_background': _reference('environment', environment, environment.get('identity_lock_asset')),
    }
    for slot, path in zip(('msr_ref2', 'msr_ref3'), supporting):
        references[slot] = _reference('character', character, path)
    approved = prompt_contract['director_packet'].get('approved_job_references', [])
    if not isinstance(approved, list):
        raise ValueError('Director approved_job_references must be a list')
    selected = [r for r in approved if r.get('descriptor', {}).get('scope', {}).get('shot_id') == job['project_context']['shot_id']
                and r.get('descriptor', {}).get('scope', {}).get('scene_id') == job['project_context']['scene_id']]
    if approved and len(selected) != 1:
        raise ValueError('No unique approved opening frame for this shot')
    # Main-reviewed new productions require an approved single-scene image.
    # Identity portraits and multi-panel cards are evidence, not scene frames.
    job_frame_binding = load_binding(packet) if not selected and prompt_contract['director_packet'].get('project_assignment', {}).get('owner_review_required') is True else None
    if prompt_contract['director_packet'].get('project_assignment', {}).get('owner_review_required') is True and not selected and not job_frame_binding:
        raise ValueError('Approved single-scene opening frame required for this reviewed shot; no GPU request was sent')
    if environment.get('project_scope') is not None and not selected and not job_frame_binding:
        raise ValueError('Project environment requires an owner-approved composed opening frame')
    identity_evidence = None
    if selected or job_frame_binding:
        manifest = selected[0] if selected else job_frame_binding['approved_frame_manifest']
        reference = reference_entry(manifest, character, environment, job['project_context']) if selected else reference_from_binding(job_frame_binding, packet)
        if char_anchor['sha256'] != manifest['descriptor']['canonical_identity_binding']['identity_source_sha256']:
            raise ValueError('Catalog anchor differs from approved frame identity binding')
        load_approved_frame(manifest)
        # This approved frame already composes the reviewed character and scene.
        # In this renderer, all MSR inputs are also frame-zero image guides.
        # A portrait is identity evidence, not an additional frame-zero scene.
        references = {'image_path': reference, 'msr_background': reference}
        identity_evidence = {'reference': char_anchor, 'role': 'canonical_identity_evidence',
                             'sent_to_renderer': False,
                             'approved_frame_identity_binding': manifest['descriptor']['canonical_identity_binding']}
    if job_frame_binding:
        references = {'image_path': references['image_path']}
    params = {item['name']: item['default'] for item in CONTRACT['parameters']}
    params.update(msr_ref2=None, msr_ref3=None, msr_ref4=None, identity_ref_image=None)
    # Make every input explicit and neutralize unrelated stylistic LoRAs.
    for key in params:
        if key.endswith(('_lora_strength', '_audio_strength')):
            params[key] = 0.0
    width, height = DIMENSIONS[spec['aspect_ratio']]
    compiled = compile_approved_scene(prompt_contract, job['project_context'], spec, approved_composed_frame=bool(job_frame_binding))
    params.update({
        'prompt': compiled['positive_prompt'],
        'negative_prompt': compiled['negative_prompt'],
        'seconds': seconds, 'max_width': width, 'max_height': height,
        'custom_res_enabled': True, 'snap_multiple': 64, 'target_mp': width * height / 1e6,
        'seed': 21, 'randomize_seed': False, 'input_mode': 'multi-reference (MSR)',
        'mode': 'anchor only', 'face_bbox': '', 'preset': 'original',
        'prompt_relay_enabled': False, 'prompt_segments': '', 'scene_chain_enabled': False,
        'scene_chain_prompt': '', 'profile_name': '', 'user_loras_text': '',
        'motion_control_type': 'off', 'audio_ref_enabled': False, 'kf_mid_enabled': False,
        'msr_lora_strength': 0.7,
    })
    if job_frame_binding:
        import os
        ceiling = int(os.environ.get('JOAT_COMPOSED_I2V_GPU_CEILING_SECONDS', '600'))
        if not 45 <= ceiling <= 600:
            raise ValueError('Composed-frame GPU allocation must be45–600seconds; no request sent')
        params.update(input_mode='single image (i2v)', msr_background=None, msr_lora_strength=0.0, gen_budget=ceiling, skip_refine=True, profile_name='__joat_controlled_composed_i2v_v1__')
    for key, ref in references.items():
        params[key] = ref['url']
    execution = worker.build_engine_execution(job)
    plan = {'schema': 'joat.render_plan.v1', 'source_job_fingerprint': job['job_fingerprint'],
            'worker_version': execution['worker']['version'],
            'source_supervisor_fingerprint': packet['packet_fingerprint'],
            'execution_fingerprint': execution['execution_fingerprint'],
            'renderer_space': CONTRACT['space'], 'renderer_revision': CONTRACT['revision'],
            'renderer_api': '/generate', 'parameters': params, 'references': references,
            'identity_evidence': identity_evidence,
            'reference_transform': {'method': 'contain and letterbox', 'width': width, 'height': height,
                                    'crop': False, 'stretch': False, 'exif_orientation_applied': True,
                                    'reason': 'Renderer derives output aspect from its first reference image'},
            'prompt_compilation': compiled['manifest'],
            'gpu_reservation': {'requested_seconds': CONTRACT['runtime_check']['reservation_ceiling_seconds'],
                                'policy': 'uncalibrated_full_msr_configured_ceiling',
                                'provider_permission_unverified': True, 'gpu_called': False,
                                'note': 'A600-second reservation is separate from the approved shot duration. Provider allowance is unverified; no automatic retry.'},
            'owner_approval_required': True, 'qc_approval': False}
    if job_frame_binding:
        plan['gpu_reservation'].update(requested_seconds=params['gen_budget'], policy='controlled_single_image_explicit_ceiling', note=f"One approved composed-frame I2V shot. Explicit{params['gen_budget']}second allocation ceiling; no automatic retry.")
        plan['job_reference_binding'] = {'binding_fingerprint':job_frame_binding['binding_fingerprint'],'origin_frame_asset_id':job_frame_binding['approved_frame_manifest']['asset_id'],'origin_frame_scope':job_frame_binding['approved_frame_manifest']['descriptor']['scope'],'target_context':job['project_context']}
    return plan


def _check_runtime(client, plan):
    parameters = plan['parameters']
    if parameters.get('input_mode') != 'single image (i2v)':
        return _check_msr_runtime(client, plan)
    check = CONTRACT.get('i2v_runtime_check', {})
    if parameters.get('msr_lora_strength') != 0 or parameters.get('msr_background') is not None or len(plan['references']) != 1:
        raise ValueError('Controlled single-image route cannot contain MSR inputs')
    if any(parameters.get(k) is not None for k in ('msr_ref2','msr_ref3','msr_ref4','identity_ref_image')):
        raise ValueError('Unexpected extra single-image reference')
    api = client.view_api(return_format='dict', print_info=False)['named_endpoints']
    names = [p['parameter_name'] for p in api.get(check.get('api_name'),{}).get('parameters',[])]
    if names != ['width','height','seconds','gen_budget']:
        raise ValueError('Single-image CPU runtime API changed')
    report = client.predict(parameters['max_width'], parameters['max_height'], parameters['seconds'], parameters['gen_budget'], api_name=check['api_name'])
    if report.get('schema') != check.get('schema') or report.get('file_version') != check.get('preflight_file_version') or report.get('status') != 'passed' or report.get('gpu_called') is not False:
        raise ValueError('Single-image CPU runtime check did not pass')
    legacy = CONTRACT['runtime_check']
    if report.get('versions') != legacy['required_versions'] or report.get('runtime_dependencies') != legacy['required_dependencies']:
        raise ValueError('Installed renderer dependencies changed; re-audit before spending GPU quota')
    workload = report.get('workload',{});shape = workload.get('workload',{})
    if workload.get('signature') != hashlib.sha256(stable(shape).encode()).hexdigest():
        raise ValueError('Single-image workload hash changed')
    frames = ((max(9,int(parameters['seconds']*24)+1)-1+7)//8)*8+1
    expected = {'generation_width':parameters['max_width'],'generation_height':parameters['max_height'],'output_width':parameters['max_width'],'output_height':parameters['max_height'],'requested_duration_seconds':parameters['seconds'],'generated_pixel_frames':frames,'output_fps':24,'input_mode':'single image (i2v)','msr_image_guide_latent_frames':0,'msr_pseudo_video_pixel_frames':0,'effective_skip_refine':True,'anchor_only':True,'user_lora_count':0,'motion_control_active':False,'audio_reference_active':False,'kv_enabled':False,'prompt_relay_enabled':False,'scene_chain_enabled':False,'last_keyframe_active':False,'mid_keyframes_active':False}
    if any(shape.get(k) != v for k,v in expected.items()):raise ValueError('Single-image workload differs from plan')
    graph = report.get('graph',{})
    if graph.get('schema') != check['graph_schema'] or graph.get('status') != 'passed' or graph.get('gpu_called') is not False:raise ValueError('Single-image graph unverified')
    for k,v in {'width':parameters['max_width'],'height':parameters['max_height'],'output_frames':frames,'image_input_count':1,'msr_node_count':0}.items():
        if graph.get(k) != v:raise ValueError('Single-image graph differs from plan')
    budget = report.get('budget',{})
    if budget.get('status') != 'ready' or budget.get('gpu_called') is not False or budget.get('workload_signature') != workload['signature'] or budget.get('budget_seconds') != parameters['gen_budget'] or budget.get('budget_seconds') > plan['gpu_reservation']['requested_seconds'] or budget.get('owner_gpu_approval_required') is not True or budget.get('provider_permission_unverified') is not True:
        raise ValueError('Single-image reservation is not approved for this plan')
    return report


def _check_msr_runtime(client, plan):
    """Validate pinned installed code and CPU graph before any GPU submission."""
    contract = CONTRACT['runtime_check']
    api = client.view_api(return_format='dict', print_info=False)['named_endpoints']
    names = [p['parameter_name'] for p in api.get(contract['api_name'], {}).get('parameters', [])]
    expected = ['width', 'height', 'seconds', 'msr_frame_count', 'reference_count', 'gen_budget']
    if names != expected:
        raise ValueError('Renderer CPU runtime API changed; no GPU call made')
    parameters = plan['parameters']
    report = client.predict(parameters['max_width'], parameters['max_height'], parameters['seconds'],
                            parameters['msr_frame_count'], len(plan['references']), 0,
                            api_name=contract['api_name'])
    if not isinstance(report, dict) or report.get('schema') != contract['schema'] or report.get('status') != 'passed' or report.get('gpu_called') is not False:
        raise ValueError('Renderer CPU runtime check failed; no GPU call made')
    if report.get('versions') != contract['required_versions'] or report.get('runtime_dependencies') != contract['required_dependencies']:
        raise ValueError('Installed renderer dependencies changed; re-audit before spending GPU quota')
    workload = report.get('workload', {})
    shape = workload.get('workload', {})
    if workload.get('schema') != 'joat.gpu_workload.v1' or workload.get('signature') != hashlib.sha256(stable(shape).encode()).hexdigest():
        raise ValueError('Renderer workload signature mismatch; no GPU call made')
    width, height, seconds = parameters['max_width'], parameters['max_height'], parameters['seconds']
    frames = ((max(9, int(seconds * 24) + 1) - 1 + 7) // 8) * 8 + 1
    expected_shape = {'generation_width': width, 'generation_height': height, 'output_width': width,
                      'output_height': height, 'requested_duration_seconds': seconds,
                      'generated_pixel_frames': frames, 'output_fps': 24,
                      'msr_image_guide_latent_frames': len(plan['references']),
                      'msr_pseudo_video_pixel_frames': parameters['msr_frame_count'],
                      'input_mode': 'multi-reference (MSR)', 'effective_skip_refine': True,
                      'anchor_only': True, 'user_lora_count': 0, 'motion_control_active': False,
                      'audio_reference_active': False, 'kv_enabled': False,
                      'prompt_relay_enabled': False, 'scene_chain_enabled': False,
                      'last_keyframe_active': False, 'mid_keyframes_active': False}
    if any(shape.get(key) != value for key, value in expected_shape.items()):
        raise ValueError('Renderer workload differs from the locked plan; no GPU call made')
    graph = report.get('graph', {})
    if graph.get('schema') != 'joat.msr_graph_preflight.v1' or graph.get('status') != 'passed' or graph.get('gpu_called') is not False or graph.get('conditioning_metadata_chain_verified') is not True:
        raise ValueError('MSR conditioning graph is unverified; no GPU call made')
    for key, expected_value in {'width':width,'height':height,'output_frames':frames,'per_image_guide_count':len(plan['references'])}.items():
        if graph.get(key) != expected_value:
            raise ValueError('MSR graph differs from the locked plan; no GPU call made')
    budget = report.get('budget', {})
    if budget.get('schema') != 'joat.gpu_reservation.v1' or budget.get('status') != 'ready' or budget.get('gpu_called') is not False or budget.get('workload_signature') != workload['signature']:
        raise ValueError('Renderer GPU reservation is unavailable; no GPU call made')
    requested = budget.get('budget_seconds')
    if type(requested) is not int or not 45 <= requested <= plan['gpu_reservation']['requested_seconds']:
        raise ValueError('Renderer reservation exceeds the owner-reviewed ceiling; no GPU call made')
    if budget.get('owner_gpu_approval_required') is not True or budget.get('provider_permission_unverified') is not True:
        raise ValueError('Renderer GPU permission report is inconsistent; no GPU call made')
    return report


def download_reference(reference, directory):
    # URL comes only from the pinned, reviewed catalog, never from user-provided URLs.
    if 'approved_job_reference' in reference:
        load_approved_frame(reference['approved_job_reference'])
    path = directory / (reference['sha256'] + Path(reference['path']).suffix)
    if not path.exists():
        if 'approved_job_reference' in reference:
            data = load_approved_frame(reference['approved_job_reference']).read_bytes()
        else:
            with urllib.request.urlopen(reference['url'], timeout=60) as response:
                data = response.read(32 * 1024 * 1024 + 1)
        if len(data) > 32 * 1024 * 1024:
            raise ValueError('Reference image exceeds size limit')
        path.write_bytes(data)
    if file_hash(path) != reference['sha256']:
        raise ValueError('Reference bytes do not match the locked asset hash')
    return path


def verify_identity_evidence(plan, directory):
    evidence = plan.get('identity_evidence')
    if evidence is None:
        return None
    reference = evidence['reference']
    if evidence.get('sent_to_renderer') is not False or reference['sha256'] != evidence['approved_frame_identity_binding']['identity_source_sha256']:
        raise ValueError('Canonical identity evidence binding differs')
    original = download_reference(reference, directory)
    return {'role': 'canonical_identity_evidence', 'sha256': file_hash(original),
            'source_hash_verified': True, 'sent_to_renderer': False,
            'biometric_identity_verified': False}


def transform_reference(path, transform, directory):
    """Preserve full reference content while making renderer aspect deterministic."""
    width, height = transform['width'], transform['height']
    output = directory / (file_hash(path) + '-%sx%s.png' % (width, height))
    with Image.open(path) as original:
        original = ImageOps.exif_transpose(original).convert('RGB')
        scaled = ImageOps.contain(original, (width, height), method=Image.Resampling.LANCZOS)
        canvas = Image.new('RGB', (width, height), 'black')
        canvas.paste(scaled, ((width - scaled.width) // 2, (height - scaled.height) // 2))
        canvas.save(output, format='PNG')
    return output



def _safe_error(exc, token):
    import re
    message = str(exc)
    sensitive = [str(token)] if token else []
    try:
        from gradio.context import LocalContext
        request = LocalContext.request.get(None)
        if request is not None:
            for key in ("x-ip-token", "authorization", "x-hf-authorization", "cookie"):
                value = request.headers.get(key)
                if value:
                    sensitive.append(str(value))
    except (ImportError, AttributeError):
        pass
    for value in sensitive:
        message = message.replace(value, "[REDACTED]")
    # Also sanitize named headers in errors produced outside a live callback.
    pattern = r"(?i)([\"']?(?:x-ip-token|x-hf-authorization|authorization|cookie|set-cookie)[\"']?\s*[:=]\s*)([\"'])(.*?)(\2)"
    message = re.sub(pattern, lambda match: match.group(1) + match.group(2) + "[REDACTED]" + match.group(2), message)
    message = re.sub(r"(?im)^(\s*(?:x-ip-token|x-hf-authorization|authorization|cookie|set-cookie)\s*:\s*)[^\r\n]*", r"\1[REDACTED]", message)
    message = re.sub(r"(?i)((?:x-ip-token|x-hf-authorization|authorization|cookie|set-cookie)\s*[:=]\s*)[^\r\n]+", r"\1[REDACTED]", message)
    message = re.sub(r"hf_[A-Za-z0-9]+", "[REDACTED]", message)
    message = re.sub(r"(?i)Bearer\s+[^\s\"']+", "Bearer [REDACTED]", message)
    return message[:1200]


def render_failure_report(exc, packet, token):
    trace = dict(getattr(exc, "connection_diagnostic", {}))
    trace.update(getattr(exc, "render_diagnostic", {}))
    trace.pop("_failure_assets", None)
    trace["error_message"] = _safe_error(trace.get("error_message", exc), token)
    trace.setdefault("error_type", type(exc).__name__)
    submission = trace.get("submission_state", "unknown")
    trace.update(schema="joat.render_failure.v1", status="render_failed",
                 source_job_fingerprint=packet["generation_job"]["job_fingerprint"],
                 automatic_retry=False, qc_approved=False,
                 render_outcome="not_submitted" if submission == "not_submitted" else "unverified")
    return trace



# These clients remain per-operation; credentials and cookies are never shared or logged.
import threading
import time
from gradio_client import Client as _GradioClient

_RENDERER_CONNECTION_LOCK = threading.RLock()
_RENDERER_RETRY_UNTIL = 0.0


class RendererConnectionError(RuntimeError):
    def __init__(self, message, diagnostic):
        super().__init__(message)
        self.connection_diagnostic = diagnostic


def _renderer_request_headers():
    try:
        from gradio.context import LocalContext
        request = LocalContext.request.get(None)
        value = request.headers.get("x-ip-token") if request is not None else None
    except (ImportError, AttributeError):
        value = None
    return {"x-ip-token": str(value)} if value else {}


def _retry_after_seconds(value):
    from email.utils import parsedate_to_datetime
    try:
        return max(0, int(math.ceil(float(value))))
    except (TypeError, ValueError, OverflowError):
        try:
            return max(0, int(math.ceil(parsedate_to_datetime(value).timestamp() - time.time())))
        except (TypeError, ValueError, OverflowError, AttributeError):
            return None


def _renderer_error_text(response, token):
    # Extract the readable error before bounding it; the HTML head can be huge.
    from html.parser import HTMLParser
    class ErrorPage(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.blocked = 0
            self.main_depth = 0
            self.body_depth = 0
            self.main = []
            self.body = []
        def handle_starttag(self, tag, attrs):
            if tag in ("head", "script", "style"):
                self.blocked += 1
            if tag == "main": self.main_depth += 1
            if tag == "body": self.body_depth += 1
        def handle_endtag(self, tag):
            if tag in ("head", "script", "style"):
                self.blocked = max(0, self.blocked - 1)
            if tag == "main": self.main_depth = max(0, self.main_depth - 1)
            if tag == "body": self.body_depth = max(0, self.body_depth - 1)
        def handle_data(self, data):
            if not self.blocked:
                if self.main_depth: self.main.append(data)
                if self.body_depth: self.body.append(data)
    raw = response.text
    if "html" in response.headers.get("content-type", "").lower() or raw.lstrip().lower().startswith(("<!doctype html", "<html")):
        parser = ErrorPage()
        try:
            parser.feed(raw[:262144])
            visible = " ".join(" ".join(parser.main or parser.body).split())
            if visible: return _safe_error(visible, token)
        except Exception:
            pass
    return _safe_error(raw, token)


class _RendererClient(_GradioClient):
    def _get_config(self):
        import httpx
        import urllib.parse
        global _RENDERER_RETRY_UNTIL
        endpoint = urllib.parse.urljoin(self.src, "config")
        response = httpx.get(endpoint, headers=self.headers, cookies=self.cookies,
                             verify=self.ssl_verify, **self.httpx_kwargs)
        if response.is_success:
            self.cookies.update({name: value for name, value in response.cookies.items()
                                 if value is not None and name not in self.cookies})
            config = response.json()
            if not isinstance(config, dict) or "components" not in config or "dependencies" not in config:
                raise RendererConnectionError("Renderer did not return a Gradio configuration.",
                                              {"http_status": response.status_code, "endpoint_phase": "renderer_config"})
            return config
        selected_headers = {}
        for key in ("retry-after", "ratelimit", "ratelimit-policy", "x-ratelimit-reset",
                    "x-ratelimit-remaining", "x-request-id", "content-type"):
            if key in response.headers:
                selected_headers[key] = _safe_error(response.headers[key], self.token)[:500]
        retry = _retry_after_seconds(response.headers.get("retry-after"))
        diagnostic = {"endpoint_phase": "renderer_config", "http_status": response.status_code,
                      "server_response": _renderer_error_text(response, self.token),
                      "request_endpoint": urllib.parse.urlunsplit((*urllib.parse.urlsplit(endpoint)[:3], "", "")),
                      "response_endpoint": urllib.parse.urlunsplit((*urllib.parse.urlsplit(str(response.url))[:3], "", "")) if response._request is not None else None,
                      "rate_limit_headers": selected_headers,
                      "owner_auth_header_present": bool(self.headers.get("x-hf-authorization")),
                      "delegated_ip_header_present": bool(self.headers.get("x-ip-token")),
                      "request_made": True}
        if response.status_code == 429:
            # Retry only when the owner chooses to check again after this deadline.
            cooldown = retry if retry is not None else 60
            _RENDERER_RETRY_UNTIL = time.time() + max(1, cooldown)
            diagnostic.update(retry_after_seconds=cooldown,
                              cooldown_basis="server_retry_after" if retry is not None else "local_60_second_pause")
            message = "Renderer configuration request returned HTTP 429. See server_response and rate_limit_headers."
        else:
            message = "Renderer configuration request returned HTTP " + str(response.status_code) + "."
        raise RendererConnectionError(message, diagnostic)


def _assert_renderer_connection_ready():
    with _RENDERER_CONNECTION_LOCK:
        remaining = int(math.ceil(_RENDERER_RETRY_UNTIL - time.time()))
        if remaining > 0:
            raise RendererConnectionError("Renderer connection is in cooldown; no request was sent.",
                                          {"endpoint_phase": "renderer_config", "cooldown_active": True,
                                           "retry_after_seconds": remaining, "request_made": False})


def _renderer_client(token, **kwargs):
    with _RENDERER_CONNECTION_LOCK:
        _assert_renderer_connection_ready()
        # Forward the owner's quota context on configuration requests too, before SDK threads start.
        client = _RendererClient(CONTRACT['space'], token=token, verbose=False,
                                 headers=_renderer_request_headers(), **kwargs)
        _capture_renderer_headers(client)
        return client


def _capture_renderer_headers(client):
    # Request context is available here; submit() uses a different thread.
    if hasattr(client, "add_zero_gpu_headers"):
        client.headers = client.add_zero_gpu_headers(dict(client.headers))


def _downloaded_video_path(response):
    video = response[0]
    if isinstance(video, dict):
        video = video.get("video")
        if isinstance(video, dict):
            video = video.get("path")
    elif isinstance(video, (tuple, list)):
        video = video[0] if video else None
    if not isinstance(video, str) or not Path(video).is_file():
        raise ValueError("Renderer returned no downloaded video asset")
    return video


def execute_render(worker, packet, plan, token):
    trace = {"stage": "validate_locked_plan", "submission_state": "not_submitted"}
    try:
        return _execute_render(worker, packet, plan, token, trace)
    except Exception as exc:
        exc.render_diagnostic = trace
        report = render_failure_report(exc, packet, token)
        exc.render_diagnostic = report
        assets = trace.pop("_failure_assets", None)
        report.pop("_failure_assets", None)
        if assets:
            video, directory = assets
            failure_file = Path(directory) / "render_failure.json"
            source_file = Path(directory) / "source_supervisor_packet.json"
            try:
                failure_file.write_text(json.dumps(report, ensure_ascii=False, indent=2))
                source_file.write_text(json.dumps(packet, ensure_ascii=False, indent=2))
                exc.render_failure_assets = (video, str(failure_file), str(source_file))
            except OSError:
                # Evidence remains available even if writing a companion file fails.
                exc.render_failure_assets = (video, None, None)
        exc.render_diagnostic = report
        print("JOAT_RENDER_FAILURE " + json.dumps(report, ensure_ascii=False), flush=True)
        raise


def check_render_connection(worker, packet, plan, token):
    from gradio_client import Client
    import huggingface_hub
    trace = {"stage": "check_locked_plan", "submission_state": "not_submitted"}
    client = None
    try:
        if plan != prepare_plan(worker, packet):
            raise ValueError("Render plan changed after preparation")
        from joat_studio_capabilities import guard_render_parameters
        guard_render_parameters(plan['parameters'])
        _assert_renderer_connection_ready()
        trace["stage"] = "check_renderer_revision"
        if huggingface_hub.HfApi(token=token).space_info(CONTRACT['space']).sha != CONTRACT['revision']:
            raise ValueError("Renderer source changed; re-audit before spending GPU quota")
        directory = Path(tempfile.mkdtemp(prefix="joat-preflight-"))
        trace["stage"] = "verify_identity_evidence"
        identity_check = verify_identity_evidence(plan, directory)
        hashes = {}
        for key, reference in plan['references'].items():
            trace["stage"] = "check_reference:" + key
            original = download_reference(reference, directory)
            transformed = transform_reference(original, plan['reference_transform'], directory)
            hashes[key] = file_hash(transformed)
        trace["stage"] = "connect_renderer"
        client = _renderer_client(token, httpx_kwargs={"timeout": 60})
        trace["stage"] = "check_renderer_api"
        params = client.view_api(return_format='dict', print_info=False)['named_endpoints']['/generate']['parameters']
        if [p['parameter_name'] for p in params] != [p['name'] for p in CONTRACT['parameters']]:
            raise ValueError("Renderer API changed; no GPU call made")
        for parameter in params:
            choices = parameter.get('type', {}).get('enum')
            if choices and plan['parameters'][parameter['parameter_name']] not in choices:
                raise ValueError("Unsupported renderer input: " + parameter['parameter_name'])
        trace['stage'] = 'check_renderer_runtime'
        runtime = _check_runtime(client, plan)
        return {"schema": "joat.render_connection_check.v1", "status": "passed", "gpu_called": False,
                "source_job_fingerprint": plan['source_job_fingerprint'],
                "renderer_revision": CONTRACT['revision'], "parameter_count": len(params),
                "locked_reference_hashes_verified": True, "transformed_reference_hashes": hashes,
                "identity_evidence": identity_check,
                "renderer_runtime": runtime,
                "note": "Connection and locked assets verified. GPU allocation and video quality still require a render."}
    except Exception as exc:
        exc.render_diagnostic = trace
        raise
    finally:
        if client is not None:
            client.close()


def _execute_render(worker, packet, plan, token, trace):
    from gradio_client import Client, handle_file
    import huggingface_hub
    # An altered retained plan is never accepted, even if the caller supplies a matching job ID.
    if plan != prepare_plan(worker, packet):
        raise ValueError('Render plan changed after preparation')
    from joat_studio_capabilities import guard_render_parameters
    guard_render_parameters(plan['parameters'])
    _assert_renderer_connection_ready()
    trace['stage'] = 'check_renderer_revision'
    metadata = huggingface_hub.HfApi(token=token).space_info(CONTRACT['space'])
    if metadata.sha != CONTRACT['revision']:
        raise ValueError('Renderer source changed; re-audit before spending GPU quota')
    directory = Path(tempfile.mkdtemp(prefix='joat-render-'))
    trace['stage'] = 'verify_identity_evidence'
    identity_check = verify_identity_evidence(plan, directory)
    params = dict(plan['parameters'])
    transformed_hashes = {}
    for key, reference in plan['references'].items():
        trace['stage'] = 'download_reference:' + key
        original = download_reference(reference, directory)
        trace['stage'] = 'transform_reference:' + key
        transformed = transform_reference(original, plan['reference_transform'], directory)
        transformed_hashes[key] = file_hash(transformed)
        params[key] = handle_file(str(transformed))
    client = None
    try:
        trace['stage'] = 'connect_renderer'
        client = _renderer_client(token, download_files=directory, httpx_kwargs={'timeout': 60})
        trace['stage'] = 'check_renderer_api'
        live = client.view_api(return_format='dict', print_info=False)['named_endpoints']['/generate']['parameters']
        names = [p['parameter_name'] for p in live]
        if names != [p['name'] for p in CONTRACT['parameters']]:
            raise ValueError('Renderer API changed; no GPU call made')
        trace['stage'] = 'check_renderer_runtime'
        runtime = _check_runtime(client, plan)
        trace['gpu_reservation'] = runtime['budget']
        trace['stage'] = 'submit_renderer'
        trace['submission_state'] = 'submission_started'
        job = client.submit(*[params[name] for name in names], api_name='/generate')
        trace['stage'] = 'wait_for_renderer_or_download'
        trace['submission_state'] = 'submitted'
        response = job.result(timeout=900)
        trace['submission_state'] = 'response_received'
    except ValueError:
        raise
    except Exception as exc:
        trace.update(getattr(exc, 'connection_diagnostic', {}))
        trace['error_type'] = type(exc).__name__
        trace['error_message'] = _safe_error(exc, token)
        raise RuntimeError('Renderer request failed or timed out; outcome may be unknown. No automatic retry was made.') from None
    finally:
        if client is not None:
            client.close()
    trace['stage'] = 'read_downloaded_video'
    # Current SDK keeps VideoData as a dictionary; old SDKs returned a tuple.
    video = _downloaded_video_path(response)
    trace['stage'] = 'inspect_actual_mp4'
    try:
        media = inspect_video(video, packet['generation_job']['generation_specification'])
    except ValueError as exc:
        evidence = getattr(exc, "media_evidence", None)
        if evidence:
            trace["media_evidence"] = evidence
            trace["technical_validation_passed"] = False
            trace["diagnostic_video_only"] = True
            trace["_failure_assets"] = (video, str(directory))
        raise
    trace['stage'] = 'register_result'
    result = worker.build_result(packet['generation_job'], status='completed', attempt_number=1, output_path=video,
                                 output_sha256=media['sha256'], model_name=CONTRACT['space'],
                                 model_version=CONTRACT['revision'])
    result['media_rendered'] = True
    result['identity_evidence'] = identity_check
    result['media_evidence'] = media
    result['render_provenance'] = {'renderer_revision': CONTRACT['revision'], 'parameters': plan['parameters'],
                                   'renderer_runtime': runtime, 'prompt_compilation': plan['prompt_compilation'],
                                   'execution_fingerprint': plan['execution_fingerprint'],
                                   'locked_reference_hashes': {k: v['sha256'] for k, v in plan['references'].items()},
                                   'reference_transform': plan['reference_transform'],
                                   'transformed_reference_hashes': transformed_hashes,
                                   'creative_integrity_scope': 'Source packets preserved; visual creative compliance requires independent QC',
                                   'creative_checks_require_independent_qc': True}
    result.pop('result_fingerprint', None)
    result['result_fingerprint'] = hashlib.sha256(stable(result).encode()).hexdigest()
    result_file = directory / 'generation_result.json'
    result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    supervisor_file = directory / 'source_supervisor_packet.json'
    supervisor_file.write_text(json.dumps(packet, ensure_ascii=False, indent=2))
    return result, video, str(result_file), str(supervisor_file)
