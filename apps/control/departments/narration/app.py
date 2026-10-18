"""Same Kokoro VoiceBible and pacing on CPU. File version1.0.0.
Candidate speech only; no GPU decorator, no automatic media/voice approval.
"""
FILE_VERSION='1.0.0'
import os,tempfile,threading,json,hashlib
from pathlib import Path
import gradio as gr
VOICE_MAP={'CHAR-001':'am_michael','CHAR-002':'af_bella','CHAR-003':'am_fenrir','CHAR-004':'am_onyx','CHAR-005':'af_nicole','CHAR-006':'am_puck','CHAR-007':'af_heart','NARRATOR':'bm_george','NONE':'bm_george'}
SPEED=0.82
_PIPELINE=None
_VOICES={}
LOCK=threading.Lock()
def generate(text:str,char_id:str='NARRATOR')->str:
 if not isinstance(text,str) or not text.strip() or len(text)>10000:raise ValueError('Use1–10000 characters of approved narration text.')
 if os.environ.get('JOAT_CPU_VOICE_ENABLED','').lower()!='true':raise ValueError('CPU voice qualification is pending; no GPU fallback is permitted.')
 global _PIPELINE
 with LOCK:
  import numpy as np
  import torch
  import soundfile as sf
  from kokoro import KPipeline,KModel
  from huggingface_hub import hf_hub_download
  manifest=json.loads((Path(__file__).parent/'model_manifest.json').read_text())
  def pinned(name):
   item=next(x for x in manifest['files'] if x['path']==name);path=Path(hf_hub_download(manifest['repo'],name,revision=manifest['revision']))
   if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Pinned voice-model bytes changed.')
   return str(path)
  if _PIPELINE is None:
   torch.set_num_threads(2)
   model=KModel(repo_id=manifest['repo'],config=pinned('config.json'),model=pinned('kokoro-v1_0.pth')).to('cpu').eval()
   _PIPELINE=KPipeline(lang_code='a',repo_id=manifest['repo'],model=model,device='cpu')
  voice_name=VOICE_MAP.get(char_id,'bm_george')
  if voice_name not in _VOICES:_VOICES[voice_name]=torch.load(pinned('voices/'+voice_name+'.pt'),map_location='cpu',weights_only=True)
  if next(_PIPELINE.model.parameters()).device.type!='cpu':raise ValueError('CPU narration must not allocate a GPU.')
  samples=[]
  with torch.inference_mode():
   for _,_,audio in _PIPELINE(text,voice=_VOICES[voice_name],speed=SPEED):samples.append(audio.detach().cpu().numpy() if hasattr(audio,'detach') else np.asarray(audio))
  if not samples:raise ValueError('CPU narration returned no audio.')
  waveform=np.concatenate(samples)
  if not np.isfinite(waveform).all() or waveform.size==0 or np.max(np.abs(waveform))>=1:raise ValueError('CPU narration is empty, nonfinite or clips.')
  folder=Path(tempfile.mkdtemp(prefix='joat-cpu-voice-'));target=folder/'narration.wav';sf.write(str(target),waveform,24000,subtype='PCM_16');return str(target)
def build_app():
 with gr.Blocks() as demo:
  gr.Markdown('CPU narration — original Kokoro VoiceBible and0.82pacing; output is a candidate until reviewed.')
  text=gr.Textbox(label='Text',lines=3);character=gr.Textbox(label='char_id',value='NARRATOR');output=gr.Audio(label='CPU speech candidate',type='filepath');gr.Button('Generate CPU speech candidate').click(generate,[text,character],output,api_name='generate',concurrency_limit=1)
 return demo
if __name__=='__main__':build_app().launch()
