"""J.O.A.T. GPU workload and reservation contract; joat_gpu_contract.py v1.0.0.

Pure CPU arithmetic only. Reservations describe the local request, not a
provider entitlement, successful GPU allocation, or completed generation.
No prompts, asset paths, URLs, tokens, or image bytes enter diagnostics.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping

FILE_VERSION = "1.0.0"
CONTRACT_MAX_SECONDS = 600
FPS = 24
TEMPORAL_COMPRESSION = 8
SPATIAL_COMPRESSION = 32
_MSR = "multi-reference (MSR)"
_ORIGINAL_MSR = "multi-reference (original)"


def _finite_number(value, name):
    if isinstance(value, bool):
        raise ValueError(name + " must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(name + " must be a finite number") from None
    if not math.isfinite(result):
        raise ValueError(name + " must be a finite number")
    return result


def _integer(value, name, lower, upper):
    result = _finite_number(value, name)
    if result != math.floor(result) or not lower <= result <= upper:
        raise ValueError(f"{name} must be an integer from {lower} to {upper}")
    return int(result)


def _grid_frames(seconds):
    # Match the renderer's _safe_frames exactly; requested duration is retained.
    frames = max(9, int(seconds * FPS) + 1)
    return ((frames - 1 + 7) // 8) * 8 + 1


def _version(value, name):
    if not isinstance(value, str) or not value or len(value) > 64:
        raise ValueError(name + " must be a nonempty version string")
    if any(character not in "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ._-" for character in value):
        raise ValueError(name + " contains invalid version characters")
    return value


def _safe_mode(value):
    # Never copy arbitrary input text into public diagnostics/signatures.
    return value if value in (_MSR, _ORIGINAL_MSR, "single image (i2v)") else "other"


def _legacy_msr_image_guides(parameters):
    """Expected current graph count; caller may supply the built graph count."""
    refs = [parameters.get("msr_ref2"), parameters.get("msr_ref3"), parameters.get("msr_ref4")]
    count = 1 + sum(bool(value) for value in refs) + bool(parameters.get("msr_background"))
    identity = parameters.get("identity_ref_image")
    # Current renderer writes an identity image under a fresh name and inserts
    # it into a free slot unless it equals an existing supporting reference.
    if identity and identity not in refs:
        if all(refs):
            raise ValueError("MSR identity reference has no free supporting reference slot")
        count += 1
    return int(count)


def profile(parameters, *, app_version, msr_version, width, height,
            image_guide_count=None, guide_frame_count=None):
    """Describe the expected executed graph using safe scalars and a stable hash.

    width/height must be the actual base-generation dimensions. When provided,
    image_guide_count is the number of image guides in the built graph after
    reference-slot assignment, making deduplication explicit. Latent site
    counts are expected VAE-grid sizes, not measured transformer tokens/VRAM.
    """
    if not isinstance(parameters, Mapping):
        raise ValueError("GPU parameters must be a mapping")
    seconds = _finite_number(parameters.get("seconds"), "requested duration")
    if not 0 < seconds <= 40:
        raise ValueError("Requested duration must be greater than zero and at most 40 seconds")
    width = _integer(width, "generation width", 32, 8192)
    height = _integer(height, "generation height", 32, 8192)
    if width % SPATIAL_COMPRESSION or height % SPATIAL_COMPRESSION:
        raise ValueError("Generation dimensions must be multiples of 32")
    mode = _safe_mode(parameters.get("input_mode"))
    full_msr = mode == _MSR
    any_msr = mode in (_MSR, _ORIGINAL_MSR)
    base_frames = _grid_frames(seconds)
    if base_frames > 1001:
        raise ValueError("Requested generated frame count exceeds the supported 1001 frames")
    base_latents = (base_frames - 1) // TEMPORAL_COMPRESSION + 1
    if any_msr:
        guide_frames = _integer(parameters.get("msr_frame_count", 41) if guide_frame_count is None else guide_frame_count,
                                "MSR pseudo-video frame count", 9, 1001)
        if (guide_frames - 1) % TEMPORAL_COMPRESSION:
            raise ValueError("MSR pseudo-video frame count must lie on the 8n+1 grid")
        guides = (_legacy_msr_image_guides(parameters) if full_msr else 0) if image_guide_count is None else image_guide_count
        guides = _integer(guides, "MSR image guide count", 0, 5)
        pseudo_latents = (guide_frames - 1) // TEMPORAL_COMPRESSION + 1
    else:
        if image_guide_count not in (None, 0) or guide_frame_count not in (None, 0):
            raise ValueError("MSR guide counts cannot be attached to a non-MSR profile")
        guide_frames, guides, pseudo_latents = 0, 0, 0
    effective_skip_refine = full_msr or bool(parameters.get("skip_refine"))
    sigma_steps = 0
    if not effective_skip_refine:
        sigma_steps = sum(_finite_number(term.strip(), "refine sigma") > 0
                          for term in str(parameters.get("sigma_string") or "0.4824,0.2412,0.0").split(",")
                          if term.strip())
    sites_per_frame = width // SPATIAL_COMPRESSION * (height // SPATIAL_COMPRESSION)
    expected_total = base_latents + pseudo_latents + guides
    workload = {
        "gpu_contract_version": FILE_VERSION,
        "app_version": _version(app_version, "app version"),
        "msr_runtime_version": _version(msr_version, "MSR runtime version"),
        "input_mode": mode,
        "requested_duration_seconds": seconds,
        "output_fps": FPS,
        "generation_width": width,
        "generation_height": height,
        "output_width": width,
        "output_height": height,
        "generated_pixel_frames": base_frames,
        "base_video_latent_frames": base_latents,
        "msr_pseudo_video_pixel_frames": guide_frames,
        "msr_pseudo_video_latent_frames": pseudo_latents,
        "msr_image_guide_latent_frames": guides,
        "expected_sampled_video_latent_frames": expected_total,
        "spatial_latent_width": width // SPATIAL_COMPRESSION,
        "spatial_latent_height": height // SPATIAL_COMPRESSION,
        "base_video_latent_sites": base_latents * sites_per_frame,
        "expected_sampled_video_latent_sites": expected_total * sites_per_frame,
        "effective_skip_refine": effective_skip_refine,
        "refine_positive_sigma_terms": sigma_steps,
        "anchor_only": parameters.get("mode") == "anchor only",
        "user_lora_count": sum(bool(line.strip()) for line in str(parameters.get("user_loras_text") or "").splitlines()),
        "motion_control_active": bool(parameters.get("motion_control_type") not in (None, "", "off") and
                                      (parameters.get("motion_video") or parameters.get("motion_prepared"))),
        "audio_reference_active": bool(parameters.get("audio_ref_enabled")),
        "kv_enabled": bool(parameters.get("kv_enabled")),
        "prompt_relay_enabled": bool(parameters.get("prompt_relay_enabled")),
        "scene_chain_enabled": bool(parameters.get("scene_chain_enabled")),
        "last_keyframe_active": bool(parameters.get("kf_last_image")),
        "mid_keyframes_active": bool(parameters.get("kf_mid_enabled")),
        "shape_basis": "expected_graph_vae_grid_not_measured_transformer_tokens",
    }
    canonical = json.dumps(workload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return {"schema": "joat.gpu_workload.v1", "signature": hashlib.sha256(canonical.encode()).hexdigest(),
            "workload": workload}


def estimate_budget(profile, samples, min=45, max=600, manual=0):
    """Reserve local GPU time without changing creative or output parameters.

    Matching samples must explicitly record successful GPU completion:
    {"signature": profile["signature"], "status": "success", "gpu_seconds":N}.
    A calibrated requirement exceeding the ceiling blocks submission. Cold
    full-MSR reserves the configured ceiling while permission remains unknown.
    """
    minimum = _integer(min, "minimum GPU reservation", 1, CONTRACT_MAX_SECONDS)
    maximum = _integer(max, "maximum GPU reservation", minimum, CONTRACT_MAX_SECONDS)
    if not isinstance(profile, Mapping) or profile.get("schema") != "joat.gpu_workload.v1":
        raise ValueError("A valid GPU workload profile is required")
    workload = profile.get("workload")
    if not isinstance(workload, Mapping):
        raise ValueError("A valid GPU workload profile is required")
    canonical = json.dumps(dict(workload), sort_keys=True, separators=(",", ":"), allow_nan=False)
    if hashlib.sha256(canonical.encode()).hexdigest() != profile.get("signature"):
        raise ValueError("GPU workload signature mismatch")
    override = _finite_number(0 if manual is None else manual, "manual GPU reservation")
    if override != 0:
        override = _integer(override, "manual GPU reservation", minimum, maximum)
    accepted = []
    for sample in samples or ():
        if not isinstance(sample, Mapping) or sample.get("signature") != profile["signature"] or sample.get("status") != "success":
            continue
        try:
            measured = _finite_number(sample.get("gpu_seconds"), "successful GPU seconds")
        except ValueError:
            continue
        if measured > 0:
            accepted.append(measured)
    accepted = accepted[-20:]
    result = {
        "schema": "joat.gpu_reservation.v1", "file_version": FILE_VERSION,
        "workload_signature": profile["signature"],
        "matching_success_samples": len(accepted),
        "configured_minimum_seconds": minimum, "configured_maximum_seconds": maximum,
        "owner_gpu_approval_required": True,
        "provider_permission_unverified": True,
        "gpu_called": False,
    }
    calibrated = None
    if len(accepted) >= 3:
        ordered = sorted(accepted)
        calibrated = math.ceil(ordered[math.ceil(.9 * len(ordered)) - 1] * 1.20 + 8)
        result["calibrated_requirement_seconds"] = calibrated
    if calibrated is not None and (calibrated > maximum or (override and override < calibrated)):
        result.update(status="requires_owner_decision", budget_seconds=None,
                      policy="calibrated_requirement_blocks_undersized_reservation",
                      uncapped_estimate_seconds=calibrated,
                      manual_requested_seconds=override or None,
                      reason=("Estimated GPU requirement exceeds configured reservation ceiling" if calibrated > maximum else
                              "Manual GPU reservation is below the calibrated requirement"))
        return result
    if override:
        estimate, policy = override, "explicit_manual_reservation"
    elif calibrated is not None:
        estimate = calibrated
        policy = "same_signature_success_p90_margin20_percent_plus8_seconds"
    elif workload["input_mode"] == _MSR:
        estimate, policy = maximum, "uncalibrated_full_msr_configured_ceiling"
    else:
        normalized = workload["generated_pixel_frames"] * workload["generation_width"] * workload["generation_height"] / (25 * 512 * 640)
        cost = 1.0 if workload["anchor_only"] else 1.10
        if workload["motion_control_active"]:
            cost *= 1.85
        if not workload["effective_skip_refine"]:
            cost *= 1 + .20 * workload["refine_positive_sigma_terms"]
        tight = 30 + int(5 * normalized * cost)
        estimate = tight if tight <= 120 else minimum + int(8 * normalized * cost)
        policy = "uncalibrated_existing_non_msr_bootstrap"
    result.update(policy=policy, uncapped_estimate_seconds=estimate)
    if estimate > maximum:
        result.update(status="requires_owner_decision", budget_seconds=None,
                      reason="Estimated GPU requirement exceeds configured reservation ceiling")
    else:
        result.update(status="ready", budget_seconds=minimum if estimate < minimum else estimate)
    return result
