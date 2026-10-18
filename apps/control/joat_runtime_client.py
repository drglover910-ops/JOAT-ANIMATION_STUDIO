"""Logical department clients routed through one owner-gated CPU host. File version1.0.1.
Logical repo IDs and packet fields stay unchanged. GPU model services stay remote.
"""
FILE_VERSION='1.0.1'
import json,os
from pathlib import Path
import gradio_client
from gradio_client import Client as NativeClient,handle_file
from joat_local_cpu import LocalClient,role_for,stable,enabled
HOST='https://dezz-9-10-j-o-a-t-executive-producer-bot.hf.space'
_INSTALLED=False
class RoutedJob:
 def __init__(self,job):self.job=job
 def result(self,timeout=None):
  result,files=self.job.result(timeout=timeout);files=files or []
  def restore(v):
   if isinstance(v,dict) and set(v)=={'__joat_output_file__'}:
    index=v['__joat_output_file__']
    if type(index) is not int or not 0<=index<len(files):raise ValueError('Invalid department output file mapping.')
    value=files[index]
    if isinstance(value,dict):return value.get('path') or value.get('url')
    return value
   return v
  return [restore(v) for v in result] if isinstance(result,list) else restore(result)
class RemoteDepartmentClient:
 def __init__(self,role,*args,**kwargs):
  self.role=role;self.description=None;kwargs=dict(kwargs);kwargs.setdefault('oauth_token',kwargs.get('token'));params=dict(kwargs.get('httpx_kwargs') or {});query=dict(params.get('params') or {});query.update(all_endpoints='true',_joat_cpu_contract=FILE_VERSION);params['params']=query;kwargs['httpx_kwargs']=params;kwargs.setdefault('verbose',False);self.native=NativeClient(HOST,**kwargs)
 @property
 def download_files(self):return self.native.download_files
 @download_files.setter
 def download_files(self,value):self.native.download_files=value
 def close(self):self.native.close()
 def view_api(self,return_format='dict',print_info=False,**kwargs):
  if self.description is None:
   value=self.native.predict(self.role,api_name='/cpu_department_describe')
   from joat_studio_capabilities import registry
   if value.get('studio_capability_registry_fingerprint')!=registry()['registry_fingerprint']:raise ValueError('Main and Studio Control capability registries differ; no department action submitted.')
   self.description=value
  return self.description
 def submit(self,*args,api_name=None,**kwargs):
  contract=self.view_api()['named_endpoints'].get(api_name)
  if contract is None:raise ValueError('Unknown native department endpoint.')
  args=list(args);kwargs=dict(kwargs)
  def as_file(v):
   if isinstance(v,(str,Path)):return handle_file(str(v))
   if isinstance(v,list):return [as_file(x) for x in v]
   return v
  for i in contract.get('file_input_indices',[]):
   if i<len(args):args[i]=as_file(args[i])
   else:
    name=contract['parameters'][i]['parameter_name']
    if name in kwargs:kwargs[name]=as_file(kwargs[name])
  files=[]
  def inputs(v):
   if isinstance(v,Path):v=handle_file(str(v))
   if isinstance(v,dict) and (v.get('meta',{}).get('_type')=='gradio.FileData' or v.get('is_file') is True):
    value=v.get('path') or v.get('name')
    if not isinstance(value,str):raise ValueError('Invalid department input file.')
    index=len(files);files.append(handle_file(value));return {'__joat_input_file__':index}
   if isinstance(v,dict):return {k:inputs(x) for k,x in v.items()}
   if isinstance(v,(list,tuple)):return [inputs(x) for x in v]
   return v
  arguments=inputs(list(args));named=inputs(kwargs)
  job=self.native.submit(self.role,api_name,stable(arguments),stable(named),files or None,api_name='/cpu_department_call')
  return RoutedJob(job)
 def predict(self,*args,api_name=None,**kwargs):return self.submit(*args,api_name=api_name,**kwargs).result()
def install(local=False):
 global _INSTALLED
 if _INSTALLED:return
 class RoutedClient(NativeClient):
  def __new__(cls,src,*args,**kwargs):
   role=role_for(src)
   if cls is RoutedClient and role and enabled():return LocalClient(role) if local else RemoteDepartmentClient(role,*args,**kwargs)
   return object.__new__(cls)
 gradio_client.Client=RoutedClient;_INSTALLED=True
