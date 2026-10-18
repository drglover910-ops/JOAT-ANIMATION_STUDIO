"""Main's owner-operated media finishing desk. File version 1.0.1.
Delegates QC, timeline and archive to their existing departments, never self-approves.
"""
FILE_VERSION='1.0.1'
import json
from pathlib import Path
import tempfile
from typing import Optional
import gradio as gr
from gradio_client import Client, handle_file
from joat_production_ui import owner_token, login
from joat_post_media import read_json, verify, file_hash, inspect_video, production_qc
from joat_post_pipeline import validate_post_receipts

SPACES={
    'qc':'Dezz-9-10/J.O.A.T.-Quality-Control-Bot',
    'timeline':'Dezz-9-10/J.O.A.T.-Editorial-Worker-Bot',
    'delivery':'Dezz-9-10/J.O.A.T.-Delivery-Archive-Bot',
}
CREATIVE=('character','environment','director','camera','performance','continuity')
FINAL=('picture','audio','titles','continuity')


def local_path(value):
    if isinstance(value,(list,tuple)):value=value[0]
    if isinstance(value,dict):value=value.get('video') or value.get('path')
    if isinstance(value,dict):value=value.get('path')
    if not isinstance(value,str) or not Path(value).is_file():
        raise ValueError('A locally uploaded/downloaded actual media file is required.')
    return value


def client_for(role,token,directory):
    if role not in SPACES or not token:raise ValueError('Owner transport is unavailable.')
    return Client(SPACES[role],token=token,oauth_token=token,verbose=False,download_files=directory)


def call_department(role,token,endpoint,args,client_factory=client_for):
    directory=tempfile.mkdtemp(prefix='joat-main-media-')
    client=None
    try:
        client=client_factory(role,token,directory)
        # Exactly one submitted call; timeouts/uncertain results are not retried.
        return client.submit(*args,api_name=endpoint).result(timeout=2700)
    finally:
        if client is not None:client.close()


def export_json(value,name):
    directory=Path(tempfile.mkdtemp(prefix='joat-main-packet-'))
    path=directory/name;path.write_text(json.dumps(value,ensure_ascii=False,indent=2))
    return str(path)


def verify_master(result,media):
    verify(result,'result_fingerprint')
    path=local_path(media)
    evidence=inspect_video(path,result['final_master']['specification'])
    if any(result['final_master'].get(key)!=value for key,value in evidence.items()):
        raise ValueError('Actual master bytes or decoded evidence differ from the result packet.')
    if result.get('schema')=='joat.post_production_result.v1':validate_post_receipts(result)
    elif result.get('schema')!='joat.timeline_result.v1' or not result.get('ordered_shots'):
        raise ValueError('Validated Post or ordered timeline result required.')
    return path


def review_generation(result_file,source_file,media,checks,notes,token,call=call_department):
    result=read_json(result_file);source=read_json(source_file)
    verify(result,'result_fingerprint');verify(source,'packet_fingerprint')
    path=local_path(media)
    packet,_=call('qc',token,'/inspect_production_media',[
        handle_file(result_file),handle_file(source_file),handle_file(path),list(checks or []),notes or ''])
    verify(packet,'qc_fingerprint')
    if (packet.get('schema')!='joat.quality_control_packet.v1'
            or packet.get('source_generation_result_fingerprint')!=result['result_fingerprint']
            or packet.get('source_job_fingerprint')!=result['source_job_fingerprint']
            or packet.get('source_supervisor_fingerprint')!=source['packet_fingerprint']
            or packet.get('source_asset',{}).get('sha256')!=file_hash(path)):
        raise ValueError('QC response does not bind the supplied generation result/source/video.')
    if packet.get('independent_review',{}).get('checks')!={key:key in (checks or []) for key in CREATIVE}:
        raise ValueError('QC response changed the owner review choices.')
    file=export_json(packet,'quality_control_packet.json')
    if packet.get('decision')=='PASS':production_qc(packet)
    return packet,file,path


def assemble(media_files,result_files,approved,token,call=call_department):
    if approved is not True:raise ValueError('Approve this exact timeline order first.')
    if not media_files or len(media_files)!=len(result_files or []) or len(media_files)>24:
        raise ValueError('Provide 1–24 MP4s and matching final-PASS JSON files in the same order.')
    results=[read_json(f) for f in result_files]
    for result,path in zip(results,media_files):
        verify_master(result,path)
        if result.get('delivery_authorized') is not True or result.get('final_qc',{}).get('decision')!='PASS':
            raise ValueError('Every input shot requires its independent final PASS.')
    packet,video,_=call('timeline',token,'/assemble_production_timeline',[
        [handle_file(local_path(p)) for p in media_files],[handle_file(p) for p in result_files],True])
    path=verify_master(packet,video)
    if (packet.get('schema')!='joat.timeline_result.v1'
            or packet.get('ordered_shots')!=[r['result_fingerprint'] for r in results]
            or packet.get('project_context')!={'project_id':results[0]['project_context']['project_id']}
            or packet.get('delivery_authorized') is not False or packet.get('final_qc_required') is not True):
        raise ValueError('Timeline response changed approved order/project or skipped final QC.')
    first=results[0]['final_master'];master=packet['final_master']
    if ((master['width'],master['height'],master['fps'])!=(first['width'],first['height'],first['fps'])
            or master['decoded_frames']!=sum(r['final_master']['decoded_frames'] for r in results)):
        raise ValueError('Timeline output changed the approved frame size, rate or frame count.')
    return packet,path,export_json(packet,'timeline_result.json')


def review_final(result_file,media,checks,token,call=call_department):
    original=read_json(result_file);path=verify_master(original,media)
    packet,_=call('qc',token,'/review_final_master',[handle_file(result_file),handle_file(path),list(checks or [])])
    verify(packet,'result_fingerprint')
    if packet.get('final_master')!=original['final_master'] or packet.get('project_context')!=original.get('project_context'):
        raise ValueError('Final review changed master evidence or project context.')
    mutable={'result_fingerprint','status','creative_integrity_preserved','delivery_authorized','final_qc','handoff'}
    for key in (set(original)|set(packet))-mutable:
        if packet.get(key)!=original.get(key):raise ValueError('Final review changed source provenance.')
    expected={key:key in (checks or []) for key in FINAL};q=packet.get('final_qc',{})
    passed=all(expected.values())
    if (q.get('reviewer')!='Dezz-9-10' or q.get('checks')!=expected
            or q.get('asset_sha256')!=file_hash(path) or q.get('technical_decode_verified') is not True
            or q.get('decision')!=('PASS' if passed else 'REJECT')
            or packet.get('delivery_authorized') is not passed):
        raise ValueError('Final QC response does not match the exact owner review.')
    return packet,path,export_json(packet,'final_review_result.json')


def deliver(result_file,media,token,call=call_department):
    result=read_json(result_file);path=verify_master(result,media)
    if result.get('delivery_authorized') is not True or result.get('final_qc',{}).get('decision')!='PASS':
        raise ValueError('Independent final PASS is required before delivery.')
    packet,master,archive,_=call('delivery',token,'/deliver_actual_master',[handle_file(result_file),handle_file(path)])
    verify(packet,'packet_fingerprint');output=local_path(master)
    if (packet.get('source_result_fingerprint')!=result['result_fingerprint']
            or packet.get('master',{}).get('sha256')!=file_hash(path) or file_hash(output)!=file_hash(path)
            or packet.get('storage_status')!='ARCHIVED_READBACK_VERIFIED'
            or packet.get('durable_remote_archive') is not True):
        raise ValueError('Delivery did not verify this exact final master in durable studio storage.')
    storage=packet.get('storage',{})
    if (storage.get('bucket')!='Dezz-9-10/J.O.A.T.-Studio-storage'
            or storage.get('master_sha256_verified') is not True
            or storage.get('approved_result_readback_verified') is not True):
        raise ValueError('Delivery archive readback evidence is missing.')
    return packet,output,local_path(archive),export_json(packet,'delivery_manifest.json')


def add_media_control_ui(post_controls,audit=None):
    def run(stage,function,*args):
        try:
            output=function(*args)
            if audit:audit('studio_media_'+stage,{'schema':output[0].get('schema'),'project_context':output[0].get('project_context'),
                       'fingerprint':output[0].get('qc_fingerprint') or output[0].get('result_fingerprint') or output[0].get('packet_fingerprint')})
            return output
        except (ValueError,TypeError) as exc:raise gr.Error(str(exc)) from None
        except Exception:raise gr.Error(stage+' handoff failed or outcome is unknown. No automatic retry; inspect returned artifacts before resuming.') from None
    def qc_callback(result_file,source_file,media,checks,notes,
                    profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
        token=owner_token(profile,oauth,request)
        packet,file,path=run('production_qc',review_generation,result_file,source_file,media,checks,notes,token)
        passed=packet.get('decision')=='PASS'
        return packet,file,file if passed else None,path if passed else None
    def timeline_callback(media_files,result_files,approved,
                          profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
        token=owner_token(profile,oauth,request)
        packet,path,file=run('timeline',assemble,media_files,result_files,approved,token)
        return packet,path,file,file,path
    def final_callback(result_file,media,checks,
                       profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
        token=owner_token(profile,oauth,request)
        packet,path,file=run('final_qc',review_final,result_file,media,checks,token)
        passed=packet.get('delivery_authorized') is True
        return packet,file,file if passed else None,path if passed else None
    def delivery_callback(result_file,media,
                          profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
        token=owner_token(profile,oauth,request)
        return run('delivery',deliver,result_file,media,token)
    with gr.Tab('Studio Finishing Desk'):
        login()
        gr.Markdown('Run finishing from Main while QC, Editorial, Post and Delivery keep their own authority. QC choices are your independent review; the assistant does not approve them. No GPU generation is called here. Existing approved results can be loaded at their matching step.')
        with gr.Tabs():
            with gr.Tab('Production QC'):
                generation=gr.File(label='Exact Generation Worker result JSON',type='filepath',file_types=['.json'])
                supervisor=gr.File(label='Matching source Supervisor packet JSON',type='filepath',file_types=['.json'])
                original=gr.File(label='Actual original rendered MP4',type='filepath',file_types=['.mp4'])
                creative=gr.CheckboxGroup(list(CREATIVE),value=[],label='Owner independent creative review')
                notes=gr.Textbox(label='Owner review notes')
                qc_view=gr.JSON(label='Independent QC decision');qc_file=gr.File(label='quality_control_packet.json')
                gr.Button('Send owner review to independent QC').click(qc_callback,[generation,supervisor,original,creative,notes],
                    [qc_view,qc_file,post_controls['qc_file'],post_controls['source']],api_visibility='private',concurrency_limit=1)
                gr.Markdown('A PASS fills Production Orchestration automatically. Use that tab to approve and run the six Post operations.')
                for component in (generation,supervisor,original):component.change(lambda:[],outputs=creative,api_visibility='private')
            with gr.Tab('Timeline Assembly'):
                shots=gr.File(label='Final-PASS MP4 shots in timeline order',file_count='multiple',type='filepath',file_types=['.mp4'])
                packets=gr.File(label='Matching final-PASS JSON files in same order',file_count='multiple',type='filepath',file_types=['.json'])
                order=gr.Checkbox(label='I approve this exact shot order and full-shot assembly',value=False)
                timeline_view=gr.JSON();timeline_video=gr.Video();timeline_file=gr.File(label='timeline_result.json')
                timeline_button=gr.Button('Assemble actual timeline through Editorial')
            with gr.Tab('Final Master Review'):
                final_result=gr.File(label='Exact Post or timeline result JSON',type='filepath',file_types=['.json'],interactive=True)
                final_media=gr.File(label='Actual final master MP4',type='filepath',file_types=['.mp4'],interactive=True)
                gr.Markdown('Watch and listen to the entire master before reviewing all four checks.')
                checks=gr.CheckboxGroup(list(FINAL),value=[],label='Owner independent final review')
                final_view=gr.JSON();final_file=gr.File(label='final_review_result.json')
                final_button=gr.Button('Record independent final PASS or REJECT')
            with gr.Tab('Final Delivery'):
                approved_result=gr.File(label='Exact final-PASS result JSON',type='filepath',file_types=['.json'],interactive=True)
                approved_media=gr.File(label='Actual approved final MP4',type='filepath',file_types=['.mp4'],interactive=True)
                delivery_view=gr.JSON();master=gr.File(label='Download finished MP4');archive=gr.File(label='Optional provenance ZIP');manifest=gr.File(label='delivery_manifest.json')
                gr.Button('Save approved master through Delivery Archive').click(delivery_callback,[approved_result,approved_media],
                    [delivery_view,master,archive,manifest],api_visibility='private',concurrency_limit=1)
        timeline_button.click(timeline_callback,[shots,packets,order],
            [timeline_view,timeline_video,timeline_file,final_result,final_media],api_visibility='private',concurrency_limit=1)
        final_button.click(final_callback,[final_result,final_media,checks],
            [final_view,final_file,approved_result,approved_media],api_visibility='private',concurrency_limit=1)
        for component in (shots,packets):component.change(lambda:False,outputs=order,api_visibility='private')
        for component in (final_result,final_media):
            component.change(lambda:([],None,None),outputs=[checks,approved_result,approved_media],api_visibility='private')
        def post_ready(result_file,video):
            if not result_file or not video:return None,None
            return result_file,local_path(video)
        post_controls['result_file'].change(post_ready,[post_controls['result_file'],post_controls['video']],
            [final_result,final_media],api_visibility='private')

    return {'generation':generation,'supervisor':supervisor,'original':original,'approved_result':approved_result,'approved_media':approved_media}
