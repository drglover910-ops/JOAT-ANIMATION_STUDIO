"""Owner review of exact mission-bound candidate stills. File version1.0.1.
No GPU calls, canonical replacement, video grant or production QC approval.
"""
FILE_VERSION='1.0.1'
import re,json,shutil,tempfile
from pathlib import Path
from datetime import datetime,timezone
from typing import Optional
import gradio as gr
import joat_managed_generation as m

def project_root(project):return m.safe_path(m.ROOT/'production-projects'/m.valid_project(project))
def selection(project,mission_fp,choice):
 if not re.fullmatch('[a-f0-9]{64}',str(mission_fp)) or not isinstance(choice,str) or not re.fullmatch('[A-Z0-9-]{1,96}/[a-f0-9]{32}',choice):raise ValueError('Choose an exact saved mission and candidate.')
 base=project_root(project);mission=m.read_json(base/'missions'/(mission_fp+'.json'));core=dict(mission);given=core.pop('plan_fingerprint',None)
 if given!=mission_fp or m.digest(core)!=given or mission.get('project_id')!=project:raise ValueError('Saved mission integrity differs.')
 asset,identifier=choice.split('/');matches=[q for q in mission.get('reference_requests',[]) if q.get('request_id')==identifier and q.get('asset_key')==asset]
 if len(matches)!=1:raise ValueError('Candidate is not declared in this exact mission.')
 folder=m.safe_path(base/'references'/asset/identifier);review=m.read_json(folder/'candidate_review.json');image=m.safe_path(folder/'candidate.png')
 if review.get('schema')!='joat.project_reference_candidate.v1' or review.get('project_id')!=project or review.get('source_request')!=matches[0] or review.get('plan_fingerprint')!=m.digest(matches[0]) or review.get('owner_visual_approved') is not False or review.get('canonical_registration') is not False or review.get('production_qc_approved') is not False:raise ValueError('Exact unapproved source candidate required.')
 if not image.is_file() or image.stat().st_size>25*1024*1024 or m.file_hash(image)!=review.get('sha256') or image.stat().st_size!=review.get('size_bytes'):raise ValueError('Candidate image integrity differs.')
 return mission,review,image

def refresh(project,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
 m.owner_token(profile,oauth,request);m.mount_check('main');base=project_root(project);missions=[];frames=[]
 for file in sorted((base/'missions').glob('*.json'))[:100]:
  if re.fullmatch('[a-f0-9]{64}',file.stem):
   v=m.read_json(file);missions.append((v.get('title',project)+' · '+file.stem[:10],file.stem))
 for file in sorted((base/'references').glob('*/*/candidate_review.json'))[:100]:
  key=file.parent.parent.name;identifier=file.parent.name
  if re.fullmatch('[A-Z0-9-]{1,96}',key) and re.fullmatch('[a-f0-9]{32}',identifier):frames.append((key+' · '+identifier[:8],key+'/'+identifier))
 selected_mission=missions[0][1] if len(missions)==1 else None;selected_frame=frames[0][1] if len(frames)==1 else None
 evidence=preview(project,selected_mission,selected_frame,profile,oauth,request) if selected_mission and selected_frame else (None,dict(status='Select a saved mission and candidate, then click Preview selected frame.'),None,False)
 return gr.update(choices=missions,value=selected_mission),gr.update(choices=frames,value=selected_frame),*evidence

def preview(project,mission,choice,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
 m.owner_token(profile,oauth,request);_,review,image=selection(project,mission,choice);out=Path(tempfile.mkdtemp(prefix='joat-scene-candidate-'))/'candidate.png';shutil.copyfile(image,out)
 state=dict(project=project,mission=mission,choice=choice,sha256=review['sha256'])
 return str(out),dict(project_id=project,mission_fingerprint=mission,candidate=review,review_scope='Still only; no video or final QC approval.'),state,False

def approve(project,mission,choice,state,approved,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
 m.owner_token(profile,oauth,request)
 if not isinstance(state,dict) or state.get('project')!=project or state.get('mission')!=mission or state.get('choice')!=choice:raise gr.Error('Click Load and preview candidates first. If you changed a selection, click Preview selected frame before saving.')
 if approved is not True:raise gr.Error('Tick the checkbox below the displayed image to approve this exact still, then click Save still approval.')
 _,review,image=selection(project,mission,choice)
 if state.get('sha256')!=review['sha256']:raise gr.Error('Preview image changed; review again.')
 from joat_project_frame_approval import save
 key,identifier=choice.split('/');existing=m.safe_path(project_root(project)/'references'/key/identifier/'owner_visual_approval.json')
 if existing.exists():
  v=m.read_json(existing);m.verify(v,'approval_fingerprint')
  if v.get('mission_fingerprint')!=mission or v.get('image_sha256')!=review['sha256'] or v.get('owner_approval',{}).get('approved') is not True:raise gr.Error('Different still approval is already retained.')
  return dict(status='exact_still_already_approved',image_sha256=review['sha256'],gpu_called=False,production_qc_approved=False),False
 payload=dict(asset_key=key,request_id=identifier,image_sha256=review['sha256'],owner_approval=dict(owner=m.OWNER,approved=True,owner_statement='Approve this frame',approved_at=datetime.now(timezone.utc).isoformat(),scope='still_only'))
 return save(project,mission,payload),False

def add_reference_review_ui():
 with gr.Tab('Project Reference Review'):
  gr.Markdown('Review a newly generated scene frame before it is used for video. Approval applies to this exact still only; no GPU or video generation runs here.')
  gr.LoginButton();project=gr.Textbox(label='Production project',value='PROJECT-OTU-STYLE001-90S-001');mission=gr.Dropdown(label='Saved mission',choices=[]);choice=gr.Dropdown(label='Candidate frame',choices=[])
  image=gr.Image(label='Exact candidate starting frame',type='filepath');details=gr.JSON(label='Candidate and approval evidence');state=gr.State(None);accepted=gr.Checkbox(label='I approve this exact still: identity, wardrobe, scene, lighting and framing match')
  gr.Button('Load and preview candidates — no GPU').click(refresh,[project],[mission,choice,image,details,state,accepted],api_name=False)
  gr.Button('Preview selected frame — no GPU').click(preview,[project,mission,choice],[image,details,state,accepted],api_name=False)
  gr.Button('Save still approval — no GPU').click(approve,[project,mission,choice,state,accepted],[details,accepted],api_name=False)
  # Only actual owner edits invalidate review. Server dropdown updates must not
  # enqueue a reset after load/preview has populated the exact-image state.
  for field in (project,mission,choice):field.input(lambda:(None,None,None,False),outputs=[image,details,state,accepted],queue=False,api_name=False)
