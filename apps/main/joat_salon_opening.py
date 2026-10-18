"""Prepare only the explicitly approved salon opening through native departments.
Embedded file version 1.0.1. CPU only; no render grant, execution or QC approval.
"""
FILE_VERSION='1.0.1'
import json,copy
import joat_managed_generation as m

def prepare(payload,mission,directory,token):
    if set(payload)!={'proposal','owner_approval','shot','brief','origin'}:raise ValueError('Exact opening preparation payload required.')
    proposal=payload['proposal'];a=payload['owner_approval'];shot=payload['shot']
    m.verify(proposal,'proposal_fingerprint')
    if a.get('owner')!=m.OWNER or a.get('approved') is not True or a.get('proposal_fingerprint')!=proposal['proposal_fingerprint'] or a.get('scope')!='opening_reuse_and_action' or not a.get('owner_statement'):raise ValueError('Explicit owner opening adjustment approval required.')
    if mission['project_id']!=proposal.get('project_id') or proposal.get('shot_id')!='SHOT-001' or proposal.get('reuse_image_sha256')!='27f173091ae09e3355dea31782848bc47c63488b46f0b9876edc8032c607b714':raise ValueError('Wrong approved opening proposal.')
    if shot.get('shot_id')!='SHOT-001' or shot.get('scene_id')!='SCENE-001' or shot.get('character_id')!='CHAR-002' or shot.get('environment_id')!='ENV-101' or shot.get('duration_seconds')!=mission['shots'][0]['duration_seconds']:raise ValueError('Opening scope or duration changed.')
    if shot['performance']['action']!=proposal['proposed_action'] or shot['purpose']!=proposal['proposed_change'] or shot['camera']!={'size':'medium','angle':'eye_level','movement':'static'} or any(shot[k] for k in ['dialogue','narration','caption']):raise ValueError('Approved opening decisions changed.')
    if payload['origin']!={'asset_key':'KIANA-SALON-RECEPTION-CORRECTED','request_id':'48dfb35061b74409b9769e07b9bb3b56'}:raise ValueError('Use the existing approved reception source.')
    story=m.read_json(m.ROOT/'production-projects'/mission['project_id']/'approvals'/(mission['plan_fingerprint']+'.json'))
    if story.get('owner_approval',{}).get('approved') is not True:raise ValueError('Existing owner story approval is required.')
    # Original owner-approved image evidence is verified before native planning.
    from joat_project_frame_reference import evidence,register
    review,approval,image=evidence(mission['project_id'],**{'key':payload['origin']['asset_key'],'identifier':payload['origin']['request_id'],'root':m.ROOT})
    if review['sha256']!=proposal['reuse_image_sha256']:raise ValueError('Opening image differs from owner approval.')
    m.write_once(directory/'owner_opening_adjustment.json',a)
    import joat_creative_workflow as workflow
    plan=workflow.validate_plan(mission['project_id'],payload['brief'],{'shots':[shot]})
    state=workflow.build_drafts(plan)
    result=workflow.assemble(state,True,m.OWNER)
    if len(result['source_packets'])!=1:raise ValueError('Only one opening source expected.')
    packet=result['source_packets'][0];job=packet['generation_job'];snap=job['immutable_upstream_snapshot']
    manifest=register(mission['project_id'],payload['origin']['asset_key'],payload['origin']['request_id'],dict(job['project_context'],character_id='CHAR-002',environment_id='ENV-101'),snap['character'],True)
    from joat_job_frame_binding import create_binding,save_binding
    bound=save_binding(packet,create_binding(packet,manifest,True,m.OWNER))
    from joat_remote_generation import signed,save_plan
    prepared=m.proxy('executive','prepare',signed(packet,'prepare'),token)
    path=save_plan(packet,prepared)
    # This saved exact plan remains ungranted. Existing owner grant UI is authoritative.
    m.write_once(directory/'managed_plan.json',prepared)
    m.write_once(directory/'approved_source.json',packet)
    return dict(status='opening_prepared_awaiting_exact_remote_grant',gpu_called=False,
                source_job_fingerprint=job['job_fingerprint'],source_supervisor_fingerprint=packet['packet_fingerprint'],
                plan_fingerprint=prepared['plan_fingerprint'],managed_plan_bucket_path=str(path.relative_to(m.ROOT.parent)),
                approved_image_sha256=manifest['descriptor']['image_sha256'],binding_fingerprint=bound['binding_fingerprint'],
                render_grant_created=False,production_qc_approved=False)
