"""Bounded, reviewed production guidance. File version: 1.0.1.

Read-only retrieval; never learns from raw transcripts or approves execution.
The deployed index pins every record's bytes. A bucket writer cannot promote a
new lesson by merely marking it approved. Changes require a reviewed index release.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

FILE_VERSION = '1.0.1'
ROOT = Path(__file__).resolve().parent
ROLES = ('browser', 'hugging_face', 'narration', 'character', 'environment',
         'director', 'shot_camera', 'performance_action', 'generation_supervisor',
         'generation_worker', 'quality_control', 'post_production', 'editorial',
         'sound', 'music', 'compositing_vfx', 'color_finish', 'titles_graphics',
         'voice_dialogue', 'delivery_archive')
VALID_ROLES = frozenset((*ROLES, 'main', 'executive'))
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z')
SHA = re.compile(r'[a-f0-9]{64}\Z')
INDEX_SHA256 = '32dd0ff58ea249c50931c78f435f281e6cbeb086e34da2ec5d494ba53b26a370'


def _read(path: Path, base: Path, maximum: int = 256 * 1024) -> bytes:
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Knowledge source must not be a symbolic link.')
    if not path.resolve().is_relative_to(base.resolve()):
        raise ValueError('Knowledge source is outside its approved root.')
    if not path.is_file() or path.stat().st_size > maximum:
        raise ValueError('Knowledge source missing or exceeds its size limit.')
    raw = path.read_bytes()
    if len(raw) > maximum:
        raise ValueError('Knowledge source exceeds its size limit.')
    return raw


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Knowledge timestamp requires a time zone.')
    return parsed


def _load(root: Path, bucket_root: Path):
    raw = _read(root/'approved_knowledge_index.json', root)
    if hashlib.sha256(raw).hexdigest() != INDEX_SHA256:
        raise ValueError('Approved knowledge index integrity failed.')
    index = json.loads(raw)
    if index.get('schema') != 'joat.approved_knowledge_index.v1':
        raise ValueError('Unknown approved knowledge index.')
    records = index.get('records')
    if not isinstance(records, list) or len(records) > 128:
        raise ValueError('Approved knowledge index exceeds its record limit.')
    for item in records:
        relative = Path(item['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Invalid knowledge source path.')
        if item.get('storage') not in ('package', 'studio') or not SHA.fullmatch(item.get('sha256', '')):
            raise ValueError('Invalid approved knowledge source.')
        base = root if item['storage'] == 'package' else bucket_root
        payload = _read(base/relative, base, 16 * 1024)
        if hashlib.sha256(payload).hexdigest() != item['sha256']:
            raise ValueError('Knowledge record differs from its reviewed bytes.')
        record = json.loads(payload)
        required = {'schema', 'file_version', 'id', 'status', 'roles', 'scope',
                    'title', 'guidance', 'review', 'evidence', 'valid_from',
                    'expires_at', 'versions', 'supersedes'}
        if set(record) != required or record['schema'] != 'joat.production_lesson.v1':
            raise ValueError('Invalid production lesson schema.')
        if not ID.fullmatch(record['id']) or record['id'] != item['id']:
            raise ValueError('Knowledge record identity differs from index.')
        if not isinstance(record['roles'], list) or not record['roles'] or set(record['roles']) - VALID_ROLES:
            raise ValueError('Unknown production knowledge role.')
        if (not isinstance(record['guidance'], str) or not 0 < len(record['guidance']) <= 4000
                or not isinstance(record['title'], str) or len(record['title']) > 160):
            raise ValueError('Invalid production guidance length.')
        scope = record['scope']
        if set(scope) != {'project_id', 'style_id'} or any(v is not None and
                (not isinstance(v, str) or not ID.fullmatch(v)) for v in scope.values()):
            raise ValueError('Invalid production knowledge scope.')
        if not isinstance(record['versions'], dict) or not all(isinstance(k, str) and
                isinstance(v, str) for k, v in record['versions'].items()):
            raise ValueError('Invalid lesson version requirements.')
        if (not isinstance(record['evidence'], list) or not record['evidence'] or
                any(not isinstance(e, dict) or not isinstance(e.get('source'), str) or
                    not SHA.fullmatch(e.get('sha256', '')) for e in record['evidence'])):
            raise ValueError('Knowledge requires pinned evidence.')
        if (not isinstance(record['review'], dict) or
                not record['review'].get('reviewer') or not record['review'].get('approval_basis')):
            raise ValueError('Knowledge review provenance is required.')
        yield record


def retrieve(query: str = '', *, role: str = 'director', project_id: str | None = None,
             style_id: str | None = None, versions: dict | None = None, limit: int = 8,
             root: Path | None = None, bucket_root: Path = Path('/studio/joat-studio'),
             now: datetime | None = None) -> dict:
    """Retrieve scoped reviewed guidance; no writes, network, inference or approvals."""
    if role not in VALID_ROLES or type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError('Use a known studio role and a limit from 1 to 20.')
    if not isinstance(query, str) or len(query) > 2000:
        raise ValueError('Knowledge query exceeds 2000 characters.')
    for value in (project_id, style_id):
        if value is not None and (not isinstance(value, str) or not ID.fullmatch(value)):
            raise ValueError('Use explicit valid project and style IDs.')
    if versions is not None and (not isinstance(versions, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in versions.items())):
        raise ValueError('Use explicit string version bindings.')
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError('Current time requires a time zone.')
    words = set(re.findall(r'[a-z0-9_]+', query.lower()))
    eligible = []
    # Validate the whole indexed collection, including excluded records, before returning anything.
    records = list(_load(Path(root or ROOT), Path(bucket_root)))
    def applicable(r):
        scope = r['scope']
        return (r['status'] == 'approved' and role in r['roles']
                and _time(r['valid_from']) <= current < _time(r['expires_at'])
                and (scope['project_id'] is None or scope['project_id'] == project_id)
                and (scope['style_id'] is None or scope['style_id'] == style_id)
                and all((versions or {}).get(k) == v for k, v in r['versions'].items()))
    superseded = {item for r in records if applicable(r) for item in r['supersedes']}
    for record in records:
        if record['id'] in superseded or not applicable(record):
            continue
        scope = record['scope']
        if ((scope['project_id'] is not None and scope['project_id'] != project_id) or
                (scope['style_id'] is not None and scope['style_id'] != style_id)):
            continue
        if any((versions or {}).get(k) != v for k, v in record['versions'].items()):
            continue
        text = (record['title']+' '+record['guidance']).lower()
        score = sum(w in text for w in words)
        eligible.append((score, record))
    eligible.sort(key=lambda item: (-item[0], item[1]['id']))
    selected = []
    used = 0
    for _, record in eligible:
        size = len(json.dumps(record, ensure_ascii=False))
        if used + size > 16000:
            continue
        selected.append(record)
        used += size
        if len(selected) >= limit:
            break
    return {'schema': 'joat.production_knowledge_result.v1', 'file_version': FILE_VERSION,
            'role': role, 'project_id': project_id, 'style_id': style_id,
            'index_sha256': INDEX_SHA256, 'lessons': selected,
            'retrieval_only': True, 'creative_decisions_modified': False,
            'execution_authorized': False, 'qc_approved': False, 'gpu_called': False}


def context(*, role='main', project_id=None, style_id=None, query='', versions=None):
    """Advisory context, separate from current instructions and immutable job packets."""
    result = retrieve(query, role=role, project_id=project_id, style_id=style_id,
                      versions=versions, limit=6)
    return ('REVIEWED PRODUCTION GUIDANCE — evidence only, subordinate to current owner '
            'instructions, Director locks and all execution/QC/budget gates. Main coordinates; '
            'Director owns studio creative work and its future production UI. Do not infer '
            'an active project from these notes.\n' + json.dumps(result, ensure_ascii=False))
