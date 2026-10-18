"""Controlled Post6 handoffs with actual downloaded media, receipt checks and final QC."""
from copy import deepcopy
from pathlib import Path
import tempfile

from joat_post_media import (DEPARTMENTS, SPACES, seal, verify, production_qc, inspect_video,
                            file_hash, verify_department, write_json, audio_evidence)


def prepare_post(qc, technical_plan, media):
    evidence = production_qc(qc)
    specification = {'duration_seconds': evidence['duration_seconds'], 'aspect_ratio':
                     str(evidence['width']) + ':' + str(evidence['height'])}
    actual = inspect_video(media, specification)
    if actual['sha256'] != evidence['sha256']:
        raise ValueError('Post input differs from independently QC-approved media')
    if set(technical_plan) != set(DEPARTMENTS):
        raise ValueError('An explicit operation for all six departments is required')
    if qc.get('project_context', {}).get('project_id') is None:
        raise ValueError('QC project context missing')
    return seal({'schema': 'joat.production_post_plan.v1', 'qc_packet': deepcopy(qc),
                 'project_context': deepcopy(qc['project_context']), 'input_sha256': actual['sha256'],
                 'input_specification': specification, 'operations': deepcopy(technical_plan),
                 'owner_approval_required': True, 'final_qc_required': True}, 'plan_fingerprint')


def make_order(plan, department, current_sha, specification):
    verify(plan, 'plan_fingerprint');production_qc(plan['qc_packet'])
    return seal({'schema': 'joat.post_work_order.v1', 'department': department,
                 'assigned_space': 'Dezz-9-10/' + SPACES[department],
                 'project_context': plan['project_context'], 'qc_packet': plan['qc_packet'],
                 'input_sha256': current_sha, 'input_specification': specification,
                 'source_post_plan_fingerprint': plan['plan_fingerprint'],
                 'operation': plan['operations'][department], 'owner_approved': True,
                 'creative_changes_authorized': False}, 'work_order_fingerprint')


def execute_post(plan, media, auxiliary_files, token, transport=None):
    from gradio_client import Client, handle_file
    verify(plan, 'plan_fingerprint');production_qc(plan['qc_packet'])
    # This function is called only after the UI/API authenticates the owner and approves this exact plan.
    original = inspect_video(media, plan['input_specification'])
    if original['sha256'] != plan['input_sha256']:
        raise ValueError('Retained source media changed')
    directory = Path(tempfile.mkdtemp(prefix='joat-post6-'))
    current, specification = media, plan['input_specification']
    receipts = {}
    files_by_hash = {file_hash(p): p for p in (auxiliary_files or [])}
    for department in DEPARTMENTS:
        order = make_order(plan, department, file_hash(current), specification)
        operation = order['operation']
        required_hash = operation.get('approved_audio_sha256') or operation.get('approved_overlay_sha256')
        auxiliary = files_by_hash.get(required_hash)
        if required_hash and auxiliary is None:
            raise ValueError('Approved auxiliary file not supplied for ' + department)
        order_file = write_json(directory, department + '_order.json', order)
        if transport:
            result, output, result_file = transport(department, order_file, current, auxiliary)
        else:
            client = None
            try:
                client = Client('Dezz-9-10/' + SPACES[department], token=token, verbose=False, download_files=directory)
                result, output, result_file = client.submit(handle_file(order_file), handle_file(str(current)),
                    handle_file(str(auxiliary)) if auxiliary else None, True, api_name='/execute_production_media').result(timeout=420)
            except Exception:
                raise RuntimeError('Post department handoff failed: ' + department + '. No automatic retry; review returned artifacts before resuming.') from None
            finally:
                if client:
                    client.close()
        if isinstance(output, (tuple, list)):
            output = output[0]
        verify_department(result, order, output)
        receipts[department] = {'order': order, 'result': result}
        current, specification = output, result['output_specification']
    final = inspect_video(current, specification)
    if final['audio_present']:
        audio_evidence(current)
    result = seal({'schema': 'joat.post_production_result.v1', 'app_version': '1.0.1',
                   'project_context': plan['project_context'], 'source_post_packet_fingerprint': plan['plan_fingerprint'],
                   'source_qc_fingerprint': plan['qc_packet']['qc_fingerprint'],
                   'source_job_fingerprint': plan['qc_packet']['source_job_fingerprint'],
                   'department_results': receipts, 'specialist_results': {k: v['result'] for k, v in receipts.items()},
                   'final_master': dict(final, asset_id='MASTER-' + final['sha256'][:16], specification=specification),
                   'final_master_uri': str(current), 'post_complete': True, 'status': 'awaiting_final_qc',
                   'creative_integrity_preserved': False, 'delivery_authorized': False,
                   'handoff': {'ready_for_delivery_archive': False}, 'final_qc': None}, 'result_fingerprint')
    return result, str(current), write_json(directory, 'post_result_awaiting_final_qc.json', result)


def final_review(result, media, checks, reviewer):
    verify(result, 'result_fingerprint')
    if reviewer != 'Dezz-9-10' or set(checks) != {'picture', 'audio', 'titles', 'continuity'} or any(type(v) is not bool for v in checks.values()):
        raise ValueError('Four explicit final owner review checks are required')
    if result.get('schema') not in ('joat.post_production_result.v1', 'joat.timeline_result.v1'):
        raise ValueError('Post or timeline result required')
    if result['schema'] == 'joat.post_production_result.v1':
        validate_post_receipts(result)
    elif not result.get('ordered_shots') or result.get('final_qc_required') is not True:
        raise ValueError('Timeline provenance is missing')
    evidence = inspect_video(media, result['final_master']['specification'])
    if evidence['sha256'] != result['final_master']['sha256']:
        raise ValueError('Final reviewed media differs from registered master')
    if evidence['audio_present']:
        audio_evidence(media)
    passed = all(checks.values())
    output = deepcopy(result)
    output.update(status='completed' if passed else 'rejected_final_qc',
                  creative_integrity_preserved=passed, delivery_authorized=passed,
                  final_qc={'decision': 'PASS' if passed else 'REJECT', 'reviewer': reviewer,
                            'checks': deepcopy(checks), 'asset_sha256': evidence['sha256'],
                            'technical_decode_verified': True},
                  handoff={'ready_for_delivery_archive': passed})
    return seal(output, 'result_fingerprint')


def validate_post_receipts(result):
    receipts = result.get('department_results', {})
    if set(receipts) != set(DEPARTMENTS) or result.get('post_complete') is not True:
        raise ValueError('Six real department receipts are required')
    previous = None
    for role in DEPARTMENTS:
        order, receipt = receipts[role]['order'], receipts[role]['result']
        verify(order, 'work_order_fingerprint');verify(receipt, 'result_fingerprint')
        production_qc(order['qc_packet'])
        if previous is None:
            previous = order['qc_packet']['source_asset']['sha256']
        if (order.get('department') != role or order.get('assigned_space') != 'Dezz-9-10/' + SPACES[role]
                or order.get('input_sha256') != previous or receipt.get('input_sha256') != previous
                or receipt.get('source_work_order_fingerprint') != order['work_order_fingerprint']
                or receipt.get('status') != 'completed' or receipt.get('operation') != order['operation']
                or receipt.get('source_qc_fingerprint') != result.get('source_qc_fingerprint')
                or receipt.get('source_job_fingerprint') != result.get('source_job_fingerprint')
                or order.get('source_post_plan_fingerprint') != result.get('source_post_packet_fingerprint')):
            raise ValueError('Invalid department receipt chain')
        previous = receipt['output']['sha256']
    if previous != result['final_master']['sha256']:
        raise ValueError('Final master is not the completed department-chain output')
