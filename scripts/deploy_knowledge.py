"""Deploy only reviewed CPU source changes; preserve runtime bindings and GPU hold.

File version: 1.0.0. Requires existing HF authentication; no secret creation.
"""
import hashlib
import json
import os
from pathlib import Path
from huggingface_hub import HfApi, CommitOperationAdd, hf_hub_download

FILE_VERSION = '1.0.0'
ROOT = Path(__file__).resolve().parents[1]
BASELINE = json.loads((ROOT/'releases/audited_baseline_v1.0.0.json').read_text())
TOKEN = os.environ['HF_TOKEN']
API = HfApi(token=TOKEN)


def changes(component):
    old = {x['path']: x['sha256'] for x in BASELINE['repositories'][component]['files']}
    names = set(old)
    for p in (ROOT/'shared').rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:
            names.add(p.relative_to(ROOT/'shared').as_posix())
    result = []
    for name in sorted(names):
        path = ROOT/'apps'/component/name
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != old.get(name):
            result.append(CommitOperationAdd(path_in_repo=name, path_or_fileobj=str(path)))
    return result


def deploy(component, expected_revision):
    repo = BASELINE['repositories'][component]['repo']
    info = API.space_info(repo)
    if info.sha != expected_revision or not info.private:
        raise ValueError('Deployment source changed or target is not private: '+component)
    if str(info.runtime.hardware) != 'cpu-basic':
        raise ValueError('Keep existing free CPU hardware.')
    if component == 'control':
        variables = API.get_space_variables(repo)
        if variables.get('JOAT_STUDIO_GPU_HOLD') is None or variables['JOAT_STUDIO_GPU_HOLD'].value != 'true':
            raise ValueError('GPU hold must remain true during CPU release.')
    operations = changes(component)
    commit = API.create_commit(repo_id=repo, repo_type='space', operations=operations,
        parent_commit=expected_revision,
        commit_message='Add scoped reviewed production guidance; preserve Main/Director and department boundaries')
    verified = []
    for op in operations:
        cached = hf_hub_download(repo, op.path_in_repo, repo_type='space', revision=commit.oid, token=TOKEN)
        if Path(cached).read_bytes() != Path(op.path_or_fileobj).read_bytes():
            raise ValueError('Deployed source readback differs: '+op.path_in_repo)
        verified.append(op.path_in_repo)
    return {'repo':repo, 'revision':commit.oid, 'parent_revision':expected_revision,
            'verified_files':verified, 'gpu_called':False}


def main():
    receipt_path = ROOT/'releases/knowledge_deployment_v1.0.0.json'
    if receipt_path.exists():
        raise ValueError('Deployment receipt already exists; inspect outcome instead of repeating.')
    receipt = {'schema':'joat.knowledge_deployment.v1', 'file_version':FILE_VERSION,
               'gpu_called':False, 'hardware_changed':False, 'components':{}}
    control = deploy('control', BASELINE['repositories']['control']['revision'])
    receipt['components']['control'] = control
    receipt_path.write_text(json.dumps(receipt, indent=2)+'\n')
    # Existing endpoint schemas and IDs were compared in the correct Space context.
    contract_check = Path('/workspace/joat-implementation/audit-2026-10-18/control_knowledge_contract_check_v1.0.1.json')
    if json.loads(contract_check.read_text())['old_endpoint_schema_differences']:
        raise ValueError('Main Control metadata requires refresh before deployment.')
    pin = ROOT/'apps/main/joat_control_contract.py'
    source = pin.read_text()
    source = source.replace('File version 1.0.14', 'File version 1.0.15').replace("FILE_VERSION='1.0.14'", "FILE_VERSION='1.0.15'")
    source = source.replace(BASELINE['repositories']['control']['revision'], control['revision'])
    pin.write_text(source)
    main_result = deploy('main', BASELINE['repositories']['main']['revision'])
    receipt['components']['main'] = main_result
    receipt['status'] = 'source_readback_verified_runtime_pending'
    receipt_path.write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({'status':receipt['status'], 'main_revision':main_result['revision'],
                      'control_revision':control['revision'], 'gpu_called':False}))


if __name__ == '__main__':
    main()
