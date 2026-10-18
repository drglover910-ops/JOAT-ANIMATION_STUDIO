"""Actual MP4 inspection shared by Generation Worker and independent QC."""
import hashlib
from pathlib import Path
import av

def file_hash(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_video(path, specification):
    """Decode every video frame, rather than accept a filename or open port."""
    path = Path(path)
    if not path.is_file() or path.stat().st_size == 0 or path.stat().st_size > 512 * 1024 * 1024:
        raise ValueError('Missing, empty, or oversized video file')
    try:
        with av.open(str(path)) as container:
            if 'mp4' not in container.format.name and 'mov' not in container.format.name:
                raise ValueError('Video is not an MP4 container')
            stream = container.streams.video[0]
            width, height = stream.width, stream.height
            fps = float(stream.average_rate or 0)
            if width <= 0 or height <= 0 or fps <= 0:
                raise ValueError('Video dimensions or frame rate unavailable')
            timestamps = []
            for frame in container.decode(stream):
                if frame.pts is None:
                    raise ValueError('Video frame has no timestamp')
                timestamps.append(float(frame.pts * frame.time_base))
                if len(timestamps) > 20000:
                    raise ValueError('Video exceeds per-shot decode limit')
            if len(timestamps) < 2 or any(b <= a for a, b in zip(timestamps, timestamps[1:])):
                raise ValueError('Video has too few frames or invalid timing')
            duration = timestamps[-1] - timestamps[0] + 1 / fps
            requested = float(specification['duration_seconds'])
            if abs(duration - requested) > max(0.1, 2 / fps):
                raise ValueError('Rendered duration differs from the approved job')
            num, den = map(float, specification['aspect_ratio'].split(':'))
            sar = float(stream.sample_aspect_ratio or 1)
            if abs((width * sar / height) / (num / den) - 1) > 0.01:
                raise ValueError('Rendered aspect differs from the approved job')
            return {'sha256': file_hash(path), 'size_bytes': path.stat().st_size,
                    'width': width, 'height': height, 'fps': fps, 'duration_seconds': duration,
                    'decoded_frames': len(timestamps), 'codec': stream.codec_context.name,
                    'audio_present': bool(container.streams.audio), 'video_fully_decoded': True}
    except ValueError:
        raise
    except Exception:
        raise ValueError('Video could not be decoded') from None


