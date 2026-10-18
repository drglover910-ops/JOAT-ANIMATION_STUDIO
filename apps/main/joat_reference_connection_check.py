"""Owner-scoped metadata diagnostics only. Embedded file version 1.0.1."""
FILE_VERSION = '1.0.1'
import os, re, json, hashlib, threading, html
from pathlib import Path
from typing import Optional
import gradio as gr

PREFIX = 'JOAT_REFERENCE_CONNECTION_CHECK_'
HOST = 'https://dezz-9-10-joat-reference-lab.hf.space'

def clean(text):
    for key, value in os.environ.items():
        if re.search(r'token|secret|password|_key', key, re.I) and len(value) >= 8:
            text = text.replace(value, '[REDACTED]')
    return re.sub(r'hf_[A-Za-z0-9]+', '[REDACTED]', text)[:6000]

def run(identifier):
    root = Path('/studio/joat-studio/migrations/reference-connection') / identifier
    if root.exists(): return
    result = dict(schema='joat.reference_connection_diagnostic.v1',file_version=FILE_VERSION,
                  check_id=identifier,gpu_called=False,inference_called=False,automatic_retry=False,probes=[])
    try:
        root.mkdir(parents=True,exist_ok=False)
        from huggingface_hub import HfApi
        import httpx
        token=os.environ.get('JOAT_SPECIALIST_TOKEN','')
        if not token or HfApi(token=token).whoami().get('name')!='Dezz-9-10':
            raise ValueError('Existing owner credential verification failed')
        from gradio_client import Client
        # Exactly the SDK's existing owner authentication headers. No IP spoofing.
        from huggingface_hub.utils import build_hf_headers
        headers=build_hf_headers(token=token,library_name='gradio_client')
        headers['x-hf-authorization']=headers.pop('authorization')
        headers['Authorization']='Bearer '+token
        for path in ['/config','/gradio_api/info']:
            response=httpx.get(HOST+path,headers=headers,params={'all_endpoints':'true'},timeout=35,follow_redirects=False)
            allowed={'content-type','retry-after','server','via','x-request-id','x-error-message','x-error-code','cf-ray'}
            safe_headers={k:clean(v) for k,v in response.headers.items() if k in allowed or k.startswith(('ratelimit','x-ratelimit'))}
            body=clean(html.unescape(re.sub('<[^>]+>',' ',re.sub(r'<(script|style)\b[^>]*>.*?</\1>','',response.text,flags=re.S))))
            probe=dict(path=path,http_status=response.status_code,headers=safe_headers,body_excerpt=body if response.status_code!=200 else 'Valid metadata response')
            result['probes'].append(probe)
            print('JOAT_REFERENCE_CONNECTION_PROGRESS '+json.dumps(dict(check_id=identifier,**probe)),flush=True)
            if response.status_code!=200: break
        result['status']='metadata_available' if len(result['probes'])==2 and all(x['http_status']==200 for x in result['probes']) else 'metadata_blocked'
    except Exception as exc:
        result.update(status='diagnostic_failed',error_type=type(exc).__name__,safe_error_message=clean(str(exc)))
    result['receipt_fingerprint']=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    if root.is_dir() and not (root/'receipt.json').exists():(root/'receipt.json').write_text(json.dumps(result,indent=2))
    print('JOAT_REFERENCE_CONNECTION_TERMINAL '+json.dumps(result),flush=True)

def start_reference_connection_checks():
    if os.environ.get('SPACE_ID')!='Dezz-9-10/J.O.A.T.-Main-Assistant-Bot': return
    for key,value in list(os.environ.items()):
        if key.startswith(PREFIX) and value==FILE_VERSION:
            identifier=key.removeprefix(PREFIX)
            if re.fullmatch('[a-f0-9]{32}',identifier):
                threading.Thread(target=run,args=(identifier,),daemon=True).start()

def browser_check(profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
    from joat_managed_generation import owner_token
    import httpx, uuid
    token=owner_token(profile,oauth,request)
    headers={'Authorization':'Bearer '+token,'x-hf-authorization':'Bearer '+token}
    delegation=request.headers.get('x-ip-token')
    if isinstance(delegation,str) and 0<len(delegation)<=8192:
        headers['x-ip-token']=delegation
    result=dict(schema='joat.reference_browser_connection.v1',file_version=FILE_VERSION,
                check_id=uuid.uuid4().hex,gpu_called=False,inference_called=False,
                automatic_retry=False,delegated_request_header_present='x-ip-token' in headers)
    try:
        response=httpx.get(HOST+'/config',headers=headers,params={'all_endpoints':'true'},timeout=35,follow_redirects=False)
        result.update(http_status=response.status_code,content_type=response.headers.get('content-type'),
                      retry_after=response.headers.get('retry-after'),rate_limit=response.headers.get('ratelimit'),
                      status='metadata_available' if response.status_code==200 else 'metadata_blocked')
    except Exception as exc:
        result.update(status='diagnostic_failed',error_type=type(exc).__name__)
    result['receipt_fingerprint']=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    root=Path('/studio/joat-studio/migrations/reference-connection')/result['check_id']
    root.mkdir(parents=True,exist_ok=False)
    (root/'receipt.json').write_text(json.dumps(result,indent=2))
    print('JOAT_REFERENCE_BROWSER_TERMINAL '+json.dumps(result),flush=True)
    return result

def add_reference_connection_ui():
    with gr.Tab('Studio Connection Check'):
        gr.Markdown('Sign in as Dezz-9-10, then check the reference connection. This requests metadata only and cannot generate an image or consume GPU inference. Browser delegation stays in memory; no token is saved.')
        gr.LoginButton()
        output=gr.JSON(label='Reference connection result — no GPU')
        gr.Button('Check Reference Connection — no GPU').click(browser_check,[],output,
            api_name='reference_browser_connection_check',api_visibility='undocumented',concurrency_limit=1)
