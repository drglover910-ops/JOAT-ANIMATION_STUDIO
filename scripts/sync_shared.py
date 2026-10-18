"""Synchronize reviewed shared sources into deployment packages. File version: 1.0.0."""
from pathlib import Path
import argparse
import shutil

FILE_VERSION = '1.0.0'
ROOT = Path(__file__).resolve().parents[1]
FRAME_MODULES = {'joat_project_frame_reference.py', 'joat_job_frame_binding.py'}

def sync(check=False):
    failures = []
    for source in sorted((ROOT/'shared').rglob('*')):
        if not source.is_file() or '__pycache__' in source.parts or source.suffix == '.pyc':
            continue
        targets = ('main', 'control/departments/generation_worker') if source.name in FRAME_MODULES else ('main', 'control')
        if source.name == 'joat_visible_cast.py':
            targets = ('main', 'control', 'control/departments/generation_worker')
        for app in targets:
            target = ROOT/'apps'/app/source.relative_to(ROOT/'shared')
            if check:
                if not target.is_file() or target.read_bytes() != source.read_bytes():
                    failures.append(str(target.relative_to(ROOT)))
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
    if failures:
        raise SystemExit('Shared sources differ: '+', '.join(failures))
    print('Shared production sources match Main and Studio Control.' if check else 'Shared copies synchronized.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    sync(parser.parse_args().check)
