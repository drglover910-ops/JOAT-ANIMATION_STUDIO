"""Owner-only playback of saved shot candidates. File version: 1.0.1.
Read and export existing media only; no inference, approval or storage mutation.
"""
FILE_VERSION='1.0.1'
import re,shutil,tempfile
from pathlib import Path
from typing import Optional
import gradio as gr
import joat_managed_generation as m
PROJECT='PROJECT-OTU-STYLE001-90S-001'

def candidates(project,root=None):
 root=Path(m.ROOT if root is None else root);m.valid_project(project);found=[]
 for path in sorted((root/'remote-generation'/'requests').glob('*/receipt.json'))[:500]:
  if not re.fullmatch('[a-f0-9]{32}',path.parent.name):continue
  m.safe_path(path);receipt=m.read_json(path)
  if receipt.get('status')!='completed':continue
  request=m.read_json(m.safe_path(path.parent/'request.json'))
  if request.get('project_id')!=project:continue
  source=m.read_json(m.safe_path(path.parent/'artifacts'/'source_supervisor_packet.json'));m.verify(source,'packet_fingerprint');m.verify(source['generation_job'],'job_fingerprint')
  job=source['generation_job'];context=job['project_context']
  if context['project_id']!=project or job['job_fingerprint']!=receipt.get('source_job_fingerprint'):raise ValueError('Saved shot source differs from project.')
  found.append(dict(key='native:'+path.parent.name,label=context['shot_id']+' — native video — '+path.parent.name[:8],saved_at_ns=path.stat().st_mtime_ns,kind='native',base=path.parent,shot_id=context['shot_id']))
 for path in sorted((root/'production-projects'/project/'graphics').glob('*/*/candidate_review.json'))[:100]:
  m.safe_path(path);review=m.read_json(path)
  if review.get('project_id')!=project or review.get('schema')!='joat.authored_graphics_candidate.v1':raise ValueError('Saved graphic project differs.')
  m.verify(review,'candidate_fingerprint');shot=review['shot_id'];plan=review['source_plan']['plan_fingerprint']
  if not re.fullmatch('SHOT-[0-9]{3}',shot) or not re.fullmatch('[a-f0-9]{64}',plan) or path.parent.name!=plan or path.parent.parent.name!=shot:raise ValueError('Saved graphic location differs.')
  found.append(dict(key='graphics:'+shot+':'+plan,label=shot+' — authored workflow — '+plan[:8],saved_at_ns=path.stat().st_mtime_ns,kind='graphics',base=path.parent,shot_id=shot))
 return sorted(found,key=lambda e:(e['shot_id'],e['key']))

def verified_media(project,key,root=None):
 entries=[e for e in candidates(project,root) if e['key']==key]
 if len(entries)!=1:raise ValueError('Select one saved shot from this project; no generation requested.')
 e=entries[0];base=e['base']
 if e['kind']=='native':
  index=m.read_json(m.safe_path(base/'artifact_index.json'));video=m.safe_path(base/'artifacts'/'output.mp4')
  source=m.read_json(m.safe_path(base/'artifacts'/'source_supervisor_packet.json'));result=m.read_json(m.safe_path(base/'artifacts'/'generation_result.json'))
  if index.get('schema')!='joat.remote_artifact_index.v1' or index.get('result_status')!='completed' or index.get('source_job_fingerprint')!=source['generation_job']['job_fingerprint']:raise ValueError('Saved artifact index differs.')
  for name in ['output.mp4','generation_result.json','source_supervisor_packet.json']:
   matches=[f for f in index['files'] if f['filename']==name]
   expected='joat-studio/remote-generation/requests/'+base.name+'/artifacts/'+name
   path=m.safe_path(base/'artifacts'/name)
   if path.stat().st_size>2*1024**3:raise ValueError('Saved candidate exceeds playback limit.')
   if len(matches)!=1 or matches[0].get('bucket_path')!=expected or path.stat().st_size!=matches[0].get('size_bytes') or m.file_hash(path)!=matches[0].get('sha256'):raise ValueError('Saved media/source integrity failed.')
  if result.get('schema')!='joat.generation_result.v1':raise ValueError('Only completed rendered candidates can be loaded here.')
  m.validate_outcome(result,source,video);evidence=result
 else:
  evidence=m.read_json(m.safe_path(base/'candidate_review.json'));video=m.safe_path(base/'candidate.mp4')
  if video.stat().st_size>2*1024**3:raise ValueError('Saved candidate exceeds playback limit.')
  if video.stat().st_size!=evidence['media_evidence']['size_bytes'] or m.file_hash(video)!=evidence['media_evidence']['sha256']:raise ValueError('Saved graphic media integrity failed.')
 if not video.is_file() or video.stat().st_size>2*1024**3:raise ValueError('Saved candidate exceeds playback limit.')
 return video,evidence,e['shot_id']

def refresh(project,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
 m.owner_token(profile,oauth,request)
 try:entries=candidates(project)
 except (ValueError,OSError) as exc:raise gr.Error(str(exc)) from None
 choices=[(e['label'],e['key']) for e in entries]
 return gr.update(choices=choices,value=max(entries,key=lambda e:e['saved_at_ns'])['key'] if entries else None),None,None,dict(saved_candidates=len(choices),gpu_called=False,production_qc_approved=False)

def watch(project,key,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
 m.owner_token(profile,oauth,request)
 try:
  source,evidence,shot=verified_media(project,key);folder=Path(tempfile.mkdtemp(prefix='joat-saved-shot-'));target=folder/(shot+'_CANDIDATE.mp4');shutil.copyfile(source,target)
  if m.file_hash(source)!=m.file_hash(target):raise ValueError('Preview export integrity failed.')
  return str(target),str(target),dict(shot_id=shot,sha256=m.file_hash(target),source_evidence=evidence,gpu_called=False,production_qc_approved=False)
 except (ValueError,OSError) as exc:raise gr.Error(str(exc)) from None

def add_saved_shots_ui():
 with gr.Tab('Saved Shot Candidates'):
  gr.Markdown('Watch or download saved shots for the current film. These buttons use no GPU and do not approve footage. The newest saved candidate is selected first; older takes remain available. Review voice, lip timing, identity and framing together.')
  gr.LoginButton();project=gr.Textbox(label='Film project',value=PROJECT);choice=gr.Dropdown(label='Saved shot',choices=[])
  video=gr.Video(label='Saved candidate — picture and original audio',format='mp4',buttons=['download']);file=gr.File(label='Download selected shot MP4',type='filepath');details=gr.JSON(label='Verified media evidence — final QC pending')
  gr.Button('Load saved shots — no GPU').click(refresh,[project],[choice,video,file,details],api_visibility='private',concurrency_limit=1)
  gr.Button('Watch selected shot — no GPU',variant='primary').click(watch,[project,choice],[video,file,details],api_visibility='private',concurrency_limit=1)
