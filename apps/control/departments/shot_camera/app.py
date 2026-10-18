"""
J.O.A.T. Shot & Camera Master v1.0.1

Roadmap Stage #4

Purpose:
- Consume Director / Character / Environment production intent
- Convert scene intent into deterministic shot/camera instructions
- Own shot size, camera angle, movement, composition, focus, duration
- Preserve character and environment continuity
- Prevent unsupported camera/shot drift
- Produce joat.shot_camera_packet.v1
- Hand generation-ready camera instructions downstream to LTX
- Never mutate Character, Environment, or Director masters
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Optional

import gradio as gr


# =============================================================================
# CONFIG
# =============================================================================

APP_VERSION = "1.0.1"
PACKET_SCHEMA = "joat.shot_camera_packet.v1"
ACCEPTANCE_TEST_VERSION = "1.0.0"

SHOT_SIZES = [
    "extreme_wide",
    "wide",
    "full",
    "medium_wide",
    "medium",
    "medium_close_up",
    "close_up",
    "extreme_close_up",
    "insert",
]

CAMERA_ANGLES = [
    "eye_level",
    "high_angle",
    "low_angle",
    "overhead",
    "birds_eye",
    "worms_eye",
    "dutch_angle",
    "over_the_shoulder",
    "point_of_view",
]

CAMERA_MOVEMENTS = [
    "static",
    "pan_left",
    "pan_right",
    "tilt_up",
    "tilt_down",
    "push_in",
    "pull_out",
    "dolly_in",
    "dolly_out",
    "truck_left",
    "truck_right",
    "pedestal_up",
    "pedestal_down",
    "orbit_left",
    "orbit_right",
    "crane_up",
    "crane_down",
    "handheld",
    "steadicam",
    "tracking",
]

FOCUS_MODES = [
    "deep_focus",
    "shallow_focus",
    "subject_focus",
    "rack_focus",
    "environment_focus",
    "director_defined",
]

COMPOSITION_MODES = [
    "centered",
    "rule_of_thirds",
    "symmetrical",
    "leading_lines",
    "negative_space",
    "foreground_frame",
    "layered_depth",
    "director_defined",
]


# =============================================================================
# HELPERS
# =============================================================================

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_json(
    raw: Any,
    default: Any,
    expected_type: Optional[type] = None,
) -> Any:
    if raw is None:
        return deepcopy(default)

    if isinstance(raw, (dict, list)):
        value = deepcopy(raw)
    else:
        text = str(raw).strip()

        if not text:
            return deepcopy(default)

        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}") from exc

    if expected_type is not None and not isinstance(value, expected_type):
        raise ValueError(
            f"Expected {expected_type.__name__}, "
            f"received {type(value).__name__}"
        )

    return value


def normalize_duration(value: Any) -> float:
    try:
        duration = float(value)
    except (TypeError, ValueError):
        raise ValueError("Duration must be a number of seconds.")

    if duration <= 0:
        raise ValueError("Duration must be greater than zero.")

    return round(duration, 3)


def ensure_choice(
    value: str,
    allowed: list[str],
    field_name: str,
) -> str:
    if value not in allowed:
        raise ValueError(
            f"Unsupported {field_name}: {value!r}. "
            f"Allowed values: {allowed}"
        )
    return value


def packet_fingerprint(packet: dict[str, Any]) -> str:
    fingerprint_source = deepcopy(packet)
    fingerprint_source.pop("packet_fingerprint", None)
    fingerprint_source.pop("created_at", None)

    return sha256_text(stable_json(fingerprint_source))


# =============================================================================
# INPUT VALIDATION
# =============================================================================

def validate_character_packet(
    packet: dict[str, Any],
) -> tuple[bool, list[str]]:
    errors: list[str] = []

    if packet.get("schema") != "joat.character_packet.v1":
        errors.append("Unsupported character packet schema.")

    if not packet.get("character_id"):
        errors.append("Missing character_id.")

    if packet.get("identity_locked") is not True:
        errors.append("Character identity is not locked.")

    approval = packet.get("approval", {})

    if approval.get("live_change_allowed") is not False:
        errors.append(
            "Character packet live_change_allowed must be False."
        )

    if approval.get(
        "requires_human_approval_for_registry_mutation"
    ) is not True:
        errors.append(
            "Character registry mutation approval gate is missing."
        )

    return len(errors) == 0, errors


def validate_environment_packet(
    packet: dict[str, Any],
) -> tuple[bool, list[str]]:
    errors: list[str] = []

    if packet.get("schema") != "joat.environment_packet.v1":
        errors.append("Unsupported environment packet schema.")

    if not packet.get("environment_id"):
        errors.append("Missing environment_id.")

    if packet.get("environment_locked") is not True:
        errors.append("Environment is not locked.")

    if packet.get("asset_identity_lock_ready") is not True:
        errors.append(
            "Environment image identity lock is not production-ready."
        )

    approval = packet.get("approval", {})

    if approval.get("live_change_allowed") is not False:
        errors.append(
            "Environment packet live_change_allowed must be False."
        )

    if approval.get(
        "requires_human_approval_for_registry_mutation"
    ) is not True:
        errors.append(
            "Environment registry mutation approval gate is missing."
        )

    return len(errors) == 0, errors


def validate_director_packet(
    packet: dict[str, Any],
) -> tuple[bool, list[str]]:
    errors: list[str] = []

    if packet.get("schema") != "joat.director_packet.v1":
        errors.append("Unsupported Director packet schema.")

    if not packet.get("project_id"):
        errors.append("Missing Director project_id.")

    if "creative_brief" not in packet:
        errors.append("Missing Director creative_brief.")

    if "per_shot" not in packet:
        errors.append("Missing Director per_shot instructions.")

    return len(errors) == 0, errors


# =============================================================================
# SHOT / CAMERA MASTER
# =============================================================================


def director_approved_camera_lock(packet, director, character):
    """Derive a camera lock only from matching, explicitly owner-approved intent."""
    approval = director.get("approval", {}) if isinstance(director, dict) else {}
    if approval.get("creative_intent_locked") is not True:
        return None  # Legacy unapproved planning packets retain their original behavior.
    if approval.get("approved_by") != "Dezz-9-10":
        raise ValueError("Camera lock requires the studio owner's Director approval.")
    core = deepcopy(director)
    expected = core.pop("packet_fingerprint", None)
    if expected != sha256_text(stable_json(core)):
        raise ValueError("Approved Director fingerprint mismatch.")
    reviewed = deepcopy(core)
    reviewed.pop("approval", None)
    if approval.get("reviewed_draft_sha256") != sha256_text(stable_json(reviewed)):
        raise ValueError("Director reviewed draft mismatch.")
    if approval.get("character_packet_sha256") != sha256_text(stable_json(character)):
        raise ValueError("Director approval belongs to another Character packet.")
    shots = [shot for shot in director.get("per_shot", [])
             if shot.get("shot_id") == packet["shot_id"] and shot.get("scene_id") == packet["scene_id"]]
    if len(shots) != 1 or director.get("project_id") != packet["project_id"]:
        raise ValueError("Camera project/scene/shot differs from approved Director.")
    shot = shots[0]
    camera = shot.get("camera_framing", {})
    normalize = lambda value: str(value).strip().lower().replace("-", "_")
    for target, origin in [("shot_size", "framing"), ("angle", "angle"), ("movement", "movement")]:
        if not camera.get(origin) or normalize(packet["camera"][target]) != normalize(camera[origin]):
            raise ValueError("Camera decisions differ from approved Director: " + target)
    for key in ("composition", "focus_mode", "lens_guidance", "depth_guidance"):
        if key in camera and packet["camera"][key] != camera[key]:
            raise ValueError("Camera decisions differ from approved Director: " + key)
    duration = shot.get("duration", director.get("duration", ""))
    parts = str(duration).split(":")
    if len(parts) not in (2, 3):
        raise ValueError("Approved Director duration must be MM:SS or HH:MM:SS.")
    seconds = sum(float(value) * 60 ** index for index, value in enumerate(reversed(parts)))
    if float(packet["timing"]["duration_seconds"]) != seconds:
        raise ValueError("Camera duration differs from approved Director.")
    if packet["performance_context"]["action"] != shot.get("performance_action", {}).get("action"):
        raise ValueError("Camera action context differs from approved Director.")
    return {"basis": "matching_owner_approved_director",
            "approved_by": approval["approved_by"],
            "director_packet_fingerprint": expected,
            "reviewed_draft_sha256": approval["reviewed_draft_sha256"],
            "character_packet_sha256": approval["character_packet_sha256"]}


class ShotCameraMaster:

    def build_packet(
        self,
        project_id: str,
        scene_id: str,
        shot_id: str,
        shot_purpose: str,
        shot_size: str,
        camera_angle: str,
        camera_movement: str,
        composition: str,
        focus_mode: str,
        duration_seconds: float,
        subject: str,
        action: str,
        lens_guidance: str,
        depth_guidance: str,
        transition_in: str,
        transition_out: str,
        character_packet: Optional[dict[str, Any]] = None,
        environment_packet: Optional[dict[str, Any]] = None,
        director_packet: Optional[dict[str, Any]] = None,
        previous_shot_packet: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:

        if not project_id.strip():
            raise ValueError("project_id is required.")

        if not scene_id.strip():
            raise ValueError("scene_id is required.")

        if not shot_id.strip():
            raise ValueError("shot_id is required.")

        shot_size = ensure_choice(
            shot_size,
            SHOT_SIZES,
            "shot size",
        )

        camera_angle = ensure_choice(
            camera_angle,
            CAMERA_ANGLES,
            "camera angle",
        )

        camera_movement = ensure_choice(
            camera_movement,
            CAMERA_MOVEMENTS,
            "camera movement",
        )

        composition = ensure_choice(
            composition,
            COMPOSITION_MODES,
            "composition",
        )

        focus_mode = ensure_choice(
            focus_mode,
            FOCUS_MODES,
            "focus mode",
        )

        duration_seconds = normalize_duration(duration_seconds)

        character_ref = None
        environment_ref = None
        director_ref = None

        if character_packet:
            valid, errors = validate_character_packet(character_packet)
            if not valid:
                raise ValueError(
                    "Character packet rejected: "
                    + "; ".join(errors)
                )

            character_ref = {
                "schema": character_packet.get("schema"),
                "character_id": character_packet.get("character_id"),
                "character_name": character_packet.get("character_name"),
                "character_version": character_packet.get(
                    "character_version"
                ),
                "identity_locked": True,
                "identity_lock_asset": character_packet.get(
                    "identity_lock_asset"
                ),
                "supporting_reference_assets": deepcopy(
                    character_packet.get(
                        "supporting_reference_assets",
                        [],
                    )
                ),
                "appearance_rules": deepcopy(
                    character_packet.get("appearance_rules")
                ),
                "continuity_rules": deepcopy(
                    character_packet.get("continuity_rules", [])
                ),
                "negative_rules": deepcopy(
                    character_packet.get("negative_rules", [])
                ),
                "source_asset_hashes": deepcopy(
                    character_packet.get("source_asset_hashes", {})
                ),
            }

        if environment_packet:
            valid, errors = validate_environment_packet(
                environment_packet
            )

            if not valid:
                raise ValueError(
                    "Environment packet rejected: "
                    + "; ".join(errors)
                )

            environment_ref = {
                "schema": environment_packet.get("schema"),
                "environment_id": environment_packet.get(
                    "environment_id"
                ),
                "environment_name": environment_packet.get(
                    "environment_name"
                ),
                "environment_version": environment_packet.get(
                    "environment_version"
                ),
                "environment_locked": True,
                "asset_identity_lock_ready": True,
                "identity_lock_asset": environment_packet.get(
                    "identity_lock_asset"
                ),
                "supporting_reference_assets": deepcopy(
                    environment_packet.get(
                        "supporting_reference_assets",
                        [],
                    )
                ),
                "environment_rules": deepcopy(
                    environment_packet.get(
                        "environment_rules",
                        {},
                    )
                ),
                "continuity_rules": deepcopy(
                    environment_packet.get(
                        "continuity_rules",
                        [],
                    )
                ),
                "negative_rules": deepcopy(
                    environment_packet.get(
                        "negative_rules",
                        [],
                    )
                ),
                "scene_context": deepcopy(
                    environment_packet.get(
                        "scene_context",
                        {},
                    )
                ),
                "source_asset_hashes": deepcopy(
                    environment_packet.get(
                        "source_asset_hashes",
                        {},
                    )
                ),
            }

        if director_packet:
            valid, errors = validate_director_packet(
                director_packet
            )

            if not valid:
                raise ValueError(
                    "Director packet rejected: "
                    + "; ".join(errors)
                )

            director_ref = {
                "schema": director_packet.get("schema"),
                "version": director_packet.get("version"),
                "project_id": director_packet.get("project_id"),
                "creative_brief": director_packet.get(
                    "creative_brief"
                ),
                "production_intent": director_packet.get(
                    "production_intent"
                ),
                "continuity_constraints": deepcopy(
                    director_packet.get(
                        "continuity_constraints"
                    )
                ),
                "generation_instructions": deepcopy(
                    director_packet.get(
                        "generation_instructions"
                    )
                ),
                "qc_gates": deepcopy(
                    director_packet.get("qc_gates", [])
                ),
            }

        continuity = self._build_continuity(
            current_scene_id=scene_id,
            current_shot_id=shot_id,
            shot_size=shot_size,
            camera_angle=camera_angle,
            camera_movement=camera_movement,
            character_ref=character_ref,
            environment_ref=environment_ref,
            previous_shot_packet=previous_shot_packet,
        )

        packet = {
            "schema": PACKET_SCHEMA,
            "version": APP_VERSION,
            "project_id": project_id,
            "scene_id": scene_id,
            "shot_id": shot_id,

            "shot_purpose": shot_purpose,

            "camera": {
                "shot_size": shot_size,
                "angle": camera_angle,
                "movement": camera_movement,
                "composition": composition,
                "focus_mode": focus_mode,
                "lens_guidance": lens_guidance,
                "depth_guidance": depth_guidance,
            },

            "performance_context": {
                "subject": subject,
                "action": action,
            },

            "timing": {
                "duration_seconds": duration_seconds,
                "transition_in": transition_in,
                "transition_out": transition_out,
            },

            "character_reference": character_ref,
            "environment_reference": environment_ref,
            "director_reference": director_ref,

            "continuity": continuity,

            "generation_constraints": {
                "preserve_character_identity": (
                    character_ref is not None
                ),
                "preserve_environment_identity": (
                    environment_ref is not None
                ),
                "camera_change_requires_shot_instruction": True,
                "no_unrequested_identity_drift": True,
                "no_unrequested_environment_drift": True,
                "no_unrequested_camera_drift": True,
            },

            "qc_gates": [
                "shot_schema_valid",
                "character_identity_match",
                "environment_identity_match",
                "camera_instruction_match",
                "composition_match",
                "shot_to_shot_continuity",
                "duration_valid",
            ],

            "downstream_handoff": {
                "target": "joat-ltx-generation-worker",
                "format": PACKET_SCHEMA,
                "ltx_compatible": True,
                "character_master_mutation_allowed": False,
                "environment_master_mutation_allowed": False,
                "director_master_mutation_allowed": False,
            },

            "created_at": utc_now(),
        }

        inherited_lock = director_approved_camera_lock(packet, director_packet, character_packet)
        if inherited_lock is not None:
            packet["camera_locked"] = True
            packet["camera_lock_provenance"] = inherited_lock
        packet["packet_fingerprint"] = packet_fingerprint(packet)

        return packet

    def _build_continuity(
        self,
        current_scene_id: str,
        current_shot_id: str,
        shot_size: str,
        camera_angle: str,
        camera_movement: str,
        character_ref: Optional[dict[str, Any]],
        environment_ref: Optional[dict[str, Any]],
        previous_shot_packet: Optional[dict[str, Any]],
    ) -> dict[str, Any]:

        continuity = {
            "scene_id": current_scene_id,
            "shot_id": current_shot_id,
            "previous_shot_id": None,
            "same_scene_as_previous": None,
            "character_identity_preserved": (
                character_ref is not None
            ),
            "environment_identity_preserved": (
                environment_ref is not None
            ),
            "camera_transition": {
                "previous_shot_size": None,
                "current_shot_size": shot_size,
                "previous_angle": None,
                "current_angle": camera_angle,
                "previous_movement": None,
                "current_movement": camera_movement,
            },
            "continuity_rules": [
                (
                    "Preserve locked character identity across "
                    "continuity-linked shots."
                ),
                (
                    "Preserve locked environment identity, architecture, "
                    "layout, permanent fixtures, and geography."
                ),
                (
                    "Camera changes must be intentional and represented "
                    "by the current shot packet."
                ),
                (
                    "Do not silently change screen direction, subject "
                    "placement, eyeline logic, or spatial relationships."
                ),
                (
                    "Shot duration and transitions must remain consistent "
                    "with Director intent and downstream edit timing."
                ),
            ],
        }

        if previous_shot_packet:
            previous_camera = previous_shot_packet.get(
                "camera",
                {},
            )

            continuity["previous_shot_id"] = (
                previous_shot_packet.get("shot_id")
            )

            continuity["same_scene_as_previous"] = (
                previous_shot_packet.get("scene_id")
                == current_scene_id
            )

            continuity["camera_transition"][
                "previous_shot_size"
            ] = previous_camera.get("shot_size")

            continuity["camera_transition"][
                "previous_angle"
            ] = previous_camera.get("angle")

            continuity["camera_transition"][
                "previous_movement"
            ] = previous_camera.get("movement")

        return continuity

    def acceptance_test(self) -> dict[str, Any]:
        tests: list[dict[str, Any]] = []

        def add(
            name: str,
            passed: bool,
            detail: Any = None,
        ) -> None:
            tests.append(
                {
                    "test": name,
                    "pass": bool(passed),
                    "detail": (
                        detail
                        if detail is not None
                        else bool(passed)
                    ),
                }
            )

        character_packet = self._sample_character_packet()
        environment_packet = self._sample_environment_packet()
        director_packet = self._sample_director_packet()

        # 1
        packet = self.build_packet(
            project_id="JOAT-TEST-PROJECT",
            scene_id="SCENE-001",
            shot_id="SHOT-001",
            shot_purpose="Establish subject in location.",
            shot_size="medium",
            camera_angle="eye_level",
            camera_movement="static",
            composition="rule_of_thirds",
            focus_mode="subject_focus",
            duration_seconds=4.0,
            subject="CHAR-001",
            action="Subject enters frame.",
            lens_guidance="natural perspective",
            depth_guidance="moderate depth",
            transition_in="cut",
            transition_out="cut",
            character_packet=character_packet,
            environment_packet=environment_packet,
            director_packet=director_packet,
        )

        add(
            "1. Shot/Camera packet generates",
            packet.get("schema") == PACKET_SCHEMA,
        )

        # 2
        required_fields = [
            "schema",
            "version",
            "project_id",
            "scene_id",
            "shot_id",
            "shot_purpose",
            "camera",
            "performance_context",
            "timing",
            "character_reference",
            "environment_reference",
            "director_reference",
            "continuity",
            "generation_constraints",
            "qc_gates",
            "downstream_handoff",
            "packet_fingerprint",
        ]

        add(
            "2. Required packet fields present",
            all(x in packet for x in required_fields),
        )

        # 3
        camera_fields = [
            "shot_size",
            "angle",
            "movement",
            "composition",
            "focus_mode",
            "lens_guidance",
            "depth_guidance",
        ]

        add(
            "3. Required camera fields present",
            all(
                x in packet.get("camera", {})
                for x in camera_fields
            ),
        )

        # 4
        add(
            "4. Character identity lock preserved",
            (
                packet.get("character_reference", {}).get(
                    "identity_locked"
                )
                is True
            ),
        )

        # 5
        add(
            "5. Environment identity lock preserved",
            (
                packet.get("environment_reference", {}).get(
                    "environment_locked"
                )
                is True
                and packet.get(
                    "environment_reference",
                    {},
                ).get("asset_identity_lock_ready")
                is True
            ),
        )

        # 6
        add(
            "6. Director reference preserved",
            (
                packet.get("director_reference", {}).get(
                    "project_id"
                )
                == "JOAT-TEST-PROJECT"
            ),
        )

        # 7
        first = self.build_packet(
            project_id="JOAT-TEST-PROJECT",
            scene_id="SCENE-001",
            shot_id="SHOT-001",
            shot_purpose="Establish subject in location.",
            shot_size="medium",
            camera_angle="eye_level",
            camera_movement="static",
            composition="rule_of_thirds",
            focus_mode="subject_focus",
            duration_seconds=4.0,
            subject="CHAR-001",
            action="Subject enters frame.",
            lens_guidance="natural perspective",
            depth_guidance="moderate depth",
            transition_in="cut",
            transition_out="cut",
            character_packet=character_packet,
            environment_packet=environment_packet,
            director_packet=director_packet,
        )

        second = self.build_packet(
            project_id="JOAT-TEST-PROJECT",
            scene_id="SCENE-001",
            shot_id="SHOT-001",
            shot_purpose="Establish subject in location.",
            shot_size="medium",
            camera_angle="eye_level",
            camera_movement="static",
            composition="rule_of_thirds",
            focus_mode="subject_focus",
            duration_seconds=4.0,
            subject="CHAR-001",
            action="Subject enters frame.",
            lens_guidance="natural perspective",
            depth_guidance="moderate depth",
            transition_in="cut",
            transition_out="cut",
            character_packet=character_packet,
            environment_packet=environment_packet,
            director_packet=director_packet,
        )

        add(
            "7. Deterministic packet fingerprint",
            (
                first["packet_fingerprint"]
                == second["packet_fingerprint"]
            ),
        )

        # 8
        invalid_character = deepcopy(character_packet)
        invalid_character["identity_locked"] = False

        rejected = False

        try:
            self.build_packet(
                project_id="TEST",
                scene_id="SCENE-001",
                shot_id="SHOT-001",
                shot_purpose="test",
                shot_size="medium",
                camera_angle="eye_level",
                camera_movement="static",
                composition="centered",
                focus_mode="subject_focus",
                duration_seconds=3,
                subject="test",
                action="test",
                lens_guidance="standard",
                depth_guidance="standard",
                transition_in="cut",
                transition_out="cut",
                character_packet=invalid_character,
            )
        except ValueError:
            rejected = True

        add(
            "8. Unlocked character packet rejected",
            rejected,
        )

        # 9
        invalid_environment = deepcopy(environment_packet)
        invalid_environment[
            "asset_identity_lock_ready"
        ] = False

        rejected = False

        try:
            self.build_packet(
                project_id="TEST",
                scene_id="SCENE-001",
                shot_id="SHOT-001",
                shot_purpose="test",
                shot_size="medium",
                camera_angle="eye_level",
                camera_movement="static",
                composition="centered",
                focus_mode="subject_focus",
                duration_seconds=3,
                subject="test",
                action="test",
                lens_guidance="standard",
                depth_guidance="standard",
                transition_in="cut",
                transition_out="cut",
                environment_packet=invalid_environment,
            )
        except ValueError:
            rejected = True

        add(
            "9. Unlocked environment packet rejected",
            rejected,
        )

        # 10
        invalid_camera_rejected = False

        try:
            self.build_packet(
                project_id="TEST",
                scene_id="SCENE-001",
                shot_id="SHOT-001",
                shot_purpose="test",
                shot_size="made_up_shot",
                camera_angle="eye_level",
                camera_movement="static",
                composition="centered",
                focus_mode="subject_focus",
                duration_seconds=3,
                subject="test",
                action="test",
                lens_guidance="standard",
                depth_guidance="standard",
                transition_in="cut",
                transition_out="cut",
            )
        except ValueError:
            invalid_camera_rejected = True

        add(
            "10. Unsupported camera instruction rejected",
            invalid_camera_rejected,
        )

        # 11
        previous = packet

        next_packet = self.build_packet(
            project_id="JOAT-TEST-PROJECT",
            scene_id="SCENE-001",
            shot_id="SHOT-002",
            shot_purpose="Move closer to subject.",
            shot_size="close_up",
            camera_angle="eye_level",
            camera_movement="push_in",
            composition="centered",
            focus_mode="shallow_focus",
            duration_seconds=3.0,
            subject="CHAR-001",
            action="Subject reacts.",
            lens_guidance="portrait perspective",
            depth_guidance="shallow depth",
            transition_in="cut",
            transition_out="cut",
            character_packet=character_packet,
            environment_packet=environment_packet,
            director_packet=director_packet,
            previous_shot_packet=previous,
        )

        continuity = next_packet.get("continuity", {})

        add(
            "11. Shot-to-shot continuity tracked",
            (
                continuity.get("previous_shot_id")
                == "SHOT-001"
                and continuity.get("same_scene_as_previous")
                is True
                and continuity.get(
                    "camera_transition",
                    {},
                ).get("previous_shot_size")
                == "medium"
            ),
        )

        # 12
        add(
            "12. LTX downstream handoff enabled",
            (
                packet.get("downstream_handoff", {}).get(
                    "ltx_compatible"
                )
                is True
            ),
        )

        # 13
        mutation_protection = packet.get(
            "downstream_handoff",
            {},
        )

        add(
            "13. Locked masters protected from mutation",
            (
                mutation_protection.get(
                    "character_master_mutation_allowed"
                )
                is False
                and mutation_protection.get(
                    "environment_master_mutation_allowed"
                )
                is False
                and mutation_protection.get(
                    "director_master_mutation_allowed"
                )
                is False
            ),
        )

        # 14
        duration_rejected = False

        try:
            self.build_packet(
                project_id="TEST",
                scene_id="SCENE-001",
                shot_id="SHOT-001",
                shot_purpose="test",
                shot_size="medium",
                camera_angle="eye_level",
                camera_movement="static",
                composition="centered",
                focus_mode="subject_focus",
                duration_seconds=0,
                subject="test",
                action="test",
                lens_guidance="standard",
                depth_guidance="standard",
                transition_in="cut",
                transition_out="cut",
            )
        except ValueError:
            duration_rejected = True

        add(
            "14. Invalid shot duration rejected",
            duration_rejected,
        )

        # 15
        generation_constraints = packet.get(
            "generation_constraints",
            {},
        )

        add(
            "15. Camera and identity drift protection active",
            (
                generation_constraints.get(
                    "no_unrequested_identity_drift"
                )
                is True
                and generation_constraints.get(
                    "no_unrequested_environment_drift"
                )
                is True
                and generation_constraints.get(
                    "no_unrequested_camera_drift"
                )
                is True
            ),
        )

        all_passed = all(x["pass"] for x in tests)

        return {
            "acceptance_test_version": ACCEPTANCE_TEST_VERSION,
            "app_version": APP_VERSION,
            "packet_schema": PACKET_SCHEMA,
            "tests": tests,
            "all_passed": all_passed,
            "production_ready": all_passed,
            "note": (
                "Shot/Camera Master is production-ready when all "
                "acceptance tests pass and locked Character, Environment, "
                "and Director inputs remain immutable."
            ),
        }

    @staticmethod
    def _sample_character_packet() -> dict[str, Any]:
        return {
            "schema": "joat.character_packet.v1",
            "character_id": "CHAR-001",
            "character_name": "Founder",
            "character_version": "1.0.0",
            "identity_locked": True,
            "identity_lock_asset": (
                "assets/CHAR-001/identity-anchor.jpeg"
            ),
            "supporting_reference_assets": [],
            "appearance_rules": {
                "identity": "Preserve approved identity."
            },
            "continuity_rules": [
                "Preserve facial identity."
            ],
            "negative_rules": [
                "Do not change identity."
            ],
            "source_asset_hashes": {
                "CHAR-001-A01": "testhash"
            },
            "approval": {
                "live_change_allowed": False,
                "requires_human_approval_for_registry_mutation": True,
            },
        }

    @staticmethod
    def _sample_environment_packet() -> dict[str, Any]:
        return {
            "schema": "joat.environment_packet.v1",
            "environment_id": "ENV-001",
            "environment_name": "Executive Office",
            "environment_version": "1.1.0",
            "environment_locked": True,
            "asset_identity_lock_ready": True,
            "identity_lock_asset": (
                "environment_assets/"
                "ENV-008_office_identity_anchor.jpeg"
            ),
            "supporting_reference_assets": [],
            "environment_rules": {
                "identity": "Preserve approved environment."
            },
            "continuity_rules": [
                "Preserve architecture and layout."
            ],
            "negative_rules": [
                "Do not change location."
            ],
            "scene_context": {
                "scene_id": "SCENE-001",
                "shot_id": "SHOT-001",
                "time_of_day": "day",
                "lighting": "natural daylight",
                "weather": "clear",
            },
            "source_asset_hashes": {
                "ENV-001-A01": "testhash"
            },
            "approval": {
                "live_change_allowed": False,
                "requires_human_approval_for_registry_mutation": True,
            },
        }

    @staticmethod
    def _sample_director_packet() -> dict[str, Any]:
        return {
            "schema": "joat.director_packet.v1",
            "version": "1.0.1",
            "project_id": "JOAT-TEST-PROJECT",
            "creative_brief": "Acceptance test.",
            "production_intent": "animation",
            "per_shot": [
                {
                    "shot_id": "SHOT-001",
                    "scene_id": "SCENE-001",
                }
            ],
            "continuity_constraints": "Preserve continuity.",
            "generation_instructions": "standard",
            "qc_gates": [
                "identity_anchor_match",
                "continuity_check",
            ],
        }


MASTER = ShotCameraMaster()


# =============================================================================
# UI
# =============================================================================

def build_packet_ui(
    project_id: str,
    scene_id: str,
    shot_id: str,
    shot_purpose: str,
    shot_size: str,
    camera_angle: str,
    camera_movement: str,
    composition: str,
    focus_mode: str,
    duration_seconds: float,
    subject: str,
    action: str,
    lens_guidance: str,
    depth_guidance: str,
    transition_in: str,
    transition_out: str,
    character_json: str,
    environment_json: str,
    director_json: str,
    previous_shot_json: str,
) -> dict[str, Any]:

    character_packet = parse_json(
        character_json,
        None,
    ) if character_json.strip() else None

    environment_packet = parse_json(
        environment_json,
        None,
    ) if environment_json.strip() else None

    director_packet = parse_json(
        director_json,
        None,
    ) if director_json.strip() else None

    previous_shot = parse_json(
        previous_shot_json,
        None,
    ) if previous_shot_json.strip() else None

    return MASTER.build_packet(
        project_id=project_id,
        scene_id=scene_id,
        shot_id=shot_id,
        shot_purpose=shot_purpose,
        shot_size=shot_size,
        camera_angle=camera_angle,
        camera_movement=camera_movement,
        composition=composition,
        focus_mode=focus_mode,
        duration_seconds=duration_seconds,
        subject=subject,
        action=action,
        lens_guidance=lens_guidance,
        depth_guidance=depth_guidance,
        transition_in=transition_in,
        transition_out=transition_out,
        character_packet=character_packet,
        environment_packet=environment_packet,
        director_packet=director_packet,
        previous_shot_packet=previous_shot,
    )


def tests_ui() -> dict[str, Any]:
    return MASTER.acceptance_test()


def build_app() -> gr.Blocks:

    with gr.Blocks(
        title=f"J.O.A.T. Shot & Camera Master v{APP_VERSION}"
    ) as app:

        gr.Markdown(
            f"# J.O.A.T. Shot & Camera Master — v{APP_VERSION}\n\n"
            "**Roadmap Stage #4**  \n"
            "Owns shot size, camera angle, movement, composition, focus, "
            "duration, and shot-to-shot continuity."
        )

        with gr.Tab("Shot / Camera Packet"):

            with gr.Row():
                project_id = gr.Textbox(
                    value="JOAT-PROJECT-001",
                    label="Project ID",
                )

                scene_id = gr.Textbox(
                    value="SCENE-001",
                    label="Scene ID",
                )

                shot_id = gr.Textbox(
                    value="SHOT-001",
                    label="Shot ID",
                )

            shot_purpose = gr.Textbox(
                value="Establish the subject and scene.",
                label="Shot Purpose",
            )

            with gr.Row():
                shot_size = gr.Dropdown(
                    choices=SHOT_SIZES,
                    value="medium",
                    label="Shot Size",
                )

                camera_angle = gr.Dropdown(
                    choices=CAMERA_ANGLES,
                    value="eye_level",
                    label="Camera Angle",
                )

                camera_movement = gr.Dropdown(
                    choices=CAMERA_MOVEMENTS,
                    value="static",
                    label="Camera Movement",
                )

            with gr.Row():
                composition = gr.Dropdown(
                    choices=COMPOSITION_MODES,
                    value="rule_of_thirds",
                    label="Composition",
                )

                focus_mode = gr.Dropdown(
                    choices=FOCUS_MODES,
                    value="subject_focus",
                    label="Focus",
                )

                duration_seconds = gr.Number(
                    value=4.0,
                    label="Duration — Seconds",
                )

            with gr.Row():
                subject = gr.Textbox(
                    value="",
                    label="Subject / Character",
                )

                action = gr.Textbox(
                    value="",
                    label="Performance / Action",
                )

            with gr.Row():
                lens_guidance = gr.Textbox(
                    value="natural perspective",
                    label="Lens Guidance",
                )

                depth_guidance = gr.Textbox(
                    value="moderate depth",
                    label="Depth Guidance",
                )

            with gr.Row():
                transition_in = gr.Textbox(
                    value="cut",
                    label="Transition In",
                )

                transition_out = gr.Textbox(
                    value="cut",
                    label="Transition Out",
                )

            gr.Markdown("### Locked Upstream Packets")

            character_json = gr.Textbox(
                label="Character Packet JSON — optional",
                lines=8,
            )

            environment_json = gr.Textbox(
                label="Environment Packet JSON — optional",
                lines=8,
            )

            director_json = gr.Textbox(
                label="Director Packet JSON — optional",
                lines=8,
            )

            previous_shot_json = gr.Textbox(
                label="Previous Shot Packet JSON — optional",
                lines=8,
            )

            packet_output = gr.JSON(
                label="joat.shot_camera_packet.v1"
            )

            gr.Button(
                "Build Shot / Camera Packet",
                variant="primary",
            ).click(
                fn=build_packet_ui,
                inputs=[
                    project_id,
                    scene_id,
                    shot_id,
                    shot_purpose,
                    shot_size,
                    camera_angle,
                    camera_movement,
                    composition,
                    focus_mode,
                    duration_seconds,
                    subject,
                    action,
                    lens_guidance,
                    depth_guidance,
                    transition_in,
                    transition_out,
                    character_json,
                    environment_json,
                    director_json,
                    previous_shot_json,
                ],
                outputs=packet_output,
            )

        with gr.Tab("Acceptance Tests"):

            test_output = gr.JSON(
                label="Shot / Camera Acceptance Test"
            )

            gr.Button(
                "Run Acceptance Tests",
                variant="primary",
            ).click(
                fn=tests_ui,
                inputs=None,
                outputs=test_output,
            )

        with gr.Tab("About"):

            gr.Markdown(
                f"""
## J.O.A.T. Shot & Camera Master

**Version:** `{APP_VERSION}`

**Packet:** `{PACKET_SCHEMA}`

### Owns

- Shot size
- Camera angle
- Camera movement
- Composition
- Focus
- Lens guidance
- Depth guidance
- Shot duration
- Shot-to-shot camera continuity

### Upstream

- Director Creative Intelligence
- Character Asset Master
- Scene & Environment Master

### Downstream

- Performance / Action Intelligence
- LTX Generation Worker
- QC / Continuity Supervisor
- Editor / Timeline system

### Locked Rules

- Character identity cannot silently drift.
- Environment identity cannot silently drift.
- Camera behavior cannot silently drift.
- Locked upstream masters cannot be mutated.
- Shot changes must be represented by a new controlled packet.
"""
            )

    return app


if __name__ == "__main__":
    demo = build_app()

    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )