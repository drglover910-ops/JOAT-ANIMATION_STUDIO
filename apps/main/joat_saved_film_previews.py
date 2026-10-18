"""Owner-only browser playback of existing verified film artifacts.
Embedded file version 1.0.9. No generation, provider call or QC approval.
"""
FILE_VERSION='1.0.9'
from pathlib import Path
from typing import Optional
import tempfile,shutil
import gradio as gr
import joat_managed_generation as m
EXECUTION='e11b674c372c4d9589deb273cee676fe'
JOB='6271e355c92bf46909ec3cb24a9419a3a713a5a65ba9aa4e27e7eff5615a6126'
VIDEO_SHA='e49fdf22f7b85e0ed6a52cacf3e37336b8ee29165c3c65017c7a5186e5d61443'

def existing_opening(root=None):
    root=Path(m.ROOT if root is None else root)
    base=m.safe_path(root/'remote-generation'/'requests'/EXECUTION)
    index=m.read_json(m.safe_path(base/'artifact_index.json'))
    if index.get('schema')!='joat.remote_artifact_index.v1' or index.get('source_job_fingerprint')!=JOB or index.get('result_status')!='completed':raise ValueError('Completed opening artifact index required.')
    matches=[f for f in index.get('files',[]) if f.get('filename')=='output.mp4']
    if len(matches)!=1:raise ValueError('One exact opening video required.')
    entry=matches[0];expected='joat-studio/remote-generation/requests/'+EXECUTION+'/artifacts/output.mp4'
    if entry.get('bucket_path')!=expected or entry.get('sha256')!=VIDEO_SHA:raise ValueError('Opening video identity differs.')
    video=m.safe_path(base/'artifacts'/'output.mp4')
    if not video.is_file() or video.stat().st_size!=entry.get('size_bytes') or video.stat().st_size>100*1024*1024 or m.file_hash(video)!=VIDEO_SHA:raise ValueError('Stored opening video integrity failed.')
    return video

def load_opening(profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
    m.owner_token(profile,oauth,request)
    try:
        video=existing_opening()
        export=Path(tempfile.mkdtemp(prefix='joat-owner-film-preview-'))/'OTU_Opening.mp4'
        shutil.copyfile(video,export)
        if m.file_hash(export)!=VIDEO_SHA:raise ValueError('Preview export integrity failed.')
        return str(export),str(export),'Archived diagnostic clip from the cancelled salon project. Not approved production.'
    except ValueError as exc:raise gr.Error(str(exc)) from None


TEST_PREVIEW_SHA='98a3c122e65341ab356bec2977a37bc719f3dd74f63fc660fd6f4b80a91a328b'
def load_engine_preview(profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
    m.owner_token(profile,oauth,request)
    video=m.safe_path(m.ROOT/'production-projects'/'PROJECT-ENGINE-60S-001'/'previews'/'v1.0.0'/'timing.mp4')
    if not video.is_file() or video.stat().st_size>100*1024*1024 or m.file_hash(video)!=TEST_PREVIEW_SHA:raise gr.Error('Verified 60-second preview is not available yet.')
    export=Path(tempfile.mkdtemp(prefix='joat-engine-preview-'))/'ENGINE_60S_TIMING_PREVIEW.mp4'
    shutil.copyfile(video,export)
    if m.file_hash(export)!=TEST_PREVIEW_SHA:raise gr.Error('Preview export integrity failed.')
    return str(export),str(export),'60-second CPU timing preview: two marked still placeholders. No new motion generation or final QC approval.'


STORY_PREVIEW_SHA='49020ab7f346ae2d715e51c2128b60222caed5aae8080ae80969e7f0cfe89c85'
STORY_EXECUTION='3774f91d931c4a4a8d1c86ce96a71995'
STORY_JOB='158b2e903106136cfa29375de9251fda5697888208289e95a7d8b03462bf6c70'
def story_source():
    base=m.safe_path(m.ROOT/'remote-generation'/'requests'/STORY_EXECUTION)
    index=m.read_json(base/'artifact_index.json')
    if index.get('schema')!='joat.remote_artifact_index.v1' or index.get('source_job_fingerprint')!=STORY_JOB or index.get('result_status')!='completed':raise ValueError('Completed exact story source required.')
    entry=[v for v in index['files'] if v.get('filename')=='output.mp4']
    if len(entry)!=1 or entry[0].get('sha256')!='4da827a7a54eec002d5fb10858f9b9d385bf9ee992ad7e9eb3fd8b0bd960b9ef':raise ValueError('Original story render differs.')
    video=m.safe_path(base/'artifacts'/'output.mp4')
    if video.stat().st_size!=entry[0].get('size_bytes') or video.stat().st_size>100*1024*1024 or m.file_hash(video)!=entry[0]['sha256']:raise ValueError('Original story render integrity failed.')
    return video


def continuation_frame(original):
    import subprocess
    folder=m.safe_path(m.ROOT/'production-projects'/'PROJECT-OTU-STORY-60S-001'/'previews'/'opening-v1.0.0')
    target=m.safe_path(folder/'closing_frame.png')
    if not target.exists():
        folder.mkdir(parents=True,exist_ok=True)
        temp=Path(tempfile.mkdtemp(prefix='joat-continuation-frame-'))/'candidate.png'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(original),'-vf',r'select=eq(n\,144)','-frames:v','1','-update','1',str(temp)],check=True,capture_output=True,timeout=30)
        m.store_media(temp,target)
    value=dict(schema='joat.render_frame_candidate.v1',file_version='1.0.0',project_id='PROJECT-OTU-STORY-60S-001',execution_id=STORY_EXECUTION,source_job_fingerprint=STORY_JOB,source_video_sha256='4da827a7a54eec002d5fb10858f9b9d385bf9ee992ad7e9eb3fd8b0bd960b9ef',frame_index=144,image_sha256=m.file_hash(target),owner_visual_approved=False,production_qc_approved=False,canonical_registration=False,gpu_called=False)
    value['candidate_fingerprint']=m.digest(value)
    report=folder/'closing_frame_candidate.json'
    if report.exists():
        if m.read_json(report)!=value:raise ValueError('Continuation frame evidence differs.')
    else:m.write_once(report,value)
    return target

def load_story_opening(profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
    m.owner_token(profile,oauth,request)
    original=story_source()
    video=m.safe_path(m.ROOT/'production-projects'/'PROJECT-OTU-STORY-60S-001'/'previews'/'opening-v1.0.0'/'review.mp4')
    if not video.is_file() or video.stat().st_size>2*1024*1024 or m.file_hash(video)!=STORY_PREVIEW_SHA:raise gr.Error('Verified story review edit is not available yet.')
    folder=Path(tempfile.mkdtemp(prefix='joat-story-opening-'));export=folder/'ONE_MORE_MESSAGE_OPENING.mp4';raw=folder/'ORIGINAL_RENDER.mp4'
    shutil.copyfile(video,export);shutil.copyfile(original,raw)
    if m.file_hash(export)!=STORY_PREVIEW_SHA:raise gr.Error('Story export integrity failed.')
    closing=continuation_frame(original);frame_export=folder/'PROPOSED_CONTINUATION_FRAME.png';shutil.copyfile(closing,frame_export)
    return str(export),str(export),str(raw),str(frame_export),'Opening-scene review excerpt with Kiana voice-over, notification and captions. 6.5 seconds, including a short review-only final-frame hold. This draft fails the on-screen speaking requirement; it is not an approved talking-character scene.'

SPEAKING_EXECUTION='9d4f69b3afe9497fa26bf66822269d2b'
SPEAKING_JOB='2d0864c9d67b6a585adc0b06648f9456e05c07d256e4ffeb9ccb4079cf626e67'
SPEAKING_SHA='2f559d92b374d913657ab3f69265460c0af54aacc99db7df817789c1d095a978'

def speaking_source(root=None):
    root=Path(m.ROOT if root is None else root)
    base=m.safe_path(root/'remote-generation'/'requests'/SPEAKING_EXECUTION)
    index=m.read_json(m.safe_path(base/'artifact_index.json'))
    if index.get('schema')!='joat.remote_artifact_index.v1' or index.get('source_job_fingerprint')!=SPEAKING_JOB or index.get('result_status')!='completed':raise ValueError('Exact completed speaking render required.')
    entries=[v for v in index.get('files',[]) if v.get('filename')=='output.mp4']
    expected='joat-studio/remote-generation/requests/'+SPEAKING_EXECUTION+'/artifacts/output.mp4'
    if len(entries)!=1 or entries[0].get('bucket_path')!=expected or entries[0].get('sha256')!=SPEAKING_SHA:raise ValueError('Speaking render identity differs.')
    video=m.safe_path(base/'artifacts'/'output.mp4')
    if not video.is_file() or video.stat().st_size!=entries[0].get('size_bytes') or video.stat().st_size>100*1024*1024 or m.file_hash(video)!=SPEAKING_SHA:raise ValueError('Speaking render integrity failed.')
    return video

def load_speaking_candidate(profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
    m.owner_token(profile,oauth,request)
    try:
        source=speaking_source()
        export=Path(tempfile.mkdtemp(prefix='joat-kiana-speaking-'))/'KIANA_SPEAKING_CANDIDATE.mp4'
        shutil.copyfile(source,export)
        if m.file_hash(export)!=SPEAKING_SHA:raise ValueError('Speaking export integrity failed.')
        return str(export),str(export),'Original generated picture and audio, unchanged. CPU transcription matches “One more message. And I’m late. Again.” Please review the voice, lip timing and face together. Final creative QC and continuity of voice across shots are pending. Loading uses no GPU.'
    except ValueError as exc:raise gr.Error(str(exc)) from None

def add_saved_film_previews():
    from joat_film_review import load_review,add_review_import_api
    add_review_import_api()
    with gr.Tab('Watch Film Preview'):
        gr.Markdown('One More Message — complete 60-second story review. Sign in, load the full film and watch with sound before final QC approval.')
        gr.LoginButton()
        full_button=gr.Button('Watch full One More Message — 60-second story',variant='primary')
        full_video=gr.Video(label='Complete story — review master',format='mp4',buttons=['download'])
        full_download=gr.File(label='Download ONE_MORE_MESSAGE_60S_REVIEW.mp4',type='filepath')
        full_manifest=gr.File(label='Download film source and edit evidence',type='filepath')
        full_note=gr.Markdown()
        full_button.click(load_review,[],[full_video,full_download,full_manifest,full_note],api_name='saved_full_character_story',api_visibility='undocumented',concurrency_limit=1)
        gr.Markdown('Earlier speaking-scene proof:')
        gr.Markdown('New: Kiana speaking in the salon. Watch the original generated audio and picture together before approving lip-sync.')
        gr.LoginButton()
        speaking_button=gr.Button('Watch Kiana speaking — original audio',variant='primary')
        speaking_video=gr.Video(label='Kiana speaking — original paired audio and video',format='mp4',buttons=['download'])
        speaking_download=gr.File(label='Download KIANA_SPEAKING_CANDIDATE.mp4',type='filepath')
        speaking_note=gr.Markdown()
        speaking_button.click(load_speaking_candidate,[],[speaking_video,speaking_download,speaking_note],api_name='saved_kiana_speaking_candidate',api_visibility='undocumented',concurrency_limit=1)
        gr.Markdown('Earlier voice-over draft: this does not satisfy the required visibly speaking, lip-synced characters. A speaking-shot qualification is being prepared.')
        gr.LoginButton()
        story_button=gr.Button('Watch One More Message — opening scene',variant='primary')
        story_video=gr.Video(label='One More Message — opening review',format='mp4',buttons=['download'])
        story_download=gr.File(label='Download opening scene with voice-over',type='filepath')
        story_original=gr.File(label='Download untouched original render',type='filepath')
        story_frame=gr.Image(label='Proposed next-shot starting frame — extracted from this render, awaiting your approval',type='filepath')
        story_note=gr.Markdown()
        story_button.click(load_story_opening,[],[story_video,story_download,story_original,story_frame,story_note],api_name='saved_character_story_opening',api_visibility='undocumented',concurrency_limit=1)
        gr.Markdown('Earlier CPU timing preview:')

        gr.Markdown('New 60-second booking-film timing preview. Includes narration and animated booking demonstrations; the two actor shots are explicitly marked still placeholders.')
        gr.LoginButton()
        test_button=gr.Button('Watch new 60-second preview — no GPU',variant='primary')
        test_video=gr.Video(label='New 60-second preview — press Play',format='mp4',buttons=['download'])
        test_download=gr.File(label='Download 60-second preview',type='filepath')
        test_note=gr.Markdown()
        test_button.click(load_engine_preview,[],[test_video,test_download,test_note],api_name='saved_engine_60s_preview',api_visibility='undocumented',concurrency_limit=1)

        gr.Markdown('Archived cancelled salon project: watch the diagnostic clip here or download it to Files. Sign in as Dezz-9-10, then press the button below. This loads a saved video and uses no GPU.')
        gr.LoginButton()
        button=gr.Button('Load salon opening — no GPU',variant='primary')
        video=gr.Video(label='Salon opening — press Play',format='mp4',buttons=['download'])
        download=gr.File(label='Download OTU_Opening.mp4',type='filepath')
        note=gr.Markdown()
        button.click(load_opening,[],[video,download,note],api_name='saved_salon_opening_preview',api_visibility='undocumented',concurrency_limit=1)

def import_private_preview():
    import os,base64
    keys=[f'JOAT_ENGINE_PREVIEW_PART_{i:02}' for i in range(10)]
    if not all(os.environ.get(k) for k in keys):return
    token=os.environ.get('JOAT_SPECIALIST_TOKEN','')
    if not token or m.HfApi(token=token).whoami().get('name')!=m.OWNER:raise ValueError('Owner service required for private preview import.')
    encoded=''.join(os.environ[k] for k in keys)
    if len(encoded)>2000000:raise ValueError('Preview transfer too large.')
    data=base64.b64decode(encoded,validate=True)
    import hashlib
    if hashlib.sha256(data).hexdigest()!=TEST_PREVIEW_SHA:raise ValueError('Private preview transfer differs.')
    target=m.safe_path(m.ROOT/'production-projects'/'PROJECT-ENGINE-60S-001'/'previews'/'v1.0.0'/'timing.mp4')
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():
        with target.open('xb') as file:file.write(data)
    if m.file_hash(target)!=TEST_PREVIEW_SHA:raise ValueError('Stored private preview differs.')
    print('JOAT_ENGINE_PREVIEW_IMPORT verified',flush=True)
import_private_preview()

def import_story_preview():
    import os,base64,hashlib
    keys=[f'JOAT_STORY_OPENING_PART_{i:02}' for i in range(7)]
    if not all(os.environ.get(k) for k in keys):return
    token=os.environ.get('JOAT_SPECIALIST_TOKEN','')
    if not token or m.HfApi(token=token).whoami().get('name')!=m.OWNER:raise ValueError('Owner service required for private story preview import.')
    story_source()
    encoded=''.join(os.environ[k] for k in keys)
    if len(encoded)>850000:raise ValueError('Preview transfer too large.')
    data=base64.b64decode(encoded,validate=True)
    if hashlib.sha256(data).hexdigest()!=STORY_PREVIEW_SHA:raise ValueError('Private story transfer integrity failed.')
    path=m.safe_path(m.ROOT/'production-projects'/'PROJECT-OTU-STORY-60S-001'/'previews'/'opening-v1.0.0'/'review.mp4');path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        with path.open('xb') as file:file.write(data)
    if m.file_hash(path)!=STORY_PREVIEW_SHA:raise ValueError('Private story readback differs.')
    print('JOAT_STORY_OPENING_IMPORT verified',flush=True)
import_story_preview()
