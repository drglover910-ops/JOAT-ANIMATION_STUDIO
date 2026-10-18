"""Actual media operations. Owner-approved plans, verified input bytes, no inferred QC."""
FILE_VERSION = "1.0.4"
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

import av
from PIL import Image, ImageDraw, ImageFont

from joat_media_tools import file_hash, inspect_video

DEPARTMENTS = ('editorial', 'sound', 'music', 'compositing_vfx', 'color_finish', 'titles_graphics')
SPACES = dict(zip(DEPARTMENTS, [
    'J.O.A.T.-Editorial-Worker-Bot', 'J.O.A.T.-Sound-Worker-Bot', 'J.O.A.T.-Music-Worker-Bot',
    'J.O.A.T.-Compositing-VFX-Worker-Bot', 'J.O.A.T.-Color-Finish-Worker-Bot', 'J.O.A.T.-Titles-Graphics-Worker-Bot']))
SCHEMAS = {k: 'joat.' + k + '_result.v1' for k in DEPARTMENTS}


def stable(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def seal(value, field):
    value = dict(value)
    value.pop(field, None)
    value[field] = hashlib.sha256(stable(value).encode()).hexdigest()
    return value


def verify(value, field):
    if not isinstance(value, dict) or value.get(field) != seal(value, field)[field]:
        raise ValueError('Invalid ' + field)


def read_json(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError('Missing or oversized JSON file')
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError('Expected a JSON object')
    return value


def write_json(directory, name, value):
    path = Path(directory) / name
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    return str(path)


def production_qc(qc):
    if qc.get('schema') == 'joat.authored_graphics_qc.v1':
        from joat_authored_graphics_qc import validate_authored_qc
        return validate_authored_qc(qc)
    verify(qc, 'qc_fingerprint')
    if qc.get('schema') != 'joat.quality_control_packet.v1' or qc.get('decision') != 'PASS' or qc.get('post_production_authorized') is not True:
        raise ValueError('Independent production QC PASS is required')
    review = qc.get('independent_review', {})
    checks = review.get('checks', {})
    if review.get('reviewer') != 'Dezz-9-10' or set(checks) != {'character', 'environment', 'director', 'camera', 'performance', 'continuity'} or any(v is not True for v in checks.values()):
        raise ValueError('All six independent owner creative checks are required')
    evidence = qc.get('media_evidence') or {}
    if evidence.get('video_fully_decoded') is not True or evidence.get('sha256') != qc.get('source_asset', {}).get('sha256'):
        raise ValueError('QC lacks actual decoded media evidence')
    return evidence


def number(value, low, high, name):
    if isinstance(value, bool):
        raise ValueError('Invalid ' + name)
    result = float(value)
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError('Out of range: ' + name)
    return result


def audio_evidence(path):
    path = Path(path)
    if not path.is_file() or not 0 < path.stat().st_size <= 128 * 1024 * 1024:
        raise ValueError('Missing or oversized approved audio')
    try:
        with av.open(str(path)) as container:
            stream = container.streams.audio[0]
            samples = 0
            rate = stream.rate
            if not rate:
                raise ValueError('Audio rate missing')
            for frame in container.decode(stream):
                samples += frame.samples
                if samples / rate > 1800:
                    raise ValueError('Audio decode limit exceeded')
            if not samples:
                raise ValueError('Empty audio')
            return {'sha256': file_hash(path), 'sample_rate': rate, 'duration_seconds': samples / rate,
                    'audio_fully_decoded': True}
    except (ValueError, OSError):
        raise
    except Exception:
        raise ValueError('Approved audio could not be decoded') from None


def ffmpeg(args, output):
    import imageio_ffmpeg
    command = [imageio_ffmpeg.get_ffmpeg_exe(), '-nostdin', '-hide_banner', '-loglevel', 'error', '-filter_threads', '2', '-filter_complex_threads', '2', '-y'] + args + [str(output)]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=300)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise ValueError('Media operation failed; no completion was registered') from None


def video_encoding():
    return ['-c:v', 'libx264', '-threads', '2', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-movflags', '+faststart']


def execute_department(department, order, media, auxiliary=None):
    verify(order, 'work_order_fingerprint')
    if order.get('schema') != 'joat.post_work_order.v1' or order.get('department') != department or order.get('assigned_space') != 'Dezz-9-10/' + SPACES[department]:
        raise ValueError('Incorrect department or routing')
    production_qc(order['qc_packet'])
    if order.get('owner_approved') is not True or order.get('creative_changes_authorized') is not False:
        raise ValueError('Owner-approved technical work only')
    specification = order['input_specification']
    evidence = inspect_video(media, specification)
    if evidence['sha256'] != order['input_sha256']:
        raise ValueError('Input bytes differ from the authorized order')
    directory = Path(tempfile.mkdtemp(prefix='joat-post-'))
    output = directory / (department + '.mp4')
    operation = order['operation']
    kind = operation.get('kind')
    allowed = {
        'preserve': {'kind'}, 'trim': {'kind', 'start_seconds', 'end_seconds'},
        'mix_audio': {'kind', 'approved_audio_sha256', 'audio_rights_confirmed', 'gain', 'offset_seconds'},
        'color': {'kind', 'brightness', 'contrast', 'saturation'},
        'overlay': {'kind', 'approved_overlay_sha256', 'x', 'y'},
        'title': {'kind', 'text', 'x', 'y', 'font_size'},
    }
    if kind not in allowed or set(operation) - allowed[kind]:
        raise ValueError('Unsupported operation or extra settings')
    expected = dict(specification)
    auxiliary_evidence = None
    if kind == 'preserve':
        # Explicit approved no-op, never claim a nonexistent effect was performed.
        if set(operation) != {'kind'}:
            raise ValueError('Unexpected preserve settings')
        shutil.copyfile(media, output)
    elif department == 'editorial' and kind == 'trim':
        start = number(operation['start_seconds'], 0, specification['duration_seconds'], 'trim start')
        end = number(operation['end_seconds'], start + 0.05, specification['duration_seconds'], 'trim end')
        expected['duration_seconds'] = end - start
        ffmpeg(['-i', str(media), '-ss', str(start), '-t', str(end - start)] + video_encoding(), output)
    elif department in ('sound', 'music') and kind == 'mix_audio':
        if not auxiliary or operation.get('approved_audio_sha256') != file_hash(auxiliary) or operation.get('audio_rights_confirmed') is not True:
            raise ValueError('Approved audio bytes and rights confirmation required')
        auxiliary_evidence = audio_evidence(auxiliary)
        gain = number(operation['gain'], 0, 2, 'audio gain')
        offset = number(operation.get('offset_seconds', 0), 0, specification['duration_seconds'], 'audio offset')
        if offset + auxiliary_evidence['duration_seconds'] > specification['duration_seconds'] + 0.1:
            raise ValueError('Audio would be truncated; provide a timing-approved shorter file')
        filt = '[1:a]volume=%s,adelay=%s:all=1,apad[a]' % (gain, round(offset * 1000))
        if evidence['audio_present']:
            filt += ';[0:a][a]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[mix]'
        else:
            filt += ';[a]alimiter=limit=0.95[mix]'
        ffmpeg(['-i', str(media), '-i', str(auxiliary), '-filter_complex', filt,
                '-map', '0:v:0', '-map', '[mix]', '-t', str(specification['duration_seconds'])] + video_encoding(), output)
    elif department == 'color_finish' and kind == 'color':
        bright = number(operation['brightness'], -0.2, 0.2, 'brightness')
        contrast = number(operation['contrast'], 0.8, 1.2, 'contrast')
        saturation = number(operation['saturation'], 0.8, 1.2, 'saturation')
        ffmpeg(['-i', str(media), '-vf', 'eq=brightness=%s:contrast=%s:saturation=%s' % (bright, contrast, saturation)] + video_encoding(), output)
    elif department == 'compositing_vfx' and kind == 'overlay':
        if not auxiliary or file_hash(auxiliary) != operation.get('approved_overlay_sha256'):
            raise ValueError('Approved overlay bytes required')
        x = int(number(operation['x'], 0, evidence['width'], 'overlay x'))
        y = int(number(operation['y'], 0, evidence['height'], 'overlay y'))
        with Image.open(auxiliary) as image:
            image.load()
            if image.format != 'PNG' or image.width + x > evidence['width'] or image.height + y > evidence['height']:
                raise ValueError('PNG overlay does not fit the approved frame')
        ffmpeg(['-i', str(media), '-loop', '1', '-i', str(auxiliary), '-filter_complex',
                '[0:v][1:v]overlay=%s:%s:shortest=1[v]' % (x, y), '-map', '[v]', '-map', '0:a?',
                '-t', str(specification['duration_seconds'])] + video_encoding(), output)
    elif department == 'titles_graphics' and kind == 'title':
        text = operation['text']
        if not isinstance(text, str) or not 1 <= len(text) <= 160 or '\x00' in text:
            raise ValueError('Approved title must contain 1–160 characters')
        size = int(number(operation.get('font_size', 32), 12, 96, 'font size'))
        font = ImageFont.load_default(size=size)
        image = Image.new('RGBA', (evidence['width'], evidence['height']), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        x = int(number(operation['x'], 0, image.width, 'title x'))
        y = int(number(operation['y'], 0, image.height, 'title y'))
        box = draw.multiline_textbbox((x, y), text, font=font)
        if box[2] > image.width or box[3] > image.height:
            raise ValueError('Approved title would leave the frame')
        draw.multiline_text((x, y), text, font=font, fill='white', stroke_width=1, stroke_fill='black')
        overlay = directory / 'approved_title.png';image.save(overlay)
        ffmpeg(['-i', str(media), '-loop', '1', '-i', str(overlay), '-filter_complex',
                '[0:v][1:v]overlay=0:0:shortest=1[v]', '-map', '[v]', '-map', '0:a?',
                '-t', str(specification['duration_seconds'])] + video_encoding(), output)
    else:
        raise ValueError('Unsupported operation for this department')
    result_evidence = inspect_video(output, expected)
    if result_evidence['audio_present']:
        audio_evidence(output)
    result = seal({'schema': SCHEMAS[department], 'app_version': '1.0.1', 'department': department,
                   'status': 'completed', 'source_work_order_fingerprint': order['work_order_fingerprint'],
                   'source_qc_fingerprint': order['qc_packet']['qc_fingerprint'],
                   'source_job_fingerprint': order['qc_packet']['source_job_fingerprint'],
                   'input_sha256': evidence['sha256'], 'operation': operation, 'output': result_evidence,
                   'output_specification': expected, 'auxiliary_evidence': auxiliary_evidence,
                   'source_packets_preserved': True, 'creative_integrity_preserved': False,
                   'creative_integrity_scope': 'Pending independent final review of modified pixels/audio',
                   'ready_for_final_qc': True, 'delivery_authorized': False}, 'result_fingerprint')
    return result, str(output), write_json(directory, 'department_result.json', result)


def verify_department(result, order, output):
    verify(result, 'result_fingerprint')
    if result.get('status') != 'completed' or result.get('source_work_order_fingerprint') != order['work_order_fingerprint'] or result.get('department') != order['department']:
        raise ValueError('Department response does not match its order')
    if result.get('input_sha256') != order['input_sha256'] or result.get('operation') != order['operation'] or result.get('source_packets_preserved') is not True:
        raise ValueError('Department response changed approved instructions')
    evidence = inspect_video(output, result['output_specification'])
    if evidence['sha256'] != result.get('output', {}).get('sha256'):
        raise ValueError('Department output bytes differ from registered media')
    return evidence


def assemble_timeline(paths, results):
    if not paths or len(paths) != len(results) or len(paths) > 24:
        raise ValueError('Timeline requires 1–24 reviewed finished shots in explicit order')
    project = results[0].get('project_context', {}).get('project_id')
    if not project or any(r.get('project_context', {}).get('project_id') != project for r in results):
        raise ValueError('Cannot assemble shots from different projects')
    evidence = []
    for path, result in zip(paths, results):
        verify(result, 'result_fingerprint')
        if result.get('post_complete') is not True or (result.get('final_qc') or {}).get('decision') != 'PASS' or result.get('delivery_authorized') is not True:
            raise ValueError('Timeline contains a shot without final QC')
        from joat_post_pipeline import validate_post_receipts
        validate_post_receipts(result)
        item = inspect_video(path, result['final_master']['specification'])
        if item['sha256'] != result['final_master']['sha256']:
            raise ValueError('Timeline shot bytes do not match final QC')
        evidence.append(item)
    first = evidence[0]
    if any((x['width'], x['height'], x['fps']) != (first['width'], first['height'], first['fps']) for x in evidence):
        raise ValueError('Shots must share frame size/rate; normalization requires explicit approval')
    directory = Path(tempfile.mkdtemp(prefix='joat-timeline-'))
    args = []
    for path in paths:
        args += ['-i', str(path)]
    filters = []
    for index, item in enumerate(evidence):
        filters.append('[%s:v]setpts=PTS-STARTPTS[v%s]' % (index, index))
        if item['audio_present']:
            filters.append('[%s:a]aresample=48000,aformat=channel_layouts=stereo,asetpts=PTS-STARTPTS[a%s]' % (index, index))
        else:
            filters.append('anullsrc=r=48000:cl=stereo,atrim=duration=%s,asetpts=PTS-STARTPTS[a%s]' % (item['duration_seconds'], index))
    filters.append(''.join('[v%s][a%s]' % (i, i) for i in range(len(paths))) + 'concat=n=%s:v=1:a=1[v][a]' % len(paths))
    output = directory / 'timeline_master.mp4'
    ffmpeg(args + ['-filter_complex', ';'.join(filters), '-map', '[v]', '-map', '[a]'] + video_encoding(), output)
    specification = {'duration_seconds': sum(x['duration_seconds'] for x in evidence), 'aspect_ratio': results[0]['final_master']['specification']['aspect_ratio']}
    final = inspect_video(output, specification);audio_evidence(output)
    result = seal({'schema': 'joat.timeline_result.v1', 'ordered_shots': [r['result_fingerprint'] for r in results],
                   'project_id': results[0]['project_context']['project_id'], 'final_master': dict(final, specification=specification),
                   'final_qc_required': True, 'delivery_authorized': False}, 'result_fingerprint')
    return result, str(output), write_json(directory, 'timeline_result.json', result)


def archive_delivery(result, media):
    verify(result, 'result_fingerprint')
    if result.get('schema') not in ('joat.post_production_result.v1', 'joat.timeline_result.v1') or result.get('delivery_authorized') is not True:
        raise ValueError('Final reviewed and authorized result required')
    if result['schema'] == 'joat.post_production_result.v1':
        from joat_post_pipeline import validate_post_receipts
        validate_post_receipts(result)
    qc = result.get('final_qc', {})
    if qc.get('decision') != 'PASS' or qc.get('reviewer') != 'Dezz-9-10' or qc.get('asset_sha256') != result['final_master']['sha256'] or set(qc.get('checks', {})) != {'picture', 'audio', 'titles', 'continuity'} or any(v is not True for v in qc['checks'].values()):
        raise ValueError('Independent final review must bind actual master bytes')
    evidence = inspect_video(media, result['final_master']['specification'])
    if evidence['sha256'] != result['final_master']['sha256']:
        raise ValueError('Final master byte mismatch')
    if evidence['audio_present']:
        audio_evidence(media)
    directory = Path(tempfile.mkdtemp(prefix='joat-delivery-'))
    output = directory / 'JOAT_final_master.mp4';shutil.copyfile(media, output)
    manifest = seal({'schema': 'joat.delivery_archive_packet.v1', 'app_version': '1.0.1',
                     'source_result_fingerprint': result['result_fingerprint'], 'master': evidence,
                     'storage_status': 'DOWNLOAD_READY', 'durable_remote_archive': False,
                     'owner_must_save_download': True}, 'packet_fingerprint')
    write_json(directory, 'delivery_manifest.json', manifest)
    write_json(directory, 'approved_final_result.json', result)
    archive = directory / 'JOAT_delivery.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in (output, directory / 'delivery_manifest.json', directory / 'approved_final_result.json'):
            bundle.write(path, path.name)
    return manifest, str(output), str(archive), str(directory / 'delivery_manifest.json')
