"""Release canonical coverage checks without GPU execution. File version: 1.0.0."""
import hashlib
import json
import os
from pathlib import Path
from huggingface_hub import HfApi, CommitOperationAdd, hf_hub_download

FILE_VERSION = '1.0.0'
ROOT = Path(__file__).resolve().parents[1]
API = HfApi(token=os.environ['HF_TOKEN'])


def deploy(component, previous, paths):
    repo = previous['repo']
    info = API.space_info(repo)
    if info.sha != previous['revision'] or not info.private or str(info.runtime.hardware) != 'cpu-basic':
        raise ValueError('Source, visibility or CPU hardware changed; review before deploying.')
    if component == 'control' and API.get_space_variables(repo)['JOAT_STUDIO_GPU_HOLD'].value != 'true':
        raise ValueError('Retain the GPU hold during this release.')
    operations = [CommitOperationAdd(path_in_repo=p, path_or_fileobj=str(ROOT/'apps'/component/p)) for p in paths]
    commit = API.create_commit(repo_id=repo, repo_type='space', operations=operations,
        parent_commit=previous['revision'], commit_message='Require canonical source coverage for every visible character; preserve legacy single-frame bindings')
    for name in paths:
        downloaded = hf_hub_download(repo, name, repo_type='space', revision=commit.oid, token=os.environ['HF_TOKEN'])
        if Path(downloaded).read_bytes() != (ROOT/'apps'/component/name).read_bytes():
            raise ValueError('Source readback differs: '+name)
    return {'repo':repo,'revision':commit.oid,'parent_revision':previous['revision'],'verified_files':paths}


def main():
    target = ROOT/'releases/visible_cast_deployment_v1.0.0.json'
    if target.exists():
        raise ValueError('Inspect the recorded release instead of redeploying.')
    previous = json.loads((ROOT/'releases/knowledge_deployment_v1.0.0.json').read_text())['components']
    paths = ['app.py','consolidated_manifest.json','joat_visible_cast.py',
             'departments/generation_worker/joat_visible_cast.py',
             'departments/generation_worker/joat_job_frame_binding.py',
             'departments/generation_worker/joat_project_frame_reference.py',
             'departments/generation_worker/joat_render_bridge.py']
    control = deploy('control',previous['control'],paths)
    receipt = {'schema':'joat.visible_cast_release.v1','file_version':FILE_VERSION,
               'gpu_called':False,'hardware_changed':False,'components':{'control':control}}
    target.write_text(json.dumps(receipt,indent=2)+'\n')
    pin = ROOT/'apps/main/joat_control_contract.py'
    s = pin.read_text().replace('File version 1.0.15','File version 1.0.16').replace("FILE_VERSION='1.0.15'","FILE_VERSION='1.0.16'")
    s = s.replace(previous['control']['revision'],control['revision'])
    pin.write_text(s)
    paths = ['app.py','joat_control_contract.py','joat_frame_assignment_task.py',
             'joat_visible_cast.py','joat_job_frame_binding.py','joat_project_frame_reference.py']
    receipt['components']['main'] = deploy('main',previous['main'],paths)
    receipt['status'] = 'source_readback_verified_runtime_pending'
    target.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'status':receipt['status'],'control_revision':control['revision'],
                     'main_revision':receipt['components']['main']['revision'],'gpu_called':False}))


if __name__ == '__main__':
    main()
