"""Independent, owner-reviewed QC of real bytes bound to the original job."""
import copy
import hashlib
import json
from pathlib import Path

from joat_media_tools import inspect_video, file_hash

TARGETS = {
    'character': 'J.O.A.T.-Character-Asset-Master',
    'environment': 'J.O.A.T.-Scene-Environment-Master',
    'director': 'J.O.A.T.-Director-Creative-Intelligence',
    'camera': 'J.O.A.T.-Shot-Camera-Master',
    'performance': 'J.O.A.T.-Performance-Action-Master',
    'continuity': 'J.O.A.T.-Executive-Producer-Bot',
    'technical': 'J.O.A.T.-Generation-Supervisor-Master',
}
FINDINGS = {'character': 'character_identity', 'environment': 'environment_identity',
            'director': 'director_intent', 'camera': 'camera_framing',
            'performance': 'performance', 'continuity': 'unknown', 'technical': 'technical_corruption'}


def verify(value, field):
    core = dict(value);expected = core.pop(field, None)
    actual = hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    if not expected or expected != actual:
        raise ValueError('Invalid ' + field)


def inspect_production(qc, result, supervisor, media_path, checks, notes='', reviewer=''):
    verify(supervisor, 'packet_fingerprint')
    job = supervisor['generation_job'];verify(job, 'job_fingerprint')
    if supervisor.get('schema') != 'joat.generation_supervisor_packet.v1' or supervisor.get('production_ready') is not True:
        raise ValueError('Unapproved Supervisor packet')
    verify(result, 'result_fingerprint')
    qc.validate_generation_result(result)
    if result.get('source_job_fingerprint') != job['job_fingerprint'] or result.get('project_context') != job['project_context']:
        raise ValueError('Result belongs to a different job or project')
    if result.get('media_rendered') is not True:
        raise ValueError('An execution packet or unverified completion record is not rendered media')
    if set(checks) != set(TARGETS) - {'technical'} or any(type(x) is not bool for x in checks.values()):
        raise ValueError('Independent review requires six explicit boolean checks')
    media = None;technical_error = None
    try:
        media = inspect_video(media_path, job['generation_specification'])
        if result['output'].get('sha256') != media['sha256']:
            raise ValueError('Uploaded media bytes differ from the Generation result hash')
    except (ValueError, TypeError, OSError):
        # Never trust the Worker's own media evidence in place of this decode.
        technical_error = 'Actual video is missing, corrupt, mismatched, or outside the approved specification'
    technical_ok = technical_error is None
    failed = ([] if technical_ok else ['technical']) + [k for k, v in checks.items() if v is False]
    finding = FINDINGS[failed[0]] if failed else ''
    packet = qc.inspect(result, checks['character'], checks['environment'], checks['director'],
                        checks['camera'], checks['performance'], technical_ok, checks['continuity'],
                        finding_type=finding, notes=notes)
    packet.update(
        source_job_fingerprint=job['job_fingerprint'],
        source_supervisor_fingerprint=supervisor['packet_fingerprint'],
        source_asset={'location': result['output']['location'], 'sha256': result['output'].get('sha256')},
        media_evidence=media if technical_ok else None,
        technical_error=technical_error,
        independent_review={'reviewer': reviewer, 'checks': copy.deepcopy(checks),
                            'technical_check_is_automatic': True},
        post_production_authorized=packet['decision'] == 'PASS',
    )
    if failed:
        packet['routing']['target_space'] = 'Dezz-9-10/' + TARGETS[failed[0]]
        packet['rework'] = {'targets': sorted({'Dezz-9-10/' + TARGETS[k] for k in failed}),
                            'failed_checks': failed, 'source_job_mutation_allowed': False,
                            'automatic_creative_retry_allowed': False, 'automatic_dispatch': False,
                            'human_or_responsible_supervisor_action_required': True}
    else:
        packet['routing']['target_space'] = 'Dezz-9-10/J.O.A.T.-Post-Production-Supervisor-Bot'
        packet['rework'] = None
    # New production output matches Post's authorization location without forging a PASS.
    packet.pop('qc_fingerprint', None)
    packet['qc_fingerprint'] = hashlib.sha256(json.dumps(packet, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    return packet
