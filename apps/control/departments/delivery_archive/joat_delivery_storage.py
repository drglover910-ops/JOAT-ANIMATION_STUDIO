"""Verified private-bucket delivery retention. File version: 1.0.1."""
FILE_VERSION = "1.0.1"
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import urllib.request
import zipfile

from joat_post_media import archive_delivery, file_hash, seal, verify

SPACE = "Dezz-9-10/J.O.A.T.-Delivery-Archive-Bot"
BUCKET = "Dezz-9-10/J.O.A.T.-Studio-storage"
ROOT = Path("/studio/joat-studio")
LOCK = threading.Lock()


def require_studio_mount():
    from joat_local_context import local_role,mount_check
    if local_role("delivery"):return mount_check("delivery")
    if os.environ.get("SPACE_ID") != SPACE:
        raise ValueError("Durable production delivery must run in the Delivery Archive Space.")
    with urllib.request.urlopen("https://huggingface.co/api/spaces/" + SPACE, timeout=30) as response:
        metadata = json.load(response)
    mounts = metadata.get("runtime", {}).get("volumes", [])
    if not any(v.get("source") == BUCKET and v.get("mountPath") == "/studio"
               and v.get("readOnly") is False for v in mounts):
        raise ValueError("Mount J.O.A.T.-Studio-storage at /studio with read/write access.")
    if not Path("/studio").is_dir():
        raise ValueError("Studio bucket mount is unavailable; no temporary archive fallback.")


def _json_bytes(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()


def _write_once(path, raw):
    if path.is_symlink():
        raise ValueError("Archive files cannot be symlinks.")
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("Archive conflict; existing files were preserved.")
        return
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    if path.read_bytes() != raw:
        raise ValueError("Bucket archive write/readback failed.")


def archive_and_store(result, media, root=ROOT, mount_validator=require_studio_mount):
    # Existing validator checks final owner PASS, all receipts and actual decoded bytes.
    packet, master, archive, download_manifest = archive_delivery(result, media)
    mount_validator()
    project = result.get("project_context", {}).get("project_id", "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", project) or project in (".", ".."):
        raise ValueError("Delivery project ID is invalid.")
    identifier = hashlib.sha256((project + ":" + result["result_fingerprint"]
        + ":" + packet["master"]["sha256"]).encode()).hexdigest()
    root = Path(root)
    folder = root / "deliveries" / project / identifier
    for parent in (root, root / "deliveries", root / "deliveries" / project, folder):
        if parent.is_symlink():
            raise ValueError("Archive directories cannot be symlinks.")
    uri = f"hf://buckets/{BUCKET}/joat-studio/deliveries/{project}/{identifier}/"
    stored_master = folder / "JOAT_final_master.mp4"
    stored_result = folder / "approved_final_result.json"
    stored_manifest = folder / "delivery_manifest.json"
    with LOCK:
        folder.mkdir(parents=True, exist_ok=True)
        _write_once(stored_master, Path(master).read_bytes())
        _write_once(stored_result, _json_bytes(result))
        if file_hash(stored_master) != packet["master"]["sha256"] or json.loads(stored_result.read_text()) != result:
            raise ValueError("Archived master or approval differs from the approved delivery.")
        if stored_manifest.exists():
            if stored_manifest.is_symlink():
                raise ValueError("Archive manifest cannot be a symlink.")
            retained = json.loads(stored_manifest.read_text())
            verify(retained, "packet_fingerprint")
            if (retained.get("source_result_fingerprint") != result["result_fingerprint"]
                or retained.get("master") != packet["master"]
                or retained.get("storage", {}).get("master_uri") != uri + stored_master.name
                or retained.get("durable_remote_archive") is not True):
                raise ValueError("Stored archive manifest differs; no files were overwritten.")
            packet = retained
        else:
            packet.update(file_version=FILE_VERSION, storage_status="ARCHIVED_READBACK_VERIFIED",
                durable_remote_archive=True, owner_must_save_download=False,
                storage={"bucket": BUCKET, "archive_id": identifier,
                         "master_uri": uri + stored_master.name,
                         "approved_result_uri": uri + stored_result.name,
                         "manifest_uri": uri + stored_manifest.name,
                         "master_sha256_verified": True, "approved_result_readback_verified": True})
            packet = seal(packet, "packet_fingerprint")
            _write_once(stored_manifest, _json_bytes(packet))
        readback = json.loads(stored_manifest.read_text())
        verify(readback, "packet_fingerprint")
        if readback != packet:
            raise ValueError("Stored archive manifest readback mismatch.")
    # Return /tmp exports for Gradio, without exposing the entire private bucket.
    Path(download_manifest).write_bytes(_json_bytes(packet))
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in (Path(master), Path(download_manifest), Path(master).parent / "approved_final_result.json"):
            bundle.write(path, path.name)
    return packet, master, archive, download_manifest
