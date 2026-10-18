"""J.O.A.T. CPU video-reference evidence helper. File version: 1.0.2.

Evidence extraction is deliberately separate from semantic interpretation and QC.
Uploaded originals and existing studio assets are never modified. No GPU or
inference provider is called by this module.
"""
from __future__ import annotations

import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse
from urllib.request import Request
import uuid

FILE_VERSION = "1.0.2"
MAX_SOURCE_BYTES = 2 * 1024 * 1024 * 1024
MAX_SOURCE_LABEL = "2 GiB"
MAX_YOUTUBE_BYTES = 512 * 1024 * 1024
MIN_EVIDENCE_FREE_BYTES = 128 * 1024 * 1024
MAX_WINDOW_SECONDS = 60.0
MAX_REPORTS = 20
MAX_TRANSCRIPT_CHARS = 60000
VIDEO_SUFFIXES = {".mp4", ".mov", ".webm", ".mkv", ".m4v", ".avi"}
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _container_format(path):
    # Force a local media demuxer: renamed HLS/concat playlists must not open
    # network or other local resources while FFmpeg probes their contents.
    suffix = Path(path).suffix.lower()
    if suffix in {".mp4", ".mov", ".m4v"}:
        return "mov"
    if suffix in {".webm", ".mkv"}:
        return "matroska"
    if suffix == ".avi":
        return "avi"
    raise VideoReferenceError("This video container is not supported.")


class VideoReferenceError(ValueError):
    """A safe, actionable failure message suitable for the owner interface."""


def canonical_youtube_url(value: str) -> str:
    """Accept public YouTube video links only; strip tracking and other URLs."""
    value = str(value or "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"https", "http"} or parsed.username or parsed.password:
        raise VideoReferenceError("Paste a public https:// YouTube video link.")
    try:
        if parsed.port not in {None, 80, 443}:
            raise VideoReferenceError("The YouTube link has an unsupported port.")
    except ValueError:
        raise VideoReferenceError("The YouTube link has an invalid port.") from None
    host = (parsed.hostname or "").lower()
    if host == "youtu.be":
        pieces = parsed.path.strip("/").split("/")
        video_id = pieces[0] if len(pieces) == 1 else ""
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            ids = parse_qs(parsed.query).get("v", [])
            video_id = ids[0] if len(ids) == 1 else ""
        else:
            pieces = parsed.path.strip("/").split("/")
            video_id = pieces[1] if len(pieces) == 2 and pieces[0] in {"shorts", "embed"} else ""
    else:
        video_id = ""
    if not VIDEO_ID.fullmatch(video_id):
        raise VideoReferenceError("Use a YouTube watch, youtu.be, Shorts, or embed link for one public video.")
    return "https://www.youtube.com/watch?v=" + video_id


def _finite_number(value, label):
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        raise VideoReferenceError(label + " must be a finite number.") from None
    if not math.isfinite(result):
        raise VideoReferenceError(label + " must be a finite number.")
    return result


def _private_root(root_dir):
    root = Path(root_dir).expanduser()
    if root.is_symlink():
        raise VideoReferenceError("The video-reference storage directory cannot be a symbolic link.")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not root.is_dir():
        raise VideoReferenceError("The video-reference storage location is not a directory.")
    return root.resolve()


def _prune(root, keep_directory):
    completed = []
    for child in root.iterdir():
        if child == keep_directory or child.is_symlink() or not child.is_dir():
            continue
        if re.fullmatch(r"reference-[0-9]{8}T[0-9]{6}-[a-f0-9]{12}", child.name) and (child / "analysis.json").is_file():
            completed.append(child)
    completed.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for child in completed[MAX_REPORTS - 1:]:
        shutil.rmtree(child)


def _validated_upload(source):
    source = Path(source)
    if source.is_symlink() or not source.is_file():
        raise VideoReferenceError("Choose an uploaded video file.")
    if source.suffix.lower() not in VIDEO_SUFFIXES:
        raise VideoReferenceError("Upload an MP4, MOV, WebM, MKV, M4V, or AVI video.")
    before = source.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size <= 0:
        raise VideoReferenceError("The uploaded video is empty or is not a regular file.")
    if before.st_size > MAX_SOURCE_BYTES:
        raise VideoReferenceError("This video exceeds the 2 GiB upload limit. Choose a smaller source or selected clip.")
    return source, before


def _hash_existing(source, maximum=MAX_SOURCE_BYTES, label="uploaded video"):
    source = Path(source)
    before = source.stat()
    if before.st_size <= 0 or before.st_size > maximum:
        raise VideoReferenceError("The " + label + " is empty or exceeds its size limit.")
    digest = hashlib.sha256()
    total = 0
    started = time.monotonic()
    with source.open("rb") as incoming:
        while chunk := incoming.read(1024 * 1024):
            total += len(chunk)
            if total > maximum:
                raise VideoReferenceError("The " + label + " exceeds its size limit.")
            if time.monotonic() - started > 120:
                raise VideoReferenceError("Reading the source timed out. Try a shorter local clip.")
            digest.update(chunk)
    after = source.stat()
    identity = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_ctime_ns)
    if identity(before) != identity(after) or total != before.st_size:
        raise VideoReferenceError("The source changed while being read. Prepare its evidence again.")
    return digest.hexdigest(), total


def _ensure_disk_space(directory, required=MIN_EVIDENCE_FREE_BYTES):
    if shutil.disk_usage(directory).free < required:
        raise VideoReferenceError("The Space has insufficient temporary disk space. Let old upload caches expire or use a smaller clip.")


def _run_child(action, request, directory, timeout):
    request_path = directory / (action + "-request.json")
    response_path = directory / (action + "-response.json")
    request_path.write_text(json.dumps(request), encoding="utf-8")
    try:
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--internal", action, str(request_path), str(response_path)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        returncode = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        # yt-dlp may spawn FFmpeg. Kill that whole process group as well as
        # the Python child so an abandoned merge cannot continue consuming CPU.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)
        raise VideoReferenceError("Video analysis timed out. Try a shorter time window or upload the video directly.") from None
    finally:
        request_path.unlink(missing_ok=True)
    if not response_path.is_file() or response_path.stat().st_size > 2 * 1024 * 1024:
        raise VideoReferenceError("Video analysis could not finish safely. Try a shorter or smaller uploaded video.")
    response = json.loads(response_path.read_text(encoding="utf-8"))
    response_path.unlink(missing_ok=True)
    if returncode or not response.get("ok"):
        raise VideoReferenceError(response.get("error", "The video could not be inspected."))
    return response["result"]


def _youtube_error(exc):
    message = str(exc).lower()
    if any(word in message for word in ["sign in", "confirm you", "bot", "cookies", "403", "429", "forbidden", "too many requests"]):
        return "YouTube blocked this server or requires a YouTube account. Hugging Face sign-in cannot authorize YouTube playback. Open the video in Safari/YouTube, then upload your existing video or a recording you are allowed to use (up to 2 GiB)."
    if any(word in message for word in ["private", "unavailable", "removed", "copyright", "restricted", "not available"]):
        return "This YouTube video is unavailable to this server. Upload a video you can access instead."
    return "The YouTube video could not be read from this server. Upload the video instead; the failure does not prove the video is missing."


def _youtube_metadata(request):
    try:
        import yt_dlp
    except ImportError:
        raise VideoReferenceError("YouTube support is not installed. Update requirements.txt, or upload the video directly.") from None
    options = {"quiet": True, "no_warnings": True, "noplaylist": True, "socket_timeout": 15, "retries": 0,
               "extractor_retries": 0, "cachedir": False, "skip_download": True,
               "js_runtimes": {"deno": {"path": shutil.which("deno") or str(Path(sys.executable).parent / "deno")}}}
    try:
        with yt_dlp.YoutubeDL(options) as reader:
            info = reader.extract_info(canonical_youtube_url(request["url"]), download=False)
    except Exception as exc:
        raise VideoReferenceError(_youtube_error(exc)) from None
    if info.get("is_live") or info.get("live_status") in {"is_live", "is_upcoming"}:
        raise VideoReferenceError("Use a finished public YouTube video rather than a live stream.")
    languages = []
    provenance = "unavailable"
    caption_formats = []
    for bucket, label in [(info.get("subtitles") or {}, "youtube_manual_captions"), (info.get("automatic_captions") or {}, "youtube_automatic_captions")]:
        if bucket:
            languages = sorted(bucket, key=lambda key: (key != "en", not key.startswith("en"), key))
            provenance = label
            caption_formats = bucket[languages[0]]
            break
    caption = next((item for item in caption_formats if item.get("ext") == "json3"), None)
    caption = caption or next((item for item in caption_formats if item.get("ext") == "vtt"), None)
    return {"id": str(info.get("id", "")), "title": str(info.get("title", ""))[:500],
            "channel": str(info.get("channel") or info.get("uploader") or "")[:500],
            "duration_seconds": info.get("duration"), "caption_language": languages[0] if languages else None,
            "caption_provenance": provenance, "caption_url": caption.get("url") if caption else None,
            "caption_extension": caption.get("ext") if caption else None}


def _youtube_download(request):
    import imageio_ffmpeg
    import yt_dlp
    directory = Path(request["directory"])
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_YOUTUBE_BYTES, MAX_YOUTUBE_BYTES))
    except (ImportError, ValueError, OSError):
        pass
    progress_sizes = {}
    def size_guard(progress):
        filename = str(progress.get("filename", "stream"))
        progress_sizes[filename] = max(progress_sizes.get(filename, 0), progress.get("downloaded_bytes", 0))
        estimated_current = max(progress_sizes[filename], progress.get("total_bytes", 0) or 0)
        total = sum(size for key, size in progress_sizes.items() if key != filename) + estimated_current
        if total > MAX_YOUTUBE_BYTES:
            raise VideoReferenceError("The YouTube video exceeds the 512 MiB limit. Upload a smaller copy.")
    options = {"quiet": True, "no_warnings": True, "noplaylist": True, "socket_timeout": 15,
               "retries": 0, "extractor_retries": 0, "fragment_retries": 0, "cachedir": False, "js_runtimes": {"deno": {"path": shutil.which("deno") or str(Path(sys.executable).parent / "deno")}},
               "format": "bestvideo[height<=720]+bestaudio/best[height<=720]", "merge_output_format": "mp4", "max_filesize": MAX_YOUTUBE_BYTES,
               "outtmpl": str(directory / "youtube-source.%(ext)s"), "overwrites": False,
               "progress_hooks": [size_guard], "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(),
               "writesubtitles": False, "writeautomaticsub": False}
    try:
        with yt_dlp.YoutubeDL(options) as reader:
            reader.extract_info(canonical_youtube_url(request["url"]), download=True)
    except Exception as exc:
        if isinstance(exc, VideoReferenceError):
            raise
        raise VideoReferenceError(_youtube_error(exc)) from None
    files = [p for p in directory.glob("youtube-source.*") if p.suffix.lower() in VIDEO_SUFFIXES and not p.is_symlink()]
    if len(files) != 1 or files[0].stat().st_size > MAX_YOUTUBE_BYTES:
        raise VideoReferenceError("YouTube did not return a usable video within the 512 MiB limit. Upload the video directly.")
    return {"source_path": str(files[0])}


def _fetch_caption(metadata, directory):
    """One bounded optional read; captions failing must not discard the video."""
    url = metadata.get("caption_url")
    extension = metadata.get("caption_extension")
    if not url or extension not in {"json3", "vtt"}:
        return None, None
    parsed = urlparse(url)
    try:
        valid_port = parsed.port in {None, 443}
    except ValueError:
        valid_port = False
    if (parsed.scheme != "https" or parsed.hostname not in {"youtube.com", "www.youtube.com", "m.youtube.com"}
            or parsed.username or parsed.password or not valid_port or parsed.path != "/api/timedtext"):
        return None, "YouTube captions were unavailable through the supported public caption endpoint."
    # Disable redirects: a server-supplied caption URL cannot redirect this
    # otherwise restricted read to an arbitrary domain or private address.
    from urllib.request import build_opener, HTTPRedirectHandler
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    try:
        with build_opener(NoRedirect()).open(Request(url, headers={"User-Agent": "JOAT-VideoReference/1.0"}), timeout=15) as response:
            data = response.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024:
            return None, "YouTube captions exceeded the bounded caption size limit."
        path = Path(directory) / ("youtube-caption." + extension)
        path.write_bytes(data)
        return str(path), None
    except Exception:
        return None, "The video was downloaded, but its optional YouTube captions could not be retrieved."


def _parse_captions(path, start, end):
    if not path:
        return ""
    path = Path(path)
    if not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    phrases = []
    if path.suffix == ".json3":
        try:
            events = json.loads(text).get("events", [])
            for item in events:
                position = float(item.get("tStartMs", 0)) / 1000
                duration = float(item.get("dDurationMs", 0)) / 1000
                if position <= end and position + duration >= start:
                    phrase = "".join(str(s.get("utf8", "")) for s in item.get("segs", [])).strip()
                    if phrase and (not phrases or phrase != phrases[-1]):
                        phrases.append(phrase)
        except (ValueError, TypeError, AttributeError):
            return ""
    elif path.suffix == ".vtt":
        def stamp(value):
            parts = value.split(":")
            return sum(float(piece) * (60 ** index) for index, piece in enumerate(reversed(parts)))
        for block in re.split(r"\n\s*\n", text):
            lines = block.splitlines()
            timing = next((index for index, line in enumerate(lines) if " --> " in line), None)
            if timing is None:
                continue
            try:
                left, right = lines[timing].split(" --> ", 1)
                if stamp(left) <= end and stamp(right.split()[0]) >= start:
                    phrase = re.sub(r"<[^>]*>", "", " ".join(lines[timing + 1:])).strip()
                    if phrase and (not phrases or phrase != phrases[-1]):
                        phrases.append(phrase)
            except (ValueError, IndexError):
                continue
    return html.unescape("\n".join(phrases))[:MAX_TRANSCRIPT_CHARS]


def _decode_reference(request):
    import av
    from PIL import Image, ImageChops, ImageDraw, ImageStat
    source = Path(request["source"])
    directory = Path(request["directory"])
    started = time.monotonic()
    with av.open(str(source), format=_container_format(source),
                 options={"protocol_whitelist": "file,pipe", "enable_drefs": "0"}) as container:
        if not container.streams.video:
            raise VideoReferenceError("The uploaded file contains no video stream.")
        video = container.streams.video[0]
        video.thread_type = "SLICE"
        video.codec_context.thread_count = 2
        width, height = video.codec_context.width, video.codec_context.height
        if width <= 0 or height <= 0 or width * height > 16777216:
            raise VideoReferenceError("The video dimensions exceed the safe CPU analysis limit.")
        fps = float(video.average_rate or video.guessed_rate or 0)
        duration = float(video.duration * video.time_base) if video.duration is not None else (float(container.duration / av.time_base) if container.duration else None)
        if duration is not None and (not math.isfinite(duration) or duration <= 0):
            duration = None
        selection = request.get("window_mode", "custom")
        if selection not in {"custom", "first_60", "last_60"}:
            raise VideoReferenceError("Choose a supported reference section.")
        start = request["start"]
        window = request["window"]
        if selection == "first_60":
            start, window = 0.0, 60.0
        elif selection == "last_60":
            if duration is None:
                raise VideoReferenceError("The last 60 seconds requires a readable video duration. Use a custom start time for this source.")
            start, window = max(0.0, duration - 60.0), 60.0
        # Reference timestamps are elapsed video time, including sources whose
        # encoded timeline begins at a nonzero presentation timestamp.
        origin = float(video.start_time * video.time_base) if video.start_time is not None else 0.0
        if duration is not None and start >= duration:
            raise VideoReferenceError("The selected start time is beyond the end of this video.")
        end = min(start + window, duration) if duration is not None else start + window
        step = max((end - start) / 7, 0.01)
        targets = [start + i * step for i in range(8)]
        targets[-1] = max(start, end - max(1 / fps if fps > 0 else 0.1, 0.02))
        if start > 0:
            container.seek(int((start + origin) / video.time_base), stream=video,
                           backward=True, any_frame=False)
        target_index = 0
        frame_paths = []
        scene_timestamps = []
        sampled_at = -1.0
        previous_small = None
        coarse_samples = 0
        decoded = 0
        observed_first = None
        observed_last = None
        for frame in container.decode(video):
            decoded += 1
            if decoded > 10000 or time.monotonic() - started > 75:
                raise VideoReferenceError("This video needs more CPU decoding than allowed. Select a shorter window or export at 720p.")
            timestamp = float(frame.pts * frame.time_base) - origin if frame.pts is not None else (decoded - 1) / fps if fps else None
            if timestamp is None:
                raise VideoReferenceError("This video has no usable timestamps or frame rate.")
            if timestamp < start - 0.001:
                continue
            if timestamp >= end + 0.001:
                break
            observed_first = timestamp if observed_first is None else observed_first
            observed_last = timestamp
            need_gallery = target_index < len(targets) and timestamp >= targets[target_index] - 0.001
            need_scene = timestamp - sampled_at >= 0.49
            if not need_gallery and not need_scene:
                continue
            image = frame.to_image().convert("RGB")
            if need_scene:
                small = image.resize((64, 36))
                if previous_small is not None:
                    difference = sum(ImageStat.Stat(ImageChops.difference(previous_small, small)).mean) / (3 * 255)
                    if difference >= 0.28:
                        scene_timestamps.append(round(timestamp, 4))
                previous_small = small
                sampled_at = timestamp
                coarse_samples += 1
            if need_gallery:
                image.thumbnail((960, 960))
                path = directory / f"frame-{len(frame_paths) + 1:02d}.jpg"
                image.save(path, quality=85, optimize=True)
                frame_paths.append({"path": str(path), "timestamp_seconds": round(timestamp, 4)})
                while target_index < len(targets) and timestamp >= targets[target_index] - 0.001:
                    target_index += 1
        if not frame_paths:
            raise VideoReferenceError("No frames could be decoded in the selected time window. Try the beginning of the video.")
        sheet = Image.new("RGB", (4 * 320, math.ceil(len(frame_paths) / 4) * 210), "#101010")
        draw = ImageDraw.Draw(sheet)
        for index, item in enumerate(frame_paths):
            with Image.open(item["path"]) as thumb:
                thumb.thumbnail((312, 176))
                x, y = (index % 4) * 320, (index // 4) * 210
                sheet.paste(thumb, (x + (320 - thumb.width) // 2, y + 2))
                draw.text((x + 8, y + 183), f'{item["timestamp_seconds"]:.2f}s', fill="white")
        contact_sheet = directory / "contact_sheet.jpg"
        sheet.save(contact_sheet, quality=90)
        return {"technical": {"width": width, "height": height, "fps": round(fps, 6),
                   "duration_seconds": duration, "duration_source": "video_stream_timestamps" if video.duration is not None else "container_metadata",
                   "codec": video.codec_context.name, "audio_present": bool(container.streams.audio),
                   "full_video_decoded": False},
                "window": {"start_seconds": start, "end_seconds": end, "duration_seconds": round(end - start, 6),
                    "selection": selection, "timestamp_basis": "elapsed_video_time",
                    "encoded_video_start_seconds": origin,
                    "observed_first_frame_seconds": observed_first, "observed_last_frame_seconds": observed_last,
                    "decoded_frames_including_seek_preroll": decoded},
                "frames": frame_paths, "contact_sheet_path": str(contact_sheet),
                "scene_changes": {"method": "RGB mean absolute difference at approximately 2 samples/second",
                    "threshold": 0.28, "timestamps_seconds": scene_timestamps, "samples_inspected": coarse_samples,
                    "coverage": "coarse candidates; fast cuts can be missed and motion/fades can be mistaken for cuts"}}


def _extract_audio(source, directory, start, window):
    import imageio_ffmpeg
    output = directory / "reference_audio.wav"
    args = [imageio_ffmpeg.get_ffmpeg_exe(), "-nostdin", "-hide_banner", "-loglevel", "error",
            "-protocol_whitelist", "file,pipe", "-ss", str(start), "-f", _container_format(source), "-i", str(source), "-t", str(window),
            "-map", "0:a:0", "-vn", "-threads", "2", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(output)]
    try:
        result = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=60, check=False)
    except subprocess.TimeoutExpired:
        output.unlink(missing_ok=True)
        return None
    if result.returncode or not output.is_file() or output.stat().st_size < 44 or output.stat().st_size > 4 * 1024 * 1024:
        output.unlink(missing_ok=True)
        return None
    return str(output)


def prepare_reference(upload_path, youtube_url, start_seconds=0, window_seconds=30,
                      transcript_text="", product_goal="", root_dir="/data/joat-main-assistant/video-references",
                      window_mode="custom"):
    """Extract bounded real evidence. Uploads take precedence over a pasted link."""
    if window_mode not in {"custom", "first_60", "last_60"}:
        raise VideoReferenceError("Choose a supported reference section.")
    start = _finite_number(start_seconds, "Start time") if window_mode == "custom" else 0.0
    window = _finite_number(window_seconds, "Window length") if window_mode == "custom" else 60.0
    if start < 0 or start > 24 * 3600:
        raise VideoReferenceError("Start time must be between 0 and 86400 seconds.")
    if window <= 0 or window > MAX_WINDOW_SECONDS:
        raise VideoReferenceError("Choose a window longer than 0 and no longer than 60 seconds.")
    transcript_text = str(transcript_text or "").strip()
    product_goal = str(product_goal or "").strip()
    if len(transcript_text) > MAX_TRANSCRIPT_CHARS or len(product_goal) > 12000:
        raise VideoReferenceError("The transcript or product brief is too long. Limit the transcript to 60000 characters and the brief to 12000.")
    if not upload_path and not str(youtube_url or "").strip():
        raise VideoReferenceError("Upload a video or paste one public YouTube video link.")
    canonical_url = canonical_youtube_url(youtube_url) if not upload_path else None
    root = _private_root(root_dir)
    _ensure_disk_space(root)
    analysis_id = "reference-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:12]
    directory = root / analysis_id
    directory.mkdir(mode=0o700)
    scratch = tempfile.TemporaryDirectory(prefix="joat-video-reference-")
    source_directory = Path(scratch.name)
    source_path = None
    try:
        source = {"kind": "upload" if upload_path else "youtube_public_video", "url": canonical_url,
                  "title": Path(str(upload_path)).name[:500] if upload_path else "", "channel": ""}
        caption_path = None
        caption_provenance = "unavailable"
        caption_language = None
        caption_warning = None
        if upload_path:
            # Read the validated Gradio upload directly: no second full-size source copy.
            source_path, source_stat = _validated_upload(upload_path)
            source_sha, size_bytes = _hash_existing(source_path)
        else:
            _ensure_disk_space(source_directory, 2 * MAX_YOUTUBE_BYTES + MIN_EVIDENCE_FREE_BYTES)
            metadata = _run_child("youtube-metadata", {"url": canonical_url}, directory, 50)
            source.update({"title": metadata["title"], "channel": metadata["channel"], "youtube_id": metadata["id"]})
            download = _run_child("youtube-download", {"url": canonical_url, "directory": str(source_directory)}, directory, 150)
            source_path = Path(download["source_path"])
            source_sha, size_bytes = _hash_existing(source_path, maximum=MAX_YOUTUBE_BYTES, label="downloaded YouTube video")
            if not transcript_text:
                try:
                    caption_path, caption_warning = _run_child("caption", {"metadata": metadata,
                                                              "directory": str(source_directory)}, directory, 25)
                except VideoReferenceError:
                    caption_warning = "The video was downloaded, but its optional YouTube captions could not be retrieved within the bounded time limit."
            caption_provenance = metadata["caption_provenance"]
            caption_language = metadata["caption_language"]
        source.update({"source_sha256": source_sha, "size_bytes": size_bytes,
                       "original_preserved": True, "original_retained_in_report_storage": False,
                       "full_source_copy_created": False, "upload_limit_bytes": MAX_SOURCE_BYTES,
                       "youtube_download_limit_bytes": MAX_YOUTUBE_BYTES})
        evidence = _run_child("decode", {"source": str(source_path), "directory": str(directory), "start": start,
                                        "window": window, "window_mode": window_mode}, directory, 90)
        start = evidence["window"]["start_seconds"]
        evidence["gallery"] = [(item["path"], f'{item["timestamp_seconds"]:.2f} seconds') for item in evidence["frames"]]
        evidence["audio_path"] = _extract_audio(source_path, directory, start, evidence["window"]["duration_seconds"]) if evidence["technical"]["audio_present"] else None
        actual_transcript = transcript_text or _parse_captions(caption_path, start, evidence["window"]["end_seconds"])
        unresolved = ["Sampled frames do not reveal the original production tools, prompts, or budget.",
                      "Visual, dialogue, music, branding, and CTA interpretation still need the semantic review step.",
                      "This reference report does not approve any studio asset, render, or QC result."]
        if not actual_transcript:
            unresolved.append("No transcript is available; extracted audio needs transcription or a supplied transcript.")
        if caption_warning:
            unresolved.append(caption_warning)
        if evidence["technical"]["audio_present"] and not evidence["audio_path"]:
            unresolved.append("The audio track exists but bounded WAV extraction failed.")
        report = {"schema": "joat.video_reference.v1", "file_version": FILE_VERSION, "analysis_id": analysis_id,
                  "directory": str(directory), "created_at": datetime.now(timezone.utc).isoformat(),
                  "status": "evidence_ready", "source_sha256": source_sha, "source": source, "evidence": evidence,
                  "transcript": {"text": actual_transcript, "available": bool(actual_transcript),
                                 "provenance": "user_supplied" if transcript_text else caption_provenance if actual_transcript else "unavailable",
                                 "language": caption_language if not transcript_text else None,
                                 "window_aligned": not bool(transcript_text)},
                  "product_goal": product_goal, "semantic_analysis": {"status": "not_run"},
                  "unresolved": unresolved, "gpu_called": False, "inference_called": False, "qc_approved": False}
        save_report(report, directory)
        _prune(root, directory)
        return report
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    finally:
        scratch.cleanup()


def save_report(report, directory):
    directory = Path(directory)
    path = directory / "analysis.json"
    temporary = directory / "analysis.json.tmp"
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)
    return str(path)


def render_summary(report):
    evidence = report["evidence"]
    technical = evidence["technical"]
    window = evidence["window"]
    def safe(value):
        text = html.escape(str(value or ""))
        return re.sub(r"([\\`*_{}\[\]()#!|])", r"\\\1", text)
    semantic = report.get("semantic_analysis") or {}
    result = semantic.get("result") or {}
    summary = [f'**Video reference {FILE_VERSION} — {safe(report["status"])}**',
               f'Source: {safe(report["source"]["kind"])} — {safe(report["source"].get("title"))}.',
               f'Section: {safe(window.get("selection", "custom"))}. Only this section is analyzed.',
               f'Inspected {window["start_seconds"]:.2f}–{window["end_seconds"]:.2f} seconds; {len(evidence["frames"])} timestamped frames.',
               f'{technical["width"]} × {technical["height"]}, {technical["fps"]:g} fps; audio track: {"present" if technical["audio_present"] else "absent"}.',
               f'Transcript: {report["transcript"]["provenance"]}. Coarse scene-change candidates: {len(evidence["scene_changes"]["timestamps_seconds"])}.',
               "Source tools and exact prompts cannot be recovered from the finished video alone."]
    if semantic.get("status") == "completed":
        summary.append("**Semantic review:** " + safe(result.get("summary", "Completed for the sampled frames.")))
        for observation in result.get("observations", [])[:12]:
            if isinstance(observation, dict):
                indices = observation.get("frame_indices") or []
                times = [f'{evidence["frames"][index]["timestamp_seconds"]:.2f}s' for index in indices
                         if isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(evidence["frames"])]
                summary.append((", ".join(times) + ": " if times else "Observation: ") + safe(observation.get("description", "")))
        for step in result.get("proposed_recreation", [])[:12]:
            if isinstance(step, dict):
                text = safe(step.get("studio_department", "Studio")) + ": " + safe(step.get("step", ""))
                if step.get("necessary_gap"):
                    text += " — needs: " + safe(step["necessary_gap"])
                summary.append(text)
        unknowns = result.get("unknowns") or []
        if unknowns:
            summary.append("**Unresolved:** " + "; ".join(safe(item) for item in unknowns[:10]))
    else:
        summary.append("CPU evidence is ready. Semantic analysis status: " + safe(semantic.get("status", "not_run")) + ".")
    speech = report.get("speech_analysis") or {}
    if speech.get("status") == "completed" and speech.get("text"):
        summary.append("**Speech transcription:** " + safe(speech["text"])[:6000])
    for label, attempt in (report.get("provider_attempts") or {}).items():
        if isinstance(attempt, dict) and attempt.get("status") in {"failed", "unavailable", "error", "failed_or_unverified", "attempt_started"}:
            summary.append(safe(label) + " review: " + safe(attempt.get("reason") or attempt.get("error_type") or attempt["status"]))
    return "\n\n".join(summary)


def _internal_main():
    action, request_path, response_path = sys.argv[2:5]
    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    try:
        handlers = {"decode": _decode_reference, "youtube-metadata": _youtube_metadata, "youtube-download": _youtube_download,
                    "caption": lambda req: _fetch_caption(req["metadata"], req["directory"])}
        result = handlers[action](request)
        response = {"ok": True, "result": result}
        returncode = 0
    except Exception as exc:
        response = {"ok": False, "error": str(exc) if isinstance(exc, VideoReferenceError) else "The video could not be decoded safely. Upload a standard MP4 or MOV file."}
        returncode = 1
    Path(response_path).write_text(json.dumps(response, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    raise SystemExit(returncode)


if __name__ == "__main__" and len(sys.argv) == 5 and sys.argv[1] == "--internal":
    _internal_main()
