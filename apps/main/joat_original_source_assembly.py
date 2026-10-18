"""Exact owner-script CPU assembly with complete visible-cast binding. File version1.0.2.
No GPU, still acceptance, spend grant or final QC. Original native drafts remain immutable.
"""
FILE_VERSION='1.0.2'
import copy,re,json,hashlib
from pathlib import Path
import joat_managed_generation as m
import joat_creative_workflow as w
from joat_source_script_authority import verify_batches

def verify_native_draft(item):
 shot=item['shot'];director=item['director'];per=director['per_shot']
 if len(per)!=1 or per[0]['shot_id']!=shot['shot_id'] or per[0]['scene_id']!=shot['scene_id'] or item['character']['character_id']!=shot['character_id'] or item['character']['identity_locked'] is not True or item['environment']['environment_id']!=shot['environment_id'] or m.digest(director)!=item['director_sha256']:raise ValueError('Native draft identity/scene integrity differs.')
 data=per[0]
 if data['dialogue_narration']!={'shot_id':shot['shot_id'],'dialogue':shot['dialogue'],'narration':shot['narration']} or data['camera_framing']!={'shot_id':shot['shot_id'],'framing':shot['camera']['size'],'angle':shot['camera']['angle'],'movement':shot['camera']['movement']} or data['performance_action']!=dict(shot['performance'],shot_id=shot['shot_id']) or data['caption_on_screen_text']!={'shot_id':shot['shot_id'],'text':shot['caption']} or data['environment_requirements']!=shot['environment_id'] or data['character_constraints']['source_asset_hashes']!=item['character']['source_asset_hashes']:raise ValueError('Native Director changed an original shot decision.')
 # Compare the Director's encoded duration without relying on its formatting.
 parts=data['duration'].split(':')
 if len(parts)!=2 or float(parts[0])*60+float(parts[1])!=shot['duration_seconds']:raise ValueError('Native Director duration differs.')
 return item

def enrich(item,source,characters):
 item=copy.deepcopy(item);d=item['director'];original=m.digest(d);ids=[item['shot']['character_id']]+[v['character_id'] for role,v in source['cast'].items() if v['character_id']!=item['shot']['character_id']]
 for cid in ids:
  packet=characters[cid]
  if packet['character_id']!=cid or packet['identity_locked'] is not True:raise ValueError('Locked secondary character packet required.')
 # Add actual Master packets as an explicit post-API, pre-approval supplement.
 # No original Director API artifact or draft is overwritten.
 d['performance_enum_adapter']=dict(file_version=FILE_VERSION,source_spec=item['shot']['performance'],normalized_spec=typed_performance(item['shot']['performance']),scope='Typed metadata only; no change to original dialogue, visual action or allocated shot duration.')
 d['visible_cast_supplement']=dict(file_version=FILE_VERSION,source_director_sha256=original,source_shot_id=source['shot_id'],character_packets={cid:characters[cid] for cid in ids},source_asset_hashes={cid:characters[cid]['source_asset_hashes'] for cid in ids},original_visual=source['visual'],original_camera=source['camera'],lighting=source['lighting'],native_render_prompt=source['native_render_prompt'])
 existing={r['character_id']:r for r in d['character_refs']}
 for cid in ids:
  if cid not in existing:
   packet=characters[cid];ref=copy.deepcopy(packet);ref.pop('schema',None);d['character_refs'].append(ref)
 for per in d['per_shot']:
  per['character_ids']=ids
  current={r['character_id'] for r in per.get('character_packet_references',[])}
  for ref in d['character_refs']:
   if ref['character_id'] not in current:per.setdefault('character_packet_references',[]).append(copy.deepcopy(ref))
  per['all_visible_character_source_hashes']={cid:characters[cid]['source_asset_hashes'] for cid in ids}
 item['director_sha256']=m.digest(d)
 return item

def verify_character_sources(mission,cid,packet):
 snapshot=json.loads(Path(__file__).with_name('joat_source_character_registry_v1.0.0.json').read_text())
 if snapshot['source_revision']!='0a5a5f4895c2fa9ea613c32b77c338ad81e14bc2' or hashlib.sha256(snapshot['registry_raw'].encode()).hexdigest()!='76113fd3c143c9f62a735accad901e68ab4f383b4cbe590e06f2141f773f2ab5':raise ValueError('Pinned canonical registry integrity differs.')
 registry=json.loads(snapshot['registry_raw']);character=next((c for c in registry['characters'] if c['id']==cid),None)
 if character is None or character['status']!='approved_locked' or packet['character_id']!=cid or packet['identity_locked'] is not True:raise ValueError('Locked canonical character required.')
 approved={a['asset_id']:a for a in character['assets'] if a['status']=='approved'};hashes=packet['source_asset_hashes']
 selected={r['asset_id']:r['sha256'] for cast in mission['production_contract']['cast'].values() if cast['character_id']==cid for r in cast['references']}
 anchor=next((a for a in approved.values() if a['path']==packet['identity_lock_asset'] and 'identity_anchor' in a['roles']),None)
 if anchor is None or selected.get(anchor['asset_id'])!=anchor['sha256'] or hashes.get(anchor['asset_id'])!=anchor['sha256']:raise ValueError('Owner mission canonical identity anchor differs.')
 if not hashes or any(k not in approved or approved[k]['sha256']!=v or (k in selected and selected[k]!=v) for k,v in hashes.items()):raise ValueError('Character source hashes differ from pinned canonical registry or selected owner sources.')
 return dict(source_revision=snapshot['source_revision'],registry_sha256=snapshot['source_sha256'],identity_anchor_asset_id=anchor['asset_id'],verified_asset_hashes=hashes)

def typed_performance(spec):
 value=copy.deepcopy(spec)
 # Explicit translation of this compiler's descriptive metadata only.
 # All original scene/action text and timing lengths remain unchanged.
 if value['timing']['pacing']=='Natural within the exact allocated duration; preserve all words.':value['timing']['pacing']='natural'
 if value['gaze']['type']=='scene':value['gaze']['type']='director_defined'
 if value['interaction']['type']=='scene':value['interaction']['type']='environment'
 if value['timing']['pacing'] not in ('very_slow','slow','natural','quick','very_quick') or value['gaze']['type'] not in ('director_defined','camera','character','object','off_screen','down','up','left','right','forward') or value['interaction']['type'] not in ('none','character','object','environment','multiple'):raise ValueError('Unsupported performance metadata; no department call requested.')
 return value

def prepare(mission,payload,directory):
 if set(payload)!={'draft_task_id'} or not re.fullmatch('[a-f0-9]{32}',str(payload['draft_task_id'])):raise ValueError('Use an exact completed native draft task.')
 project=mission['project_id'];base=m.safe_path(m.ROOT/'production-projects'/m.valid_project(project));prior=m.safe_path(base/'tasks'/payload['draft_task_id']);receipt=m.read_json(prior/'receipt.json')
 if receipt.get('status')!='native_director_drafts_awaiting_review' or receipt.get('mission_fingerprint')!=mission['plan_fingerprint'] or receipt.get('project_id')!=project or receipt.get('gpu_called') is not False:raise ValueError('Completed exact CPU draft task required.')
 manifest=m.read_json(prior/'draft_manifest.json');states=[]
 for entry in manifest['files']:
  path=m.safe_path(prior/('drafts_'+str(entry['batch'])+'.json'));state=w.validate_state(m.read_json(path))
  if state['state_fingerprint']!=entry['state_fingerprint'] or state['creative_approved'] is not False or state['gpu_called'] is not False:raise ValueError('Original native draft state differs.')
  for item in state['drafts']:verify_native_draft(item)
  states.append(state)
 verify_batches(mission,[dict(brief=s['plan']['brief'],plan=dict(shots=s['plan']['shots'])) for s in states])
 source_shots={s['shot_id']:s for s in mission['shots'] if s['production_type']=='video'};characters={item['character']['character_id']:item['character'] for state in states for item in state['drafts']}
 ids={c['character_id'] for s in source_shots.values() for c in s['cast'].values()}
 for cid in sorted(ids-set(characters)):
  packet=w.packet(w.call(project,'character',dict(cid=cid,task='scene')),'joat.character_packet.v1')
  if packet['character_id']!=cid or packet['identity_locked'] is not True:raise ValueError('Secondary Character Master identity mismatch.')
  characters[cid]=packet
 for cid,packet in characters.items():
  verify_character_sources(mission,cid,packet)
 results=[]
 for index,state in enumerate(states):
  state=copy.deepcopy(state);original=state.pop('state_fingerprint');state['drafts']=[enrich(i,source_shots[i['shot']['shot_id']],characters) for i in state['drafts']];state['source_draft_state_fingerprint']=original;state=w.handoff.seal(state,'state_fingerprint');m.write_once(directory/('enriched_drafts_'+str(index+1)+'.json'),state)
  provenance=dict(schema='joat.original_script_packet_review.v1',file_version='1.0.0',owner=m.OWNER,reviewer='Codex',project_id=project,plan_fingerprint=state['plan']['plan_fingerprint'],source_prompt_sha256=mission['owner_source_prompt_sha256'],scope='original_owner_script_machine_verified_packet_mapping',review_statement='Owner supplied and authorized the unchanged production script. Codex verified exact native packet mapping and canonical hashes; this does not assert personal owner review of generated drafts, still acceptance, video QC or spending authorization.')
  result=w.assemble(state,True,m.OWNER,aspect_ratio='9:16',source_script_review=provenance);m.write_once(directory/('sources_'+str(index+1)+'.json'),result);results.append(result)
 summary=dict(schema='joat.original_script_source_manifest.v1',file_version=FILE_VERSION,project_id=project,mission_fingerprint=mission['plan_fingerprint'],batches=[dict(plan_fingerprint=r['plan_fingerprint'],result_fingerprint=r['result_fingerprint'],shots_prepared=r['shots_prepared']) for r in results],shots_prepared=sum(r['shots_prepared'] for r in results),visible_character_ids=sorted(ids),canonical_cast_verification={cid:verify_character_sources(mission,cid,characters[cid]) for cid in ids},aspect_ratio='9:16',gpu_called=False,production_qc_approved=False,render_grants_issued=False)
 m.write_once(directory/'source_manifest.json',summary)
 return dict(status='original_script_portrait_sources_prepared',gpu_called=False,source_manifest_bucket_path=str((directory/'source_manifest.json').relative_to(m.ROOT.parent)),shots_prepared=summary['shots_prepared'],render_grants_issued=False,production_qc_approved=False)
