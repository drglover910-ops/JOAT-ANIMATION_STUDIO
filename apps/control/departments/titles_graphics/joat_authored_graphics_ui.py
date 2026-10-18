"""Owner-gated native Titles candidate generation. Embedded file version1.0.1."""
FILE_VERSION='1.0.1'
import json
from typing import Optional
import gradio as gr
from joat_production_ui import bearer_header,login,OWNER
from joat_authored_graphics import render

def require_graphics_owner(profile,oauth,request):
 if profile is not None and profile.username==OWNER:return OWNER
 header=bearer_header(request)
 token=oauth.token if oauth is not None and oauth.token else header[7:] if header.lower().startswith('bearer ') else None
 if not token:raise gr.Error('Sign in as Dezz-9-10: owner OAuth was not forwarded; no graphics action started.')
 from huggingface_hub import HfApi
 try:owner=HfApi(token=token).whoami().get('name')
 except Exception as exc:raise gr.Error('Owner verification unavailable ('+type(exc).__name__+'); no graphics action started.') from None
 if owner!=OWNER:raise gr.Error('Sign in as Dezz-9-10 to run production media actions.')
 return OWNER

def execute(plan_json:str,owner_approved:bool,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
 require_graphics_owner(profile,oauth,request)
 if owner_approved is not True:raise gr.Error('Review and authorize the exact graphics plan first; final QC remains separate.')
 try:return render(json.loads(plan_json))
 except (ValueError,TypeError) as exc:raise gr.Error(str(exc)) from None
 except Exception:raise gr.Error('CPU graphics generation failed; no approved production output registered.') from None

def add_authored_graphics_ui():
 with gr.Tab('Authored Booking Graphics'):
  gr.Markdown('Create an illustrative animated booking screen on CPU. This returns a candidate MP4; independent visual review and production QC are still required.')
  login();plan=gr.Code(label='Exact authored graphics plan JSON',language='json');approved=gr.Checkbox(label='I reviewed this exact plan and authorize candidate creation',value=False);result=gr.JSON(label='Candidate evidence — awaiting independent QC');video=gr.Video(label='Actual authored MP4');file=gr.File(label='Candidate source and media evidence')
  gr.Button('Create authored graphics candidate — CPU only').click(execute,[plan,approved],[result,video,file],api_name='create_authored_graphics',api_visibility='undocumented',concurrency_limit=1,trigger_mode='once')
  plan.change(lambda:False,outputs=approved,api_visibility='private')
