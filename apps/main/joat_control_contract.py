"""Pinned API discovery for the fixed Studio Control service. File version 1.0.23.
Caches public metadata only. Live API authentication, HMAC and rate limits remain enforced.
"""
FILE_VERSION='1.0.23'
import copy,json,hashlib
from pathlib import Path
from huggingface_hub import HfApi
from gradio_client import Client
ROOT=Path(__file__).parent
REPO='Dezz-9-10/J.O.A.T.-Executive-Producer-Bot'
HOST='https://dezz-9-10-j-o-a-t-executive-producer-bot.hf.space'
REVISION='8b427ff762dd8be9c82d0fe64bb9def3393eee46'
HASHES={'control_config_v1.0.1.json': '38ade4f4d4bf205142835cb11966b33dd4ccc0c91ceee4b8d849a3c2ff2c59e3', 'control_api_v1.0.1.json': 'e0ebe4c1c9a7d044e58626c364347590aa322209f7ae715839c9a2607ce79d1c'}

def read_contract(name):
 p=ROOT/name
 if p.is_symlink() or p.stat().st_size>2000000:raise ValueError('Invalid pinned Control metadata path.')
 raw=p.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=HASHES[name]:raise ValueError('Control metadata integrity changed; re-audit required.')
 return json.loads(raw)

class ContractClient(Client):
 def _get_config(self):return read_contract('control_config_v1.0.1.json')
 def _get_api_info(self):
  info=read_contract('control_api_v1.0.1.json')
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
 config=read_contract('control_config_v1.0.1.json');api=read_contract('control_api_v1.0.1.json')
 expected={'/managed_prepare','/managed_check','/managed_execute','/managed_status','/managed_reuse'}
 if config.get('version')!='6.29.1' or not expected<=set(api.get('named_endpoints',{})):raise ValueError('Pinned Control API contract differs.')
 return ContractClient(source,token=token,oauth_token=token,headers=headers,verbose=False,download_files=directory,analytics_enabled=False)
