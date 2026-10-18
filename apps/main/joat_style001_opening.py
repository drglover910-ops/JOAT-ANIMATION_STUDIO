"""Prepare the exact approved portrait opening; no render/grant. File version1.0.0."""
FILE_VERSION='1.0.0'
import re
import joat_managed_generation as m

def verify_inputs(mission,receipt,result):
 if receipt.get('status')!='original_script_portrait_sources_prepared' or receipt.get('mission_fingerprint')!=mission['plan_fingerprint'] or receipt.get('project_id')!=mission['project_id'] or receipt.get('gpu_called') is not False:raise ValueError('Complete exact portrait source task required.')
 m.verify(result,'result_fingerprint');packet=result['source_packets'][0];m.verify(packet,'packet_fingerprint');job=packet['generation_job'];m.verify(job,'job_fingerprint');first=mission['shots'][0]
 if job['project_context']!={'project_id':mission['project_id'],'scene_id':first['scene_id'],'shot_id':first['shot_id']} or job['generation_specification']['duration_seconds']!=first['duration_seconds'] or job['generation_specification']['aspect_ratio']!='9:16' or len(first['visible_roles'])!=1:raise ValueError('Use the exact declared single-character portrait opening.')
 return packet

def prepare(mission,payload,directory,token):
 if set(payload)!={'source_task_id'} or not re.fullmatch('[a-f0-9]{32}',str(payload['source_task_id'])):raise ValueError('Use an exact completed portrait source task.')
 base=m.safe_path(m.ROOT/'production-projects'/m.valid_project(mission['project_id'])/'tasks'/payload['source_task_id']);receipt=m.read_json(base/'receipt.json');result=m.read_json(base/'sources_1.json');packet=verify_inputs(mission,receipt,result)
 requests=mission.get('reference_requests',[])
 if len(requests)!=1:raise ValueError('Exact existing opening reference required.')
 reference=requests[0];scope=dict(packet['generation_job']['project_context'],character_id=packet['generation_job']['immutable_upstream_snapshot']['character']['character_id'],environment_id='ENV-001')
 from joat_project_frame_reference import register
 from joat_job_frame_binding import create_binding,save_binding
 frame=register(mission['project_id'],reference['asset_key'],reference['request_id'],scope,packet['generation_job']['immutable_upstream_snapshot']['character'],True)
 binding=save_binding(packet,create_binding(packet,frame,True,m.OWNER))
 from joat_remote_generation import signed,save_plan
 prepared=m.proxy('executive','prepare',signed(packet,'prepare'),token);path=save_plan(packet,prepared)
 params=prepared['plan']['parameters']
 if params.get('max_width')!=576 or params.get('max_height')!=1024 or params.get('seconds')!=mission['shots'][0]['duration_seconds'] or params.get('input_mode')!='single image (i2v)':raise ValueError('Opening render plan does not preserve approved portrait image, duration and i2v mode.')
 if not 0<float(params.get('gen_budget',0))<=600:raise ValueError('Opening allocation exceeds the approved preparation ceiling.')
 m.write_once(directory/'managed_plan.json',prepared);m.write_once(directory/'approved_source.json',packet)
 return dict(status='style001_opening_prepared_no_render_grant',gpu_called=False,plan_fingerprint=prepared['plan_fingerprint'],source_job_fingerprint=packet['generation_job']['job_fingerprint'],source_supervisor_fingerprint=packet['packet_fingerprint'],binding_fingerprint=binding['binding_fingerprint'],managed_plan_bucket_path=str(path.relative_to(m.ROOT.parent)),duration_seconds=params['seconds'],width=params['max_width'],height=params['max_height'],gpu_ceiling_seconds=params['gen_budget'],render_grant_created=False,production_qc_approved=False)
