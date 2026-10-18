"""Shared CPU-only studio capability tools. Embedded file version1.0.0."""
FILE_VERSION='1.0.0'
import json
from typing import Optional
import gradio as gr
from joat_studio_capabilities import catalogue,plan_project,observations

def lookup(query:str=''):return catalogue(query)
def plan(raw:str):
 try:return plan_project(json.loads(raw))
 except (ValueError,TypeError) as exc:raise gr.Error(str(exc)) from None

def evidence(limit:float,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
 from joat_managed_generation import owner_token
 owner_token(profile,oauth,request)
 if isinstance(limit,bool) or int(limit)!=limit:raise gr.Error('Use a whole number of observations.')
 try:return observations(limit=int(limit))
 except ValueError as exc:raise gr.Error(str(exc)) from None

def add_studio_capability_ui():
 with gr.Tab('Studio Capabilities & Planning'):
  gr.Markdown('Verified tool knowledge for commercials, stories and dramas. These tools run on CPU and do not generate media, approve creative decisions or change an existing job. New GPU features stay gated until qualified.')
  query=gr.Textbox(label='Find a capability',placeholder='identity, keyframe, soundtrack, continuation…');output=gr.JSON(label='Capabilities, limitations and evidence');gr.Button('Look up studio capabilities — no GPU').click(lookup,query,output,api_name='studio_capability_catalogue',api_visibility='public')
  request=gr.Code(label='Production requirements and existing creative locks',language='json',value=json.dumps(dict(project_id='PROJECT-EXAMPLE',intent='Create an original commercial using approved references and existing audio.',format='product_commercial',locks={},required_features=['image_to_video'],clip_count=1),indent=2));result=gr.JSON(label='Capability-aware plan — approval workflow still required');gr.Button('Prepare capability-aware production plan — CPU only').click(plan,request,result,api_name='plan_studio_capabilities',api_visibility='public')

  gr.Markdown('Technique evidence grows from existing durable generation results. Technical observations never grant creative QC or authorize a new technique.')
  count=gr.Number(value=10,minimum=1,maximum=50,precision=0,label='Maximum saved observations');saved=gr.JSON(label='Verified saved technical observations — owner access required');gr.Button('Read existing technique evidence — no regeneration').click(evidence,count,saved,api_name='studio_technique_evidence',api_visibility='undocumented',concurrency_limit=1)
