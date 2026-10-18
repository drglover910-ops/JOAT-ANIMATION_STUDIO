"""Project-scoped visible-speech requirement; not a lip-sync quality approval. File version1.0.0."""
FILE_VERSION='1.0.0'
import json,hashlib,re
from pathlib import Path
ROOT=Path('/studio/joat-studio')
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def require_character_speech(packet,root=ROOT):
 job=packet['generation_job'];project=job['project_context']['project_id']
 if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,127}',project):raise ValueError('Invalid speech-policy project.')
 path=Path(root)/'production-projects'/project/'requirements'/'character_speech.json'
 if any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('Speech policy links rejected.')
 if not path.exists():return False
 if path.stat().st_size>32768:raise ValueError('Oversized speech requirement.')
 v=json.loads(path.read_text());given=v.pop('requirement_fingerprint',None)
 if digest(v)!=given or v.get('schema')!='joat.character_speech_policy.v1' or v.get('project_id')!=project or v.get('owner')!='Dezz-9-10' or v.get('visible_speech_required') is not True or v.get('narration_substitute_allowed') is not False:raise ValueError('Visible-speech requirement integrity failed.')
 shots=job['immutable_upstream_snapshot']['director'].get('per_shot',[])
 target=[s for s in shots if s.get('shot_id')==job['project_context']['shot_id']]
 if len(target)!=1:raise ValueError('Exact character speech shot required.')
 q=target[0].get('dialogue_narration',{});audio=target[0].get('audio_music_sfx',{}).get('instructions','')
 if not isinstance(q.get('dialogue'),str) or not q['dialogue'].strip() or q.get('narration') or 'no generated dialogue' in audio.lower():raise ValueError('This project requires visibly spoken character dialogue; a silent or voice-over shot cannot be rendered as its substitute.')
 return True
