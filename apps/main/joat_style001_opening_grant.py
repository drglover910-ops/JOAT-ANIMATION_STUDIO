"""Issue the one opening grant approved in owner chat. File version 1.0.2.
No rendering, retries, further shots, final QC, or credit purchases authorized.
"""
FILE_VERSION = '1.0.2'
PROJECT = 'PROJECT-OTU-STYLE001-90S-001'
MISSION = '2a881aa9651cd9058fd3f9ddaf199f1c2cbfc849b82caf511b1bcd661921868d'
PLAN = 'a70529cef9b40305b6371ed87f443621595232b7acec794ba802213516e2f221'
JOB = '222eedbf801f0a847e0fe2f470d3c7d211e5ab08a668c8a19027d2400ce51227'
SUPERVISOR = '8d0657bcdcacd16bae2eae587d05ac083e533d00ac0f089817b9bee6f411df79'
CONNECTION = '4d348bec71d94a029f4e12e2a23ea14a'
STATEMENT = "Okay, we're fine. Continue to finish."

def authorize(mission, payload, directory):
    if payload.get("plan_fingerprint") == REVISED_PLAN:
        return authorize_reduced(mission, payload, directory)
    import joat_managed_generation as m
    from joat_remote_generation import source_for, prepared_path, grant
    if mission.get('project_id') != PROJECT or mission.get('plan_fingerprint') != MISSION:
        raise ValueError('Only the approved Style001 opening mission is authorized.')
    if payload != {'owner_statement': STATEMENT, 'plan_fingerprint': PLAN}:
        raise ValueError('Exact opening-only owner authorization required.')
    packet = source_for(PROJECT, JOB, SUPERVISOR)
    prepared = m.read_json(prepared_path(m.ROOT, packet, PLAN))
    plan = prepared['plan']
    if m.digest(plan) != PLAN:
        raise ValueError('Opening plan integrity failed.')
    params = plan['parameters']
    if (params['seconds'], params['max_width'], params['max_height'], params['input_mode'], params['gen_budget']) != (5, 576, 1024, 'single image (i2v)', 600):
        raise ValueError('Approved opening settings differ.')
    check = m.read_json(m.ROOT/'remote-generation'/'requests'/CONNECTION/'connection_check.json')
    checked = m.read_json(m.ROOT/'remote-generation'/'requests'/CONNECTION/'request.json')
    if (check.get('status') != 'passed' or check.get('gpu_called') is not False or check.get('source_job_fingerprint') != JOB or checked.get('plan_fingerprint') != PLAN):
        raise ValueError('The approved opening lacks its successful exact-plan connection check.')
    # One project/plan ledger prevents a second task from minting another grant.
    ledger = m.ROOT/'production-projects'/PROJECT/'opening-authorization'/PLAN
    m.write_once(ledger/'reservation.json', dict(file_version=FILE_VERSION, owner=m.OWNER, owner_statement=STATEMENT, plan_fingerprint=PLAN, maximum_attempts=1, estimated_credit_cost_usd=[0, 0.89], estimate_is_not_enforced_billing_cap=True, credit_purchase_authorized=False, further_shots_authorized=False, automatic_retry=False))
    issued = grant(packet, plan, True)
    m.write_once(ledger/'grant.json', issued)
    m.write_once(directory/'grant.json', issued)
    return dict(status='exact_opening_grant_issued_no_render', gpu_called=False, grant_id=issued['grant_id'], plan_fingerprint=PLAN, maximum_attempts=1, gpu_ceiling_seconds=600, further_shots_authorized=False, production_qc_approved=False)


REVISED_PLAN = 'b4bbe8c6c9c086a59f9373ac504ac071103278bbdcf2e8981720eeca7ac2dcfe'
DENIED_EXECUTION = '81dee8a497874c66a2bb2bae07af838e'

def authorize_reduced(mission, payload, directory):
    import copy, re
    import joat_managed_generation as m
    from joat_remote_generation import source_for, prepared_path, grant
    if mission.get('project_id') != PROJECT or mission.get('plan_fingerprint') != MISSION:
        raise ValueError('Only the existing approved opening mission is authorized.')
    if set(payload) != {'owner_statement', 'plan_fingerprint', 'connection_request_id'} or payload['owner_statement'] != STATEMENT or payload['plan_fingerprint'] != REVISED_PLAN or not re.fullmatch('[a-f0-9]{32}', str(payload['connection_request_id'])):
        raise ValueError('Exact reduced-ceiling opening authorization required.')
    failed = m.ROOT/'remote-generation'/'requests'/DENIED_EXECUTION
    outcome = m.read_json(failed/'artifacts'/'generation_result.json')
    request = m.read_json(failed/'request.json')
    if (outcome.get('status') != 'render_failed' or outcome.get('source_job_fingerprint') != JOB or outcome.get('error_type') != 'AppError' or not outcome.get('error_message', '').startswith('You have exceeded your Pro ZeroGPU quota (900s requested vs. 668s left).') or request.get('plan_fingerprint') != PLAN or request.get('grant_id') != '21335921c0c74dba8ac73bcd918360c0'):
        raise ValueError('Confirmed original provider quota rejection required; never retry an uncertain GPU outcome.')
    packet = source_for(PROJECT, JOB, SUPERVISOR)
    previous = m.read_json(prepared_path(m.ROOT, packet, PLAN))['plan']
    plan = m.read_json(prepared_path(m.ROOT, packet, REVISED_PLAN))['plan']
    expected = copy.deepcopy(previous)
    expected['renderer_revision'] = 'be1591ad2ad05c3af51f27fd671658d1873e15af'
    expected['parameters']['gen_budget'] = 420
    expected['gpu_reservation']['requested_seconds'] = 420
    expected['gpu_reservation']['note'] = 'One approved composed-frame I2V shot. Explicit420second allocation ceiling; no automatic retry.'
    if m.digest(previous) != PLAN or m.digest(plan) != REVISED_PLAN or plan != expected:
        raise ValueError('Only allocation and the audited CPU-preflight revision may change; all creative and inference quality settings must remain identical.')
    connection = m.ROOT/'remote-generation'/'requests'/payload['connection_request_id']
    checked = m.read_json(connection/'request.json');check = m.read_json(connection/'connection_check.json')
    if checked.get('operation') != 'check' or checked.get('project_id') != PROJECT or checked.get('plan_fingerprint') != REVISED_PLAN or check.get('status') != 'passed' or check.get('gpu_called') is not False or check.get('source_job_fingerprint') != JOB:
        raise ValueError('Reduced plan requires a successful exact CPU connection check.')
    ledger = m.ROOT/'production-projects'/PROJECT/'opening-authorization'/REVISED_PLAN
    m.write_once(ledger/'reservation.json', dict(file_version=FILE_VERSION, owner=m.OWNER, owner_statement=STATEMENT, plan_fingerprint=REVISED_PLAN, supersedes_provider_denied_execution=DENIED_EXECUTION, allocation_ceiling_reduced_from=600, allocation_ceiling_seconds=420, provider_reported_quota_seconds=668, expected_normalized_reservation_seconds=630, quota_conversion_basis='observed900/600factor1.5_not_live_billing_API', inference_quality_settings_changed=False, maximum_attempts=1, credit_purchase_authorized=False, further_shots_authorized=False, automatic_retry=False))
    issued = grant(packet, plan, True)
    m.write_once(ledger/'grant.json', issued);m.write_once(directory/'grant.json', issued)
    return dict(status='reduced_opening_grant_issued_no_render', gpu_called=False, grant_id=issued['grant_id'], plan_fingerprint=REVISED_PLAN, maximum_attempts=1, gpu_ceiling_seconds=420, further_shots_authorized=False, production_qc_approved=False)
