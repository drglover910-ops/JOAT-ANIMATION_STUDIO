"""Independent owner review of real authored graphics. File version1.0.0."""
FILE_VERSION='1.0.0'
import json,tempfile
from pathlib import Path
from typing import Optional
import gradio as gr
from joat_production_ui import require_owner,login
from joat_authored_graphics_qc import inspect_authored,CHECKS

def inspect(candidate_file:str,media:str,reviewed:list[str],notes:str,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
 owner=require_owner(profile,request,oauth)
 if not Path(candidate_file).is_file() or Path(candidate_file).stat().st_size>2*1024**2:raise gr.Error('Exact small candidate report required.')
 try:result=inspect_authored(json.loads(Path(candidate_file).read_text()),media,{k:k in reviewed for k in CHECKS},owner,notes)
 except ValueError as exc:raise gr.Error(str(exc)) from None
 target=Path(tempfile.mkdtemp(prefix='joat-authored-qc-'))/'authored_graphics_qc.json';target.write_text(json.dumps(result,indent=2));return result,str(target)

def add_authored_qc_ui():
 with gr.Tab('Authored Graphics QC'):
  gr.Markdown('Watch the entire authored graphics clip. Review design, readable text, the complete booking transaction and truthful branding/claims. Actor-identity checks do not apply to this source type. Unchecked items require rework; this step never creates or repairs media.')
  login();candidate=gr.File(label='Exact authored candidate JSON',type='filepath',file_types=['.json']);media=gr.File(label='Exact authored MP4',type='filepath',file_types=['.mp4']);review=gr.CheckboxGroup(sorted(CHECKS),value=[],label='Requirements independently reviewed');notes=gr.Textbox(label='Review notes');result=gr.JSON(label='Independent authored QC decision');file=gr.File(label='Exact authored QC packet')
  gr.Button('Inspect authored graphics and issue QC decision').click(inspect,[candidate,media,review,notes],[result,file],api_name='inspect_authored_graphics',api_visibility='undocumented',concurrency_limit=1)
