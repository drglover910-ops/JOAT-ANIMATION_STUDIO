"""Verify actual consolidated host and bucket without spoofing logical Space IDs.
Embedded file version1.0.1. Does not grant owner approval or reset any secret.
"""
FILE_VERSION='1.0.1'
import json,os,urllib.request
from pathlib import Path
from functools import lru_cache
HOST_SPACE='Dezz-9-10/J.O.A.T.-Executive-Producer-Bot';BUCKET='Dezz-9-10/J.O.A.T.-Studio-storage'
def local_role(role):
 return os.environ.get('JOAT_STUDIO_CONSOLIDATED_ENABLED','').lower()=='true' and os.environ.get('SPACE_ID')==HOST_SPACE and os.environ.get('JOAT_CPU_CHILD_ROLE')=={'supervisor':'generation_supervisor','worker':'generation_worker','delivery':'delivery_archive'}.get(role)
@lru_cache(maxsize=2)
def mount_check(role):
 if not local_role(role):raise ValueError('Consolidated department/runtime mismatch.')
 token=os.environ.get('JOAT_SPECIALIST_TOKEN','')
 if not token:raise ValueError('Existing owner credential required for private consolidated metadata.')
 request=urllib.request.Request('https://huggingface.co/api/spaces/'+HOST_SPACE,headers={'Authorization':'Bearer '+token})
 with urllib.request.urlopen(request,timeout=30) as r:metadata=json.load(r)
 if not any(v.get('type')=='bucket' and v.get('source')==BUCKET and v.get('mountPath')=='/studio' and v.get('readOnly') is False for v in metadata.get('runtime',{}).get('volumes',[])) or not Path('/studio/joat-studio').is_dir():raise ValueError('Actual Studio Control read/write bucket mount required.')
