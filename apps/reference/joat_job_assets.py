# joat_job_assets.py — FILE VERSION: 1.0.1
"""Owner-approved, job-scoped images in the existing Hugging Face bucket.

No inference, GHL dependency, canonical registration or production QC approval.
One writer Space; commit manifest last, validate exact bytes on every read.
"""
FILE_VERSION = "1.0.1"
DESCRIPTOR_VERSION = "1.0.0"  # Stable data format: upgrades must preserve approved asset IDs.

import hashlib
import io
import json
import os
import re
import tempfile
import threading
import urllib.request
from functools import lru_cache
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

OWNER = "Dezz-9-10"
BUCKET = OWNER + "/J.O.A.T.-Studio-storage"
OLD_BUCKET = OWNER + "/J.O.A.T.-Main-Assistant-Bot-storage"
OLD_ROOT = Path("/data/joat-studio")
WRITER_SPACE = OWNER + "/joat-reference-lab"
ROOT = Path("/studio/joat-studio")
LOCK = threading.Lock()
HEX = re.compile(r"[0-9a-f]{64}\Z")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
CHARACTER_REGISTRY_REVISION = "0a5a5f4895c2fa9ea613c32b77c338ad81e14bc2"
CHARACTER_REGISTRY_SHA256 = "76113fd3c143c9f62a735accad901e68ab4f383b4cbe590e06f2141f773f2ab5"
CHARACTER_REGISTRY_URL = ("https://huggingface.co/spaces/Dezz-9-10/J.O.A.T.-Character-Asset-Master/resolve/"
                          + CHARACTER_REGISTRY_REVISION + "/characters.json")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def fingerprint(value):
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False).encode())


def require_owner(profile):
    if profile is None or profile.username.casefold() != OWNER.casefold():
        raise ValueError("Sign in as Dezz-9-10.")


@lru_cache(maxsize=1)
def canonical_characters():
    try:
        with urllib.request.urlopen(CHARACTER_REGISTRY_URL, timeout=15) as response:
            raw = response.read(2 * 1024 * 1024)
        if digest(raw) != CHARACTER_REGISTRY_SHA256:
            raise ValueError("registry hash")
        return json.loads(raw)["characters"]
    except Exception:
        raise ValueError("Cannot verify the pinned Character Master registry. No identity binding was saved.") from None


def identity_binding(character_id, references):
    character = next((c for c in canonical_characters() if c["id"] == character_id), None)
    identity = references[0]
    if character is None:
        # A new character's owner-approved proposal may be retained, but production
        # requires separate canonical onboarding before a Director can use it.
        return {"status": "awaiting_canonical_character_registration",
                "character_id": character_id, "identity_source_sha256": identity["sha256"],
                "registry_revision": CHARACTER_REGISTRY_REVISION, "biometric_identity_verified": False}
    anchor = next((a for a in character["assets"] if "identity_anchor" in a["roles"]
                   and a["sha256"] == identity["sha256"]), None)
    if anchor is None:
        raise ValueError("Primary identity image is not this character's registered identity anchor.")
    return {"status": "canonical_source_hash_matched", "character_id": character_id,
            "identity_source_sha256": identity["sha256"], "identity_asset_id": anchor["asset_id"],
            "registry_revision": CHARACTER_REGISTRY_REVISION, "registry_sha256": CHARACTER_REGISTRY_SHA256,
            "biometric_identity_verified": False}


def require_mount(bucket, mount_path, write_required):
    """Require platform evidence, not an ordinary /data folder or temp fallback."""
    space = os.environ.get("SPACE_ID")
    if space != WRITER_SPACE:
        raise ValueError("Approved asset writer must run in " + WRITER_SPACE + ".")
    try:
        with urllib.request.urlopen("https://huggingface.co/api/spaces/" + space,
                                    timeout=15) as response:
            info = json.load(response)
    except Exception:
        raise ValueError("Cannot verify the configured Hugging Face bucket mount; nothing was saved.") from None
    mounts = info.get("runtime", {}).get("volumes") or []
    if not any(v.get("type") == "bucket" and v.get("source") == bucket
               and v.get("mountPath") == mount_path and (not write_required or v.get("readOnly") is False)
               for v in mounts) or not Path(mount_path).is_dir():
        raise ValueError("Mount " + bucket + " at " + mount_path + (" read/write" if write_required else "") + " first.")


def require_bucket():
    return require_mount(BUCKET, "/studio", True)


def require_old_bucket():
    return require_mount(OLD_BUCKET, "/data", False)


def read_json(path):
    p = Path(path or "")
    if not p.is_file() or p.stat().st_size > 1024 * 1024:
        raise ValueError("Upload a valid candidate review JSON under 1 MiB.")
    try:
        result = json.loads(p.read_text())
    except (ValueError, UnicodeError):
        raise ValueError("Candidate review is not valid JSON.") from None
    if not isinstance(result, dict):
        raise ValueError("Candidate review must be a JSON object.")
    return result


def candidate_evidence(image_path, report_path):
    p = Path(image_path or "")
    if not p.is_file() or p.stat().st_size > 25 * 1024 * 1024:
        raise ValueError("Upload the original candidate PNG under 25 MiB.")
    raw = p.read_bytes()
    report = read_json(report_path)
    if report.get("schema") != "joat.mission_reference_candidate.v1":
        raise ValueError("Use candidate_review.json, not a failure or production result.")
    if report.get("status") != "awaiting_independent_review":
        raise ValueError("Candidate status is not eligible for owner approval.")
    plan = report.get("plan")
    if not isinstance(plan, dict) or plan.get("schema") != "joat.mission_reference_plan.v1":
        raise ValueError("Missing candidate source plan.")
    # Gradio's JSON display can serialize the original 1.0 guidance as 1.
    # This normalization is allowed only if it restores the signed plan hash.
    plan = dict(plan)
    unsigned = {k: v for k, v in plan.items() if k != "fingerprint"}
    if fingerprint(unsigned) != plan.get("fingerprint"):
        if unsigned.get("guidance_scale") == 1:
            unsigned["guidance_scale"] = 1.0
        if fingerprint(unsigned) != plan.get("fingerprint"):
            raise ValueError("Candidate plan fingerprint mismatch.")
        plan = dict(unsigned, fingerprint=plan["fingerprint"])
    if not HEX.fullmatch(str(report.get("sha256", ""))) or digest(raw) != report["sha256"]:
        raise ValueError("PNG hash differs from candidate_review.json. Use the original downloaded PNG.")
    refs = plan.get("references")
    if not isinstance(refs, list) or not refs or refs[0].get("role") != "identity":
        raise ValueError("Candidate has no canonical identity source binding.")
    roles = {"identity", "second_same_character_identity", "environment", "wardrobe_support"}
    if len(refs) > 4 or len({r.get("role") for r in refs}) != len(refs):
        raise ValueError("Invalid reference role count.")
    for ref in refs:
        if ref.get("role") not in roles or not HEX.fullmatch(str(ref.get("sha256", ""))):
            raise ValueError("Invalid source reference hash or role.")
    with Image.open(io.BytesIO(raw)) as img:
        if img.format != "PNG" or img.width * img.height > 20_000_000:
            raise ValueError("Use the exact original candidate PNG, not a screenshot.")
        img.load()
        size = (img.width, img.height)
    if size != (report.get("width"), report.get("height")) or size != (plan.get("width"), plan.get("height")):
        raise ValueError("Candidate dimensions differ from its plan/review.")
    report = dict(report, plan=plan)
    return raw, report, plan


def prepare_asset(image, report, project, scene, shot, character, environment, style, wardrobe, purpose):
    raw, evidence, plan = candidate_evidence(image, report)
    ids = {"project_id": project, "scene_id": scene, "shot_id": shot,
           "character_id": character, "environment_id": environment}
    for key, value in ids.items():
        value = (value or "").strip()
        if not value and key == "environment_id":
            ids[key] = None
        elif not IDENTIFIER.fullmatch(value):
            raise ValueError("Enter a valid " + key + " (letters, numbers, dots, underscores or hyphens).")
        else:
            ids[key] = value
    scope = " / ".join(ids[k] for k in ("project_id", "scene_id", "shot_id"))
    if plan.get("mission") != scope:
        raise ValueError("Project / scene / shot must match the candidate's signed mission. Do not relabel an old job.")
    labels = {}
    for key, value in (("art_style", style), ("wardrobe", wardrobe), ("purpose", purpose)):
        value = (value or "").strip()
        if not value or len(value) > 500:
            raise ValueError("Describe " + key + " (1–500 characters).")
        labels[key] = value
    descriptor = {"schema": "joat.approved_job_reference_descriptor.v1", "file_version": DESCRIPTOR_VERSION,
                  "scope": ids, "labels": labels, "role": "shot_start_frame",
                  "canonical_identity_binding": identity_binding(ids["character_id"], plan["references"]),
                  "image_sha256": digest(raw), "width": evidence["width"], "height": evidence["height"],
                  "size_bytes": len(raw), "plan": plan, "candidate_review_sha256": fingerprint(evidence),
                  "canonical_registration": False, "production_qc_approved": False}
    descriptor["asset_id"] = fingerprint(descriptor)
    return descriptor


def write_once(path, raw):
    """No replace/rename requirement on the bucket filesystem; reject conflicting bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("Stored asset conflict; existing bytes were preserved.")
        return
    try:
        with path.open("xb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
    except FileExistsError:
        if path.read_bytes() != raw:
            raise ValueError("Concurrent asset conflict; nothing was overwritten.") from None
    if path.read_bytes() != raw:
        raise ValueError("Storage readback mismatch; asset is not committed.")


class AssetStore:
    def __init__(self, root=ROOT, validate_mount=require_bucket, bucket=BUCKET):
        self.root = Path(root)
        self.bucket = bucket
        self.validate_mount = validate_mount

    def check(self):
        self.validate_mount()
        return {"schema": "joat.asset_storage_check.v1", "file_version": FILE_VERSION,
                "status": "mount_configuration_verified", "bucket": BUCKET,
                "namespace": "joat-studio", "mount_path": "/studio", "gpu_called": False,
                "note": "Approval/save and readback must still succeed; no files were written by this check."}

    def claim_attempt(self, plan):
        unsigned = {k: v for k, v in plan.items() if k != "fingerprint"}
        if not HEX.fullmatch(str(plan.get("fingerprint", ""))) or fingerprint(unsigned) != plan["fingerprint"]:
            raise ValueError("Plan fingerprint mismatch.")
        self.validate_mount()
        p = self.root / "generation-attempts" / (plan["fingerprint"] + ".json")
        p.parent.mkdir(parents=True, exist_ok=True)
        with LOCK:
            try:
                with p.open("x") as f:
                    json.dump({"schema": "joat.reference_attempt.v1", "file_version": FILE_VERSION,
                               "status": "submitted_or_uncertain", "fingerprint": plan["fingerprint"],
                               "automatic_retry": False}, f)
                    f.flush()
                    os.fsync(f.fileno())
            except FileExistsError:
                raise ValueError("This exact plan was already attempted. No duplicate GPU request was sent.") from None
        if json.loads(p.read_text()).get("fingerprint") != plan["fingerprint"]:
            raise ValueError("Attempt storage readback failed; no GPU request was sent.")
        return p

    def approve(self, descriptor, image, report, profile, approved):
        require_owner(profile)
        if approved is not True:
            raise ValueError("Review the exact image and confirm approval before saving.")
        scope, labels = descriptor["scope"], descriptor["labels"]
        actual = prepare_asset(image, report, scope["project_id"], scope["scene_id"], scope["shot_id"],
                               scope["character_id"], scope["environment_id"], labels["art_style"],
                               labels["wardrobe"], labels["purpose"])
        if actual != descriptor:
            raise ValueError("Approval inputs changed. Prepare the save preview again.")
        self.validate_mount()
        raw, evidence, _ = candidate_evidence(image, report)
        folder = self.root / "approved-references" / descriptor["asset_id"]
        with LOCK:
            if (folder / "manifest.json").exists():
                manifest = self.load(descriptor["asset_id"])
                if manifest["descriptor"] != descriptor:
                    raise ValueError("Stored descriptor conflict.")
                return manifest
            write_once(folder / "image.png", raw)
            write_once(folder / "candidate_review.json", json.dumps(evidence, sort_keys=True,
                       separators=(",", ":"), ensure_ascii=False).encode())
            manifest = {"schema": "joat.approved_job_reference.v1", "file_version": FILE_VERSION,
                        "asset_id": descriptor["asset_id"], "descriptor": descriptor,
                        "owner_approval": {"owner": profile.username, "approved_at": datetime.now(timezone.utc).isoformat(),
                                           "kind": "visual_job_reference", "descriptor_fingerprint": descriptor["asset_id"]},
                        "image_uri": "hf://buckets/" + self.bucket + "/joat-studio/approved-references/" + descriptor["asset_id"] + "/image.png",
                        "canonical_registration": False, "production_qc_approved": False}
            manifest["fingerprint"] = fingerprint(manifest)
            write_once(folder / "manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False).encode())
            return self.load(descriptor["asset_id"])

    def load(self, asset_id, expected_scope=None):
        self.validate_mount()
        if not HEX.fullmatch(str(asset_id)):
            raise ValueError("Invalid approved asset identifier.")
        folder = self.root / "approved-references" / asset_id
        manifest = read_json(folder / "manifest.json")
        unsigned = {k: v for k, v in manifest.items() if k != "fingerprint"}
        descriptor = manifest.get("descriptor", {})
        if (manifest.get("schema") != "joat.approved_job_reference.v1"
                or fingerprint(unsigned) != manifest.get("fingerprint")
                or descriptor.get("asset_id") != asset_id
                or fingerprint({k: v for k, v in descriptor.items() if k != "asset_id"}) != asset_id
                or manifest.get("owner_approval", {}).get("owner", "").casefold() != OWNER.casefold()
                or manifest["owner_approval"].get("descriptor_fingerprint") != asset_id):
            raise ValueError("Approved manifest integrity/owner binding failed.")
        expected_uri = "hf://buckets/" + self.bucket + "/joat-studio/approved-references/" + asset_id + "/image.png"
        if manifest.get("image_uri") != expected_uri:
            raise ValueError("Manifest bucket location does not match this storage.")
        scope, labels = descriptor["scope"], descriptor["labels"]
        if expected_scope is not None and scope != expected_scope:
            raise ValueError("Approved reference belongs to a different job or character.")
        actual = prepare_asset(folder / "image.png", folder / "candidate_review.json",
                               scope["project_id"], scope["scene_id"], scope["shot_id"],
                               scope["character_id"], scope["environment_id"], labels["art_style"],
                               labels["wardrobe"], labels["purpose"])
        actual["file_version"] = descriptor["file_version"]
        actual["asset_id"] = fingerprint({k: v for k, v in actual.items() if k != "asset_id"})
        if actual != descriptor:
            raise ValueError("Stored image or evidence differs from the approved descriptor.")
        return manifest


def export_manifest(manifest):
    # Only this selected manifest reaches Gradio's temp cache; never allow all /data.
    folder = Path(tempfile.mkdtemp(prefix="joat-approved-reference-"))
    p = folder / "approved_job_reference.json"
    p.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return str(p)


def migrate_studio(expected, profile, confirmed, source=None, destination=None):
    """Owner-triggered copy; originals and approval descriptors remain untouched."""
    require_owner(profile)
    if confirmed is not True:
        raise ValueError("Confirm copying the existing studio records to the dedicated bucket.")
    source = source or AssetStore(OLD_ROOT, require_old_bucket, OLD_BUCKET)
    destination = destination or AssetStore()
    if source.bucket != OLD_BUCKET or destination.bucket != BUCKET or source.root.resolve() == destination.root.resolve():
        raise ValueError("Migration must copy from the old assistant bucket to the dedicated studio bucket.")
    source.validate_mount()
    destination.validate_mount()
    if expected.get("schema") != "joat.approved_job_reference.v1":
        raise ValueError("Upload approved_job_reference.json for migration, not candidate_review.json or a preview.")
    retained = source.load(expected.get("asset_id"))
    if retained != expected:
        raise ValueError("Uploaded approval record differs from the stored source record.")
    approved = source.root / "approved-references"
    records = []
    for folder in sorted(approved.iterdir()):
        if folder.is_symlink() or not folder.is_dir() or not HEX.fullmatch(folder.name):
            raise ValueError("Unexpected approved-reference entry; no unrecognized files will be migrated.")
        if not (folder / "manifest.json").is_file():
            raise ValueError("An incomplete approved-reference entry needs diagnosis before migration.")
        for name in ("image.png", "candidate_review.json", "manifest.json"):
            if (folder / name).is_symlink():
                raise ValueError("Symbolic-link source files are not allowed.")
        records.append(source.load(folder.name))
        if len(records) > 1000:
            raise ValueError("Migration exceeds the 1000-record safety limit.")
    attempts = []
    attempt_root = source.root / "generation-attempts"
    if attempt_root.exists():
        for path in sorted(attempt_root.iterdir()):
            if path.is_symlink() or not path.is_file() or path.suffix != ".json" or not HEX.fullmatch(path.stem):
                raise ValueError("Unrecognized generation-attempt entry.")
            if path.stat().st_size > 1024 * 1024:
                raise ValueError("Generation-attempt record exceeds 1 MiB.")
            json.loads(path.read_text())
            attempts.append(path)
            if len(attempts) > 1000:
                raise ValueError("Migration exceeds the 1000-attempt limit.")
    migrated = []
    with LOCK:
        # Claims first: copied assets must never enable an accidental GPU resubmission.
        for path in attempts:
            write_once(destination.root / "generation-attempts" / path.name, path.read_bytes())
        for record in records:
            asset_id = record["asset_id"]
            src = source.root / "approved-references" / asset_id
            dst = destination.root / "approved-references" / asset_id
            migrated_record = dict(record)
            migrated_record.update(file_version=FILE_VERSION,
                image_uri="hf://buckets/" + destination.bucket + "/joat-studio/approved-references/" + asset_id + "/image.png",
                storage_migration={"source_bucket": source.bucket, "source_manifest_fingerprint": record["fingerprint"],
                                   "authorized_by": profile.username, "original_approval_preserved": True})
            migrated_record.pop("fingerprint", None)
            migrated_record["fingerprint"] = fingerprint(migrated_record)
            write_once(dst / "image.png", (src / "image.png").read_bytes())
            write_once(dst / "candidate_review.json", (src / "candidate_review.json").read_bytes())
            write_once(dst / "manifest.json", json.dumps(migrated_record, indent=2, ensure_ascii=False).encode())
            verified = destination.load(asset_id)
            if verified != migrated_record or verified["descriptor"] != record["descriptor"] or verified["owner_approval"] != record["owner_approval"]:
                raise ValueError("Destination approval/readback differs; source was retained.")
            migrated.append(verified)
    result = {"schema": "joat.studio_storage_migration.v1", "file_version": FILE_VERSION,
              "status": "copied_and_readback_verified", "source_bucket": source.bucket,
              "destination_bucket": destination.bucket, "destination_mount": "/studio",
              "approved_reference_count": len(migrated), "attempt_records_copied": len(attempts),
              "original_approvals_preserved": True, "source_deleted": False,
              "main_assistant_private_data_copied": False, "gpu_called": False,
              "selected_approved_reference": next(r for r in migrated if r["asset_id"] == expected["asset_id"]),
              "note": "Destination restart/readback remains to be verified; other bots require their own storage routing integration."}
    return result


def add_storage_migration_ui():
    import gradio as gr
    with gr.Tab("Studio Storage Migration"):
        gr.Markdown("### Studio storage migration v1.0.1\nCopy only studio-approved references and generation-attempt records "
                    "to the dedicated bucket. Original approval and image bytes are preserved; old copies remain. No GPU is called.")
        gr.LoginButton()
        receipt = gr.File(label="Existing approved_job_reference.json — saved approval, not candidate review",
                          file_types=[".json"], type="filepath")
        confirmed = gr.Checkbox(label="Authorize copying the existing studio records to J.O.A.T.-Studio-storage")
        result = gr.JSON(label="Studio migration result")
        export = gr.File(label="Download studio_storage_migration.json")

        def copy_studio(path, approval, profile: gr.OAuthProfile | None):
            try:
                require_owner(profile)
                outcome = migrate_studio(read_json(path), profile, approval)
                folder = Path(tempfile.mkdtemp(prefix="joat-storage-migration-"))
                file = folder / "studio_storage_migration.json"
                file.write_text(json.dumps(outcome, indent=2, ensure_ascii=False))
                return outcome, str(file), False
            except Exception as exc:
                raise gr.Error(str(exc)) from None

        gr.Button("Copy studio records and verify (no GPU)").click(
            copy_studio, [receipt, confirmed], [result, export, confirmed],
            api_visibility="private", concurrency_limit=1)
        receipt.change(lambda: (False, None, None), outputs=[confirmed, result, export], api_visibility="private")


def add_approved_assets_ui():
    import gradio as gr
    store = AssetStore()
    with gr.Tab("Approved Job References"):
        gr.Markdown("### Approved job references v1.0.1\nImport an existing candidate or the PNG/JSON from the Mission tab. "
                    "Review once, approve and save automatically to studio storage. No GPU is called. "
                    "This does not replace canonical identity or approve a production video.")
        gr.LoginButton()
        status = gr.JSON(label="Storage and saved-reference result")
        image = gr.File(label="Original candidate PNG — not a screenshot", file_types=[".png"], type="filepath")
        report = gr.File(label="candidate_review.json", file_types=[".json"], type="filepath")
        project = gr.Textbox(label="Project ID from candidate plan", value="PROJECT-001")
        scene = gr.Textbox(label="Scene ID", value="SCENE-001")
        shot = gr.Textbox(label="Shot ID", value="SHOT-001")
        character = gr.Textbox(label="Character ID", value="CHAR-001")
        environment = gr.Textbox(label="Environment ID (optional)", value="ENV-001")
        style = gr.Textbox(label="Approved art style", value="Stylized 3D, matching supplied references")
        wardrobe = gr.Textbox(label="Approved wardrobe", value="Black blazer over black shirt; sunglasses and accessories")
        purpose = gr.Textbox(label="Job purpose", value="Approved Founder office opening frame")
        state = gr.State(None)
        preview = gr.JSON(label="Exact save preview — verify character, scope, image hash and source references")
        approval = gr.Checkbox(label="I approve this exact image, identity, scene, style and wardrobe for this job")
        exported = gr.File(label="Download approved_job_reference.json")

        def check_storage(profile: gr.OAuthProfile | None):
            try:
                require_owner(profile)
                return store.check()
            except Exception as exc:
                raise gr.Error(str(exc)) from None

        def preview_save(*args, profile: gr.OAuthProfile | None):
            try:
                require_owner(profile)
                descriptor = prepare_asset(*args)
                return descriptor, descriptor, False, None, None
            except Exception as exc:
                raise gr.Error(str(exc)) from None

        # Explicit argument signatures let Gradio inject the OAuth profile correctly.
        def prepare_save(i, r, p, s, h, c, e, a, w, u, profile: gr.OAuthProfile | None):
            return preview_save(i, r, p, s, h, c, e, a, w, u, profile=profile)

        def approve_save(descriptor, i, r, p, s, h, c, e, a, w, u, confirmed,
                         profile: gr.OAuthProfile | None):
            try:
                require_owner(profile)
                if not descriptor or prepare_asset(i, r, p, s, h, c, e, a, w, u) != descriptor:
                    raise ValueError("Prepare the exact save preview first; inputs must remain unchanged.")
                manifest = store.approve(descriptor, i, r, profile, confirmed)
                return manifest, export_manifest(manifest), False
            except Exception as exc:
                raise gr.Error(str(exc)) from None

        inputs = [image, report, project, scene, shot, character, environment, style, wardrobe, purpose]
        gr.Button("Check studio storage (no GPU)").click(check_storage, [], status, api_visibility="private")
        gr.Button("Prepare approval/save preview (no GPU)").click(
            prepare_save, inputs, [state, preview, approval, exported, status], api_visibility="private")
        gr.Button("Approve and save this exact reference (no GPU)").click(
            approve_save, [state] + inputs + [approval], [status, exported, approval],
            api_visibility="private", concurrency_limit=1)
        for component in inputs:
            component.change(lambda: (None, None, False, None, None),
                             outputs=[state, preview, approval, exported, status], api_visibility="private")
    add_storage_migration_ui()
