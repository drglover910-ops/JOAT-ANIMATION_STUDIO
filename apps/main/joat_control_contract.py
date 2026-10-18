"""Pinned API discovery for the fixed Studio Control service. File version 1.0.16.
Caches public metadata only. Live API authentication, HMAC and rate limits remain enforced.
"""
FILE_VERSION='1.0.16'
import copy,json,hashlib
from pathlib import Path
from huggingface_hub import HfApi
from gradio_client import Client
ROOT=Path(__file__).parent
REPO='Dezz-9-10/J.O.A.T.-Executive-Producer-Bot'
HOST='https://dezz-9-10-j-o-a-t-executive-producer-bot.hf.space'
REVISION='1161eb36496532dcc64d21c56c1e7c8d2a3d7364'
HASHES={'control_config_v1.0.0.json': '6f2826c891eb02fcf0b9638047ab8f09509e3c6d1413bfa158cf9f6707afb419', 'control_api_v1.0.0.json': '531298ede4dd591a0c0c035c125db9ac060342d2963e893878e84b07936b4ceb'}

def read_contract(name):
 p=ROOT/name
 if p.is_symlink() or p.stat().st_size>2000000:raise ValueError('Invalid pinned Control metadata path.')
 raw=p.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=HASHES[name]:raise ValueError('Control metadata integrity changed; re-audit required.')
 return json.loads(raw)

class ContractClient(Client):
 def _get_config(self):return read_contract('control_config_v1.0.0.json')
 def _get_api_info(self):
  info=read_contract('control_api_v1.0.0.json')
  for group in ('named_endpoints','unnamed_endpoints'):
   kept={}
   for key,entry in info[group].items():
    entry.pop('code_snippets',None)
    if ('api_visibility' in entry and entry.pop('api_visibility')!='private') or entry.pop('show_api',True):kept[key]=entry
   info[group]=kept
  return info

def create(source,token,headers,directory):
 if source!=HOST:raise ValueError('Pinned metadata may only target the existing Studio Control host.')
 info=HfApi(token=token).space_info(REPO)
 if info.sha!=REVISION:raise ValueError('Studio Control source changed; refresh the verified API contract before execution.')
 config=read_contract('control_config_v1.0.0.json');api=read_contract('control_api_v1.0.0.json')
 expected={'/managed_prepare','/managed_check','/managed_execute','/managed_status','/managed_reuse'}
 if config.get('version')!='6.29.1' or not expected<=set(api.get('named_endpoints',{})):raise ValueError('Pinned Control API contract differs.')
 return ContractClient(source,token=token,oauth_token=token,headers=headers,verbose=False,download_files=directory,analytics_enabled=False)
