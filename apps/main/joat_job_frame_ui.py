"""Owner review of an approved frame's assignment to an unchanged saved job. Version1.0.0."""
FILE_VERSION='1.0.0'
import json,re,shutil,tempfile
from pathlib import Path
from typing import Optional
import gradio as gr
from joat_production_ui import require_owner,login
import joat_job_frame_binding as binding
from joat_approved_reference import validate_manifest,load_approved_frame
from joat_managed_generation import mount_check,valid_project

def read_source(project,choice):
 valid_project(project)
 if not isinstance(choice,str) or not re.fullmatch('[a-f0-9]{64}/[a-f0-9]{64}',choice):raise ValueError('Select a saved approved source job.')
 packet=json.loads(binding.safe(binding.ROOT/'approved-jobs'/project/(choice+'.json')).read_text());job,ctx,_=binding.source(packet)
 if ctx['project_id']!=project or choice!=job['job_fingerprint']+'/'+packet['packet_fingerprint']:raise ValueError('Selected source path differs from its content.')
 return packet

def read_frame(asset):
 if not isinstance(asset,str) or not re.fullmatch('[a-f0-9]{64}',asset):raise ValueError('Select a saved approved scene frame.')
 manifest=json.loads(binding.safe(binding.ROOT/'approved-references'/asset/'manifest.json').read_text());validate_manifest(manifest)
 if manifest['asset_id']!=asset:raise ValueError('Approved frame asset path differs from its content.')
 return manifest

def add_job_frame_ui():
 with gr.Tab('Approved Scene Frames'):
  gr.Markdown('Assign an already approved scene frame to a saved video job. Review character, wardrobe, location and pose. This preserves the original image record and creative decisions. No video is rendered here.')
  login();project=gr.Textbox(label='Saved production project');jobs=gr.Dropdown(label='Saved video job',choices=[]);frames=gr.Dropdown(label='Approved scene frame',choices=[])
  preview=gr.Image(label='Exact approved image for this job',type='filepath');details=gr.JSON(label='Scene frame assignment review');state=gr.State(None);approved=gr.Checkbox(label='I reviewed this exact image for the selected job: identity, wardrobe, style, location and starting pose match')
  def refresh(project,profile:Optional[gr.OAuthProfile],request:gr.Request):
   require_owner(profile,request)
   try:
    valid_project(project);mount_check('main');choices=[]
    for file in sorted(binding.safe(binding.ROOT/'approved-jobs'/project).glob('*/*.json')):
     choice=file.parent.name+'/'+file.stem;packet=read_source(project,choice);context=packet['generation_job']['project_context'];character=packet['generation_job']['immutable_upstream_snapshot']['character'];choices.append((context['scene_id']+' / '+context['shot_id']+' · '+character.get('character_name',character['character_id']),choice))
    assets=[]
    for file in sorted(binding.safe(binding.ROOT/'approved-references').glob('*/manifest.json')):
     manifest=read_frame(file.parent.name);d=manifest['descriptor'];assets.append((d['scope']['character_id']+' · '+d['labels']['purpose'],manifest['asset_id']))
    return gr.update(choices=choices,value=None),gr.update(choices=assets,value=None),None,None,None,False
   except Exception as exc:raise gr.Error(str(exc)) from None
  def preview_frame_assignment(project,job,frame,profile:Optional[gr.OAuthProfile],request:gr.Request):
   require_owner(profile,request)
   try:
    mount_check('main');packet=read_source(project,job);manifest=read_frame(frame)
    # Check identity/environment compatibility without inventing assignment approval.
    snap=packet['generation_job']['immutable_upstream_snapshot'];d=binding.bind_character(manifest,snap['character'])
    if d['scope']['environment_id']!=snap['environment']['environment_id']:raise ValueError('Image belongs to a different environment.')
    image=load_approved_frame(manifest);out=Path(tempfile.mkdtemp(prefix='joat-frame-review-'))/'approved_frame.png';shutil.copyfile(image,out)
    review={'schema':'joat.job_frame_assignment_preview.v1','file_version':FILE_VERSION,'target_context':packet['generation_job']['project_context'],'original_image_scope':d['scope'],'original_image_labels':d['labels'],'source_job_fingerprint':packet['generation_job']['job_fingerprint'],'image_sha256':d['image_sha256'],'assignment_approved':False,'gpu_called':False}
    return str(out),review,{'project':project,'job_choice':job,'frame_asset':frame,'packet':packet,'manifest':manifest},False
   except Exception as exc:raise gr.Error(str(exc)) from None
  def save(project,job,frame,state,approved,profile:Optional[gr.OAuthProfile],request:gr.Request):
   require_owner(profile,request)
   try:
    if approved is not True or not state or state['project']!=project or state['job_choice']!=job or state['frame_asset']!=frame:raise ValueError('Preview this exact image and explicitly approve its assignment first.')
    packet=read_source(project,job);manifest=read_frame(frame)
    if state['packet']!=packet or state['manifest']!=manifest:raise ValueError('Preview inputs changed; review again.')
    value=binding.create_binding(packet,manifest,True,'Dezz-9-10');value=binding.save_binding(packet,value)
    return {'schema':'joat.job_frame_assignment_result.v1','file_version':FILE_VERSION,'status':'approved_frame_assigned','target_context':value['project_context'],'binding_fingerprint':value['binding_fingerprint'],'source_job_fingerprint':value['source_job_fingerprint'],'image_sha256':value['owner_approval']['image_sha256'],'original_image_and_source_unchanged':True,'gpu_called':False},False
   except Exception as exc:raise gr.Error(str(exc)) from None
  gr.Button('Refresh saved jobs and approved frames (no GPU)').click(refresh,[project],[jobs,frames,preview,details,state,approved],api_visibility='private')
  gr.Button('Preview scene frame assignment (no GPU)').click(preview_frame_assignment,[project,jobs,frames],[preview,details,state,approved],api_visibility='private')
  gr.Button('Save approved frame assignment (no GPU)').click(save,[project,jobs,frames,state,approved],[details,approved],api_visibility='private')
  for component in (project,jobs,frames):component.change(lambda:(None,None,None,False),outputs=[preview,details,state,approved],api_visibility='private')
