"""CPU-only completion preparation and exact owner batch grants. File version1.0.1.
Never generates media, replaces speech, or invents final QC approval.
"""
FILE_VERSION='1.0.1'
from pathlib import Path
from typing import Optional
import json
import gradio as gr
import joat_managed_generation as m
PROJECT='PROJECT-OTU-STORY-60S-001'
MISSION='8adfba490b6aedd13d1c1f3823121d32edb1eab826273beb3ac9f09bae0a4020'
OPENING='9d4f69b3afe9497fa26bf66822269d2b'
OPENING_SHA='2f559d92b374d913657ab3f69265460c0af54aacc99db7df817789c1d095a978'
OWNER_STATEMENT="That's perfect. We will tidy up on little things later. That is actually amazing. Okay, so now can we get that story and that whole thing put together the right way? If so, go ahead and do it. Don't stop."
def base():return m.safe_path(m.ROOT/'production-projects'/PROJECT/'film-completion'/MISSION)
def preserve(path,value):
    if path.exists():
        if m.read_json(path)!=value:raise ValueError('Existing film completion evidence differs; no overwrite.')
    else:m.write_once(path,value)
def spec(shot,style):
    kiana=shot['speaker']=='KIANA';cid='CHAR-002' if kiana else 'CHAR-001';words=shot['onscreen_dialogue']
    if not words or words!=shot['voice_text'] or shot['duration_seconds']!=6:raise ValueError('Exact six-second film dialogue required.')
    speaker='Kiana' if kiana else 'the Founder'
    voice='a natural feminine conversational voice' if kiana else 'a natural masculine conversational voice, warm, steady and clear'
    seat='seated behind reception counter' if kiana else 'seated behind executive desk'
    emotions={'SHOT-002':'frustrated but composed','SHOT-006':'hopeful curiosity','SHOT-009':'relieved'}
    native_intent=shot.get('native_visual_intent',shot['visual_intent'])
    action=f'Facing the camera with face and mouth clearly visible, {speaker} says in English: "{words}". Lips and jaw visibly articulate the audible words in natural synchronization. One visible speaker only. '+native_intent+' Keep face proportions, hairstyle, clothes, jewellery, hands and room unchanged. No generated lettering or extra people.'
    return dict(scene_id='SCENE-001' if kiana else 'SCENE-002',shot_id=shot['source_shot_id'],character_id=cid,environment_id='ENV-102' if kiana else 'ENV-001',purpose=native_intent,duration_seconds=6,camera=dict(size='medium',angle='eye_level',movement='static'),performance=dict(emotion=emotions.get(shot['shot_id'],'calm and reassuring'),expression='natural conversational expression with stable eye shape and facial identity',body_language=seat+', restrained posture',action=action,gaze=dict(type='camera',target='camera'),blocking=dict(start_position=seat,end_position=seat),interaction=dict(type='none',target='',action=''),timing=dict(pacing='natural',hold_seconds=0)),dialogue=words,narration='',audio='Generate the visible '+('woman Kiana' if kiana else 'man, the Founder')+' speaking this exact English dialogue in '+voice+'. Speech and mouth movement are generated together. Preserve the generated dialogue audio. No off-screen narrator, voice-over, music, dubbed replacement or other speakers.',caption='',style=style,wardrobe='Preserve approved navy blazer, striped top, jewellery and hairstyle exactly.' if kiana else 'Preserve approved black blazer, black shirt, sunglasses, watch and accessories exactly.')
def verify_entry(entry):
    from joat_remote_generation import source_for,prepared_path
    packet=source_for(PROJECT,entry['source_job_fingerprint'],entry['source_supervisor_fingerprint'])
    prepared=m.read_json(prepared_path(m.ROOT,packet,entry['plan_fingerprint']))
    if m.digest(prepared['plan'])!=entry['plan_fingerprint']:raise ValueError('Film render plan changed.')
    from joat_character_speech import verify_speaking_packet
    verify_speaking_packet(packet,entry['dialogue'])
    params=prepared['plan']['parameters']
    if (params['input_mode'],params['seconds'],params['max_width'],params['max_height'],params['gen_budget'])!=('single image (i2v)',6,1024,576,600) or params['skip_refine'] is not True:raise ValueError('Film route or budget differs.')
    if entry['dialogue'] not in params['prompt'] or 'No generated dialogue' in params['prompt']:raise ValueError('Film prompt lost spoken dialogue.')
    return packet,prepared

def prepare(payload,mission,directory,token):
    if mission.get('plan_fingerprint')!=MISSION or mission.get('project_id')!=PROJECT or payload!={'owner_statement':OWNER_STATEMENT,'approved_opening_execution_id':OPENING,'approved_opening_sha256':OPENING_SHA}:raise ValueError('Exact owner completion request and approved opening required.')
    from joat_saved_film_previews import speaking_source
    if m.file_hash(speaking_source())!=OPENING_SHA:raise ValueError('Approved opening differs.')
    approved=mission['approved_opening']
    preserve(base()/'opening_approval.json',dict(schema='joat.film_opening_reuse_approval.v1',file_version=FILE_VERSION,project_id=PROJECT,owner=m.OWNER,**approved,production_qc_approved=False))
    preserve(base()/'mission.json',mission)
    import joat_creative_workflow as workflow
    from joat_approved_reference import load_approved_frame
    from joat_job_frame_binding import create_binding,save_binding
    from joat_remote_generation import signed,save_plan
    kiana=m.read_json(m.ROOT/'job-reference-bindings'/PROJECT/'2d0864c9d67b6a585adc0b06648f9456e05c07d256e4ffeb9ccb4079cf626e67'/'binding.json')['approved_frame_manifest']
    founder=m.read_json(m.ROOT/'approved-references'/'684992636df23263a5df2218efe531596cb0485b7bba729dd56da331d9f2f442'/'manifest.json')
    for manifest,sha in [(kiana,'27f173091ae09e3355dea31782848bc47c63488b46f0b9876edc8032c607b714'),(founder,'b7b6732bf0020c4813ef19e80815636e6c8fb2f083ab12472dc205da1857bdbf')]:
        load_approved_frame(manifest)
        if manifest['descriptor']['image_sha256']!=sha:raise ValueError('Approved reference changed.')
    entries=[]
    for shot in mission['shots'][1:]:
        target=base()/'plans'/(shot['source_shot_id']+'.json')
        if target.exists():
            entry=m.read_json(target);verify_entry(entry)
            if entry['dialogue']!=shot['voice_text']:raise ValueError('Saved film dialogue differs.')
        else:
            native=spec(shot,mission['art_style'])
            brief='One More Message, original OTU booking commercial. Founder advises Kiana through a video consultation between salon and office. Owner approved Kiana native-speaking candidate and instructed full story completion. Visible character speech with exact words; no voice-over. Reuse approved references. Product graphics added beside visible Founder on CPU, never generated in the model. '+mission['story_connection']
            plan=workflow.validate_plan(PROJECT,brief,{'shots':[native]});state=workflow.build_drafts(plan,recovery_approved=True);result=workflow.assemble(state,True,m.OWNER)
            if len(result['source_packets'])!=1:raise ValueError('One exact source per shot required.')
            packet=result['source_packets'][0]
            from joat_character_speech import verify_speaking_packet
            job=verify_speaking_packet(packet,shot['voice_text'])
            binding=save_binding(packet,create_binding(packet,kiana if shot['speaker']=='KIANA' else founder,True,m.OWNER))
            prepared=m.proxy('executive','prepare',signed(packet,'prepare'),token);save_plan(packet,prepared)
            entry=dict(schema='joat.film_render_entry.v1',file_version=FILE_VERSION,film_shot_id=shot['shot_id'],source_shot_id=shot['source_shot_id'],speaker=shot['speaker'],dialogue=shot['voice_text'],start_seconds=shot['start_seconds'],duration_seconds=6,source_job_fingerprint=job['job_fingerprint'],source_supervisor_fingerprint=packet['packet_fingerprint'],plan_fingerprint=prepared['plan_fingerprint'],binding_fingerprint=binding['binding_fingerprint'],cpu_graphics_overlay=shot['cpu_graphics_overlay'],gpu_ceiling_seconds=600,automatic_retry=False,production_qc_approved=False)
            verify_entry(entry);preserve(target,entry)
        entries.append(entry)
        print('JOAT_FILM_PREPARATION '+m.stable(dict(file_version=FILE_VERSION,completed_shots=len(entries),planned_shots=9,last_shot=entry['film_shot_id'],gpu_called=False)),flush=True)
    batch=dict(schema='joat.film_completion_batch.v1',file_version=FILE_VERSION,project_id=PROJECT,mission_fingerprint=MISSION,approved_opening_execution_id=OPENING,approved_opening_sha256=OPENING_SHA,entries=entries,maximum_new_attempts=9,total_allocation_ceiling_seconds=5400,actual_gpu_usage_not_guaranteed=True,automatic_retry=False,additional_reference_generations=0,grants_created=False,production_qc_approved=False)
    batch['batch_fingerprint']=m.digest(batch);preserve(base()/'batch.json',batch)
    return dict(status='film_completion_prepared_awaiting_exact_owner_batch_grant',gpu_called=False,shots_prepared=9,approved_opening_reused=True,batch_fingerprint=batch['batch_fingerprint'],batch_bucket_path=str((base()/'batch.json').relative_to(m.ROOT.parent)),render_grants_created=False,production_qc_approved=False)

def read_batch():
    batch=m.read_json(base()/'batch.json');m.verify(batch,'batch_fingerprint')
    if batch.get('schema')!='joat.film_completion_batch.v1' or batch.get('mission_fingerprint')!=MISSION or batch.get('maximum_new_attempts')!=9 or len(batch.get('entries',[]))!=9 or batch.get('total_allocation_ceiling_seconds')!=5400:raise ValueError('Exact remaining film batch required.')
    if [e['source_shot_id'] for e in batch['entries']]!=[f'SHOT-{n:03}' for n in range(12,21)]:raise ValueError('Film shot order or uniqueness differs.')
    for e in batch['entries']:verify_entry(e)
    return batch

def load_batch(profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
    m.owner_token(profile,oauth,request)
    try:batch=read_batch()
    except (ValueError,FileNotFoundError) as exc:raise gr.Error('Remaining film preparation is not ready: '+str(exc)) from None
    display=dict(batch,exact_native_render_plans=[dict(source_shot_id=e['source_shot_id'],plan=verify_entry(e)[1]['plan']) for e in batch['entries']])
    return display,batch,False

def authorize_batch(state,approved,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
    m.owner_token(profile,oauth,request)
    if approved is not True:raise gr.Error('Review the exact nine remaining plans and approve their one-attempt limits first.')
    try:
        batch=read_batch()
        if state!=batch:raise ValueError('Displayed film batch changed; reload before authorization.')
        from joat_remote_generation import grant,load_grant
        grants=[]
        for entry in batch['entries']:
            packet,prepared=verify_entry(entry);path=base()/'grants'/(entry['source_shot_id']+'.json')
            if path.exists():
                record=m.read_json(path);value=load_grant(record['grant_id'],packet,entry['plan_fingerprint'])
            else:
                reservation=path.with_suffix('.reservation.json')
                if reservation.exists():raise ValueError('Prior grant creation is incomplete or unknown; audit before any new authorization.')
                m.write_once(reservation,dict(source_shot_id=entry['source_shot_id'],plan_fingerprint=entry['plan_fingerprint'],automatic_retry=False))
                value=grant(packet,prepared['plan'],True);preserve(path,dict(grant_id=value['grant_id'],plan_fingerprint=entry['plan_fingerprint']))
            grants.append(dict(source_shot_id=entry['source_shot_id'],source_job_fingerprint=entry['source_job_fingerprint'],plan_fingerprint=entry['plan_fingerprint'],grant_id=value['grant_id']))
        receipt=dict(schema='joat.film_completion_authorization.v1',file_version=FILE_VERSION,project_id=PROJECT,batch_fingerprint=batch['batch_fingerprint'],owner=m.OWNER,maximum_new_attempts=9,automatic_retry=False,grants=grants,gpu_called=False,production_qc_approved=False)
        receipt['authorization_fingerprint']=m.digest(receipt);preserve(base()/'authorization.json',receipt)
        return receipt,'Authorized the nine exact remaining shots once each. No render started by this button. Already completed shots and approvals are retained; no automatic retries.'
    except ValueError as exc:raise gr.Error(str(exc)) from None

def add_film_completion_ui():
    with gr.Tab('Finish One More Message'):
        gr.Markdown('Approved Kiana opening is reused. The remaining nine six-second shots use visible character speech; booking graphics are added beside the Founder. No new reference images. Each shot permits one attempt, no retries, with a 600-second GPU allocation ceiling (nine-shot ceiling: 5,400 seconds). Actual GPU use and account quota deductions can differ. This prepares a review master; final QC remains required.')
        gr.LoginButton()
        state=gr.State(None);shown=gr.JSON(label='Exact remaining film shots, dialogue and plan fingerprints')
        ready=gr.Checkbox(label='I reviewed these nine exact plans and authorize one remote attempt per shot, within the displayed ceilings',value=False)
        gr.Button('Load remaining film plans — no GPU',variant='primary').click(load_batch,[],[shown,state,ready],api_name='load_film_completion_batch',api_visibility='undocumented',concurrency_limit=1)
        result=gr.JSON(label='Film authorization receipt — no GPU');note=gr.Markdown()
        gr.Button('Authorize remaining film shots — does not start GPU',variant='primary').click(authorize_batch,[state,ready],[result,note],api_name='authorize_film_completion_batch',api_visibility='undocumented',concurrency_limit=1)
