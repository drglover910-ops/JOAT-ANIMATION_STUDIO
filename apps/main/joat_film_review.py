"""Owner-staged import and playback of exact film review master. File version1.0.2.
No generation, replacement dialogue, final QC approval or delivery authorization.
"""
FILE_VERSION='1.0.2'
import json,re,subprocess,tempfile,shutil
from pathlib import Path
from typing import Optional
import gradio as gr
import joat_managed_generation as m
import joat_film_completion as film

def target():return film.base()/'review-master'
def verify_manifest(value,batch):
 if not isinstance(value,dict) or value.get('schema')!='joat.film_review_edit.v1' or value.get('project_id')!=film.PROJECT or value.get('mission_fingerprint')!=film.MISSION:raise ValueError('Exact completed film review manifest required.')
 if value.get('production_qc_approved') is not False or value.get('delivery_authorized') is not False or value.get('gpu_called') is not False or value.get('audio_substitution') is not False or value.get('native_character_audio_preserved') is not True:raise ValueError('Review master cannot invent QC or replace character speech.')
 if not re.fullmatch('[a-f0-9]{64}',str(value.get('sha256',''))) or abs(float(value.get('duration_seconds',0))-60)>.1:raise ValueError('Exact sixty-second review media required.')
 segments=value.get('segments',[])
 if len(segments)!=10 or [s.get('film_shot_id') for s in segments]!=[f'SHOT-{n:03}' for n in range(1,11)]:raise ValueError('Exact ten-shot story order required.')
 expected={'SHOT-001':'2d0864c9d67b6a585adc0b06648f9456e05c07d256e4ffeb9ccb4079cf626e67'};expected.update({e['film_shot_id']:e['source_job_fingerprint'] for e in batch['entries']})
 for segment in segments:
  if segment.get('source_job_fingerprint')!=expected[segment['film_shot_id']] or segment.get('native_dialogue_preserved') is not True or segment.get('original_source_unchanged') is not True or segment.get('edited_duration_seconds')!=6:raise ValueError('Review segment source, audio or edit duration differs.')
 return segments

def import_review(payload,mission,directory,token):
 if mission.get('plan_fingerprint')!=film.MISSION or set(payload)!={'review_manifest','temporary_upload_path','executions'}:raise ValueError('Exact owner-staged film import required.')
 batch=film.read_batch();manifest=payload['review_manifest'];segments=verify_manifest(manifest,batch);executions=payload['executions']
 if set(executions)!={s['film_shot_id'] for s in segments} or executions['SHOT-001']!=film.OPENING:raise ValueError('All ten original executions required.')
 for segment in segments:
  identifier=executions[segment['film_shot_id']]
  if not re.fullmatch('[a-f0-9]{32}',str(identifier)):raise ValueError('Invalid exact source execution.')
  index=m.read_json(m.safe_path(m.ROOT/'remote-generation'/'requests'/identifier/'artifact_index.json'))
  entries=[e for e in index.get('files',[]) if e.get('filename')=='output.mp4']
  if index.get('schema')!='joat.remote_artifact_index.v1' or index.get('result_status')!='completed' or index.get('source_job_fingerprint')!=segment['source_job_fingerprint'] or len(entries)!=1 or entries[0].get('sha256')!=segment.get('source_video_sha256'):raise ValueError('Review master source differs from actual native artifact.')
  if segment['film_shot_id']=='SHOT-001' and segment['source_video_sha256']!=film.OPENING_SHA:raise ValueError('Owner-approved opening changed.')
 path=m.safe_path(Path(payload['temporary_upload_path']));allowed=Path(tempfile.gettempdir())/'gradio'
 if not path.resolve().is_relative_to(allowed.resolve()) or path.name!='ONE_MORE_MESSAGE_60S_REVIEW.mp4' or not path.is_file() or path.stat().st_size>200*1024*1024 or m.file_hash(path)!=manifest['sha256']:raise ValueError('Exact uploaded temporary review MP4 required.')
 raw=subprocess.run(['ffprobe','-v','error','-count_frames','-show_streams','-of','json',str(path)],check=True,capture_output=True,text=True,timeout=60).stdout
 streams=json.loads(raw)['streams'];video=next(s for s in streams if s['codec_type']=='video')
 if (video['width'],video['height'],video['r_frame_rate'],int(video['nb_read_frames']))!=(1024,576,'24/1',1440) or abs(float(video['duration'])-60)>.1 or video['codec_name']!='h264' or not any(s['codec_type']=='audio' for s in streams):raise ValueError('Uploaded master dimensions, timing, codec or audio differ.')
 subprocess.run(['ffmpeg','-v','error','-i',str(path),'-f','null','-'],check=True,capture_output=True,timeout=90)
 destination=m.safe_path(target()/'ONE_MORE_MESSAGE_60S_REVIEW.mp4')
 if destination.exists():
  if m.file_hash(destination)!=manifest['sha256']:raise ValueError('A different review master already exists; no overwrite.')
 else:m.store_media(path,destination)
 film.preserve(target()/'review_edit_manifest.json',manifest)
 record=dict(schema='joat.film_review_storage.v1',file_version=FILE_VERSION,project_id=film.PROJECT,mission_fingerprint=film.MISSION,batch_fingerprint=batch['batch_fingerprint'],sha256=manifest['sha256'],size_bytes=destination.stat().st_size,executions=executions,source_chain_verified=True,technical_validation_passed=True,native_character_audio_preserved=True,gpu_called=False,production_qc_approved=False,delivery_authorized=False)
 record['storage_fingerprint']=m.digest(record);film.preserve(target()/'storage_receipt.json',record)
 return dict(status='film_review_master_saved_awaiting_owner_final_qc',gpu_called=False,sha256=manifest['sha256'],duration_seconds=60,source_chain_verified=True,storage_fingerprint=record['storage_fingerprint'],production_qc_approved=False)

def load_review(profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
 m.owner_token(profile,oauth,request)
 try:
  receipt=m.read_json(target()/'storage_receipt.json');m.verify(receipt,'storage_fingerprint');batch=film.read_batch();manifest=m.read_json(target()/'review_edit_manifest.json');verify_manifest(manifest,batch)
  if receipt.get('mission_fingerprint')!=film.MISSION or receipt.get('batch_fingerprint')!=batch['batch_fingerprint'] or receipt.get('production_qc_approved') is not False or receipt.get('sha256')!=manifest['sha256']:raise ValueError('Review storage scope differs.')
  source=m.safe_path(target()/'ONE_MORE_MESSAGE_60S_REVIEW.mp4')
  if not source.is_file() or source.stat().st_size!=receipt['size_bytes'] or source.stat().st_size>200*1024*1024 or m.file_hash(source)!=receipt['sha256']:raise ValueError('Saved master integrity failed.')
  folder=Path(tempfile.mkdtemp(prefix='joat-complete-film-'));export=folder/'ONE_MORE_MESSAGE_60S_REVIEW.mp4';shutil.copyfile(source,export)
  report=folder/'film_review_manifest.json';report.write_text(json.dumps(manifest,indent=2)+'\n')
  return str(export),str(export),str(report),'Complete 60-second story review: Kiana and the Founder speak with their original generated audio. Includes booking demonstrations and OTU CTA. Please review the full film with sound before final QC approval. Loading uses no GPU.'
 except (ValueError,FileNotFoundError) as exc:raise gr.Error('Completed film review is not ready: '+str(exc)) from None


def accept_staged_import(raw:str):
 """One-use, exact-file capability staged by the authenticated Space owner.
 The credential permits only this known review MP4; no generation/QC authority.
 """
 import os,hmac
 if not isinstance(raw,str) or len(raw.encode())>8192:raise gr.Error('Invalid bounded review transfer.')
 try:
  value=json.loads(raw)
  if set(value)!={'request_id','transfer_token','temporary_upload_path'}:raise ValueError('Exact transfer fields required.')
  identifier=value['request_id']
  if not isinstance(identifier,str) or not re.fullmatch('[a-f0-9]{32}',identifier):raise ValueError('Invalid review transfer identifier.')
  staged=os.environ.get('JOAT_FILM_REVIEW_IMPORT_'+identifier,'')
  if not staged or len(staged.encode())>131072:raise ValueError('Owner-staged review import is unavailable.')
  spec=json.loads(staged)
  if set(spec)!={'schema','file_version','request_id','transfer_token','project_id','mission_fingerprint','review_manifest','executions'} or spec.get('schema')!='joat.film_review_import_request.v1' or spec.get('request_id')!=identifier or spec.get('project_id')!=film.PROJECT or spec.get('mission_fingerprint')!=film.MISSION:raise ValueError('Review transfer scope differs.')
  supplied=value['transfer_token'];expected=spec['transfer_token']
  if not isinstance(supplied,str) or not isinstance(expected,str) or not 32<=len(expected)<=256 or not hmac.compare_digest(supplied,expected):raise ValueError('Review transfer authorization invalid.')
  token=os.environ.get('JOAT_SPECIALIST_TOKEN','')
  if not token or m.HfApi(token=token).whoami().get('name')!=m.OWNER:raise ValueError('Verified owner service required.')
  m.mount_check('main');batch=film.read_batch();verify_manifest(spec['review_manifest'],batch)
  existing=target()/'storage_receipt.json'
  if existing.exists():
   receipt=m.read_json(existing);m.verify(receipt,'storage_fingerprint')
   if receipt.get('sha256')!=spec['review_manifest']['sha256']:raise ValueError('Different review master already stored.')
   return dict(status='exact_review_master_already_saved',sha256=receipt['sha256'],gpu_called=False,production_qc_approved=False)
  directory=film.base()/'review-transfers'/identifier;claim=directory/'claim.json'
  if claim.exists():raise ValueError('Review transfer outcome unknown; inspect saved artifacts before resuming.')
  m.write_once(claim,dict(schema='joat.film_review_import_claim.v1',file_version=FILE_VERSION,request_id=identifier,sha256=spec['review_manifest']['sha256'],automatic_retry=False,gpu_called=False))
  payload=dict(review_manifest=spec['review_manifest'],executions=spec['executions'],temporary_upload_path=value['temporary_upload_path'])
  result=import_review(payload,m.read_json(film.base()/'mission.json'),directory,token)
  m.write_once(directory/'receipt.json',result)
  print('JOAT_FILM_REVIEW_IMPORT '+m.stable(dict(request_id=identifier,status=result['status'],sha256=result['sha256'],gpu_called=False)),flush=True)
  return result
 except (ValueError,KeyError,FileNotFoundError) as exc:raise gr.Error(str(exc)) from None

def add_review_import_api():
 chunk=gr.Textbox(visible=False);ack=gr.JSON(visible=False)
 gr.Button(visible=False).click(accept_staged_chunk,chunk,ack,api_name='upload_exact_film_piece',api_visibility='undocumented',concurrency_limit=1)
 payload=gr.Textbox(visible=False);result=gr.JSON(visible=False)
 gr.Button(visible=False).click(accept_staged_import,payload,result,api_name='import_exact_film_review',api_visibility='undocumented',concurrency_limit=1)

def accept_staged_chunk(raw:str):
 """Receive bounded transport pieces of the one owner-staged exact review file."""
 import os,hmac,base64,hashlib,math
 if not isinstance(raw,str) or len(raw.encode())>400000:raise gr.Error('Invalid bounded film transfer piece.')
 try:
  value=json.loads(raw)
  if set(value)!={'request_id','transfer_token','index','data'}:raise ValueError('Exact piece fields required.')
  identifier=value['request_id']
  if not isinstance(identifier,str) or not re.fullmatch('[a-f0-9]{32}',identifier):raise ValueError('Invalid transfer identifier.')
  staged=os.environ.get('JOAT_FILM_REVIEW_IMPORT_'+identifier,'')
  if not staged or len(staged.encode())>131072:raise ValueError('Owner-staged film transfer unavailable.')
  spec=json.loads(staged)
  if spec.get('schema')!='joat.film_review_import_request.v1' or spec.get('request_id')!=identifier or spec.get('project_id')!=film.PROJECT or spec.get('mission_fingerprint')!=film.MISSION:raise ValueError('Film transfer scope differs.')
  supplied=value['transfer_token'];expected=spec.get('transfer_token')
  if not isinstance(supplied,str) or not isinstance(expected,str) or not 32<=len(expected)<=256 or not hmac.compare_digest(supplied,expected):raise ValueError('Film transfer authorization invalid.')
  manifest=spec['review_manifest'];size=manifest.get('size_bytes');chunk_size=262144
  if type(size) is not int or not 1<=size<=200*1024*1024 or not re.fullmatch('[a-f0-9]{64}',str(manifest.get('sha256',''))):raise ValueError('Exact staged file size and hash required.')
  index=value['index'];total=math.ceil(size/chunk_size)
  if type(index) is not int or not 0<=index<total or not isinstance(value['data'],str):raise ValueError('Piece outside staged file.')
  data=base64.b64decode(value['data'],validate=True)
  if len(data)!=min(chunk_size,size-index*chunk_size):raise ValueError('Piece size differs from exact staged file.')
  directory=Path(tempfile.gettempdir())/'gradio'/('joat-film-transfer-'+identifier);directory.mkdir(parents=True,exist_ok=True)
  if directory.is_symlink():raise ValueError('Invalid transfer directory.')
  part=directory/f'part-{index:04}.bin'
  if part.exists():
   if part.is_symlink() or part.read_bytes()!=data:raise ValueError('Different piece already retained; no overwrite.')
  else:
   with part.open('xb') as output:output.write(data)
  count=sum((directory/f'part-{n:04}.bin').is_file() for n in range(total))
  result=dict(request_id=identifier,received_piece=index,received_count=count,total_pieces=total,gpu_called=False)
  if count==total:
   destination=directory/'ONE_MORE_MESSAGE_60S_REVIEW.mp4'
   if not destination.exists():
    temporary=directory/'assembling.bin'
    with temporary.open('wb') as output:
     for n in range(total):
      source=directory/f'part-{n:04}.bin'
      if source.is_symlink():raise ValueError('Invalid retained piece.')
      output.write(source.read_bytes())
    if temporary.stat().st_size!=size or hashlib.sha256(temporary.read_bytes()).hexdigest()!=manifest['sha256']:temporary.unlink();raise ValueError('Whole transferred film hash differs.')
    temporary.rename(destination)
   if destination.is_symlink() or destination.stat().st_size!=size or hashlib.sha256(destination.read_bytes()).hexdigest()!=manifest['sha256']:raise ValueError('Whole transferred film integrity failed.')
   result.update(temporary_upload_path=str(destination),sha256=manifest['sha256'])
  return result
 except (ValueError,KeyError,TypeError) as exc:raise gr.Error(str(exc)) from None
