"""
J.O.A.T. Generation Supervisor Master v1.0.3

Roadmap Stage #6

Purpose:
- Receive locked upstream production packets
- Validate Character, Environment, Director, Shot/Camera, and Performance/Action
- Preserve all approved creative and continuity decisions
- Select an approved generation route
- Build deterministic joat.generation_job.v1 packets
- Route jobs toward LTX / image / audio / VFX generation workers
- Never silently mutate upstream masters
- Never invent missing locked production decisions
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Optional

import gradio as gr
from joat_worker_dispatch import handoff_generation_packet


# =============================================================================
# CONFIG
# =============================================================================

APP_VERSION = "1.0.3"

PACKET_SCHEMA = "joat.generation_supervisor_packet.v1"
JOB_SCHEMA = "joat.generation_job.v1"

SUPPORTED_JOB_TYPES = [
    "video",
    "image",
    "voice",
    "audio",
    "vfx",
]

SUPPORTED_ENGINES = {
    "video": [
        "ltx",
    ],
    "image": [
        "image_generation",
    ],
    "voice": [
        "voice_generation",
    ],
    "audio": [
        "audio_generation",
    ],
    "vfx": [
        "vfx_generation",
    ],
}

REQUIRED_UPSTREAM = {
    "character": {
        "schemas": [
            "joat.character_packet.v1",
            "joat.character_identity_packet.v1",
        ],
        "lock_fields": [
            "identity_locked",
            "character_locked",
            "asset_identity_lock_ready",
        ],
    },
    "environment": {
        "schemas": [
            "joat.environment_packet.v1",
        ],
        "lock_fields": [
            "environment_locked",
            "asset_identity_lock_ready",
        ],
    },
    "director": {
        "schemas": [
            "joat.director_packet.v1",
        ],
        "lock_fields": [
            "director_locked",
            "intent_locked",
            "creative_intent_locked",
        ],
    },
    "shot_camera": {
        "schemas": [
            "joat.shot_camera_packet.v1",
        ],
        "lock_fields": [
            "shot_camera_locked",
            "camera_locked",
        ],
    },
    "performance_action": {
        "schemas": [
            "joat.performance_action_packet.v1",
        ],
        "lock_fields": [
            "performance_action_locked",
            "performance_locked",
        ],
    },
}


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


def parse_json_object(raw: str, label: str) -> dict[str, Any]:
    if raw is None or not str(raw).strip():
        raise ValueError(f"{label} packet is required.")

    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{label} packet contains invalid JSON: {exc}"
        ) from exc

    if not isinstance(value, dict):
        raise ValueError(
            f"{label} packet must be a JSON object."
        )

    return value


def packet_fingerprint(packet: dict[str, Any]) -> str:
    existing = packet.get("packet_fingerprint")

    if existing:
        return str(existing)

    return sha256_text(stable_json(packet))


def find_true_lock(
    packet: dict[str, Any],
    candidates: list[str],
) -> Optional[str]:
    for field in candidates:
        if packet.get(field) is True:
            return field

    approval = packet.get("approval", {})

    if isinstance(approval, dict):
        for field in candidates:
            if approval.get(field) is True:
                return f"approval.{field}"

    return None


def validate_upstream_packet(
    role: str,
    packet: dict[str, Any],
) -> dict[str, Any]:
    definition = REQUIRED_UPSTREAM[role]

    schema = packet.get("schema")

    if schema not in definition["schemas"]:
        raise ValueError(
            f"{role} packet schema rejected. "
            f"Received {schema!r}; expected one of "
            f"{definition['schemas']}."
        )

    lock_field = find_true_lock(
        packet,
        definition["lock_fields"],
    )

    # Environment has two distinct locks in our existing contract:
    # registry/location lock + approved image identity lock.
    if role == "environment":
        if packet.get("environment_locked") is not True:
            raise ValueError(
                "Environment packet rejected: "
                "environment_locked must be true."
            )

        if packet.get("asset_identity_lock_ready") is not True:
            raise ValueError(
                "Environment packet rejected: "
                "asset_identity_lock_ready must be true."
            )

        lock_field = (
            "environment_locked + "
            "asset_identity_lock_ready"
        )

    if not lock_field:
        raise ValueError(
            f"{role} packet rejected: no approved lock field "
            "is true."
        )

    return {
        "role": role,
        "schema": schema,
        "lock_verified": True,
        "lock_source": lock_field,
        "fingerprint": packet_fingerprint(packet),
    }


def choose_engine(
    job_type: str,
    requested_engine: str,
) -> str:
    if job_type not in SUPPORTED_JOB_TYPES:
        raise ValueError(
            f"Unsupported generation job type: {job_type}"
        )

    allowed = SUPPORTED_ENGINES[job_type]

    if requested_engine == "auto":
        return allowed[0]

    if requested_engine not in allowed:
        raise ValueError(
            f"Engine {requested_engine!r} is not approved for "
            f"job type {job_type!r}. Approved engines: {allowed}"
        )

    return requested_engine


def validate_duration(
    job_type: str,
    duration_seconds: float,
) -> Optional[float]:
    if job_type in ("video", "audio", "voice", "vfx"):
        if duration_seconds <= 0:
            raise ValueError(
                f"{job_type} duration must be greater than zero."
            )

        if duration_seconds > 300:
            raise ValueError(
                "Generation job duration exceeds the v1 safety "
                "limit of 300 seconds."
            )

        return float(duration_seconds)

    # Still-image jobs do not require a duration.
    return None


def build_prompt_contract(
    character: dict[str, Any],
    environment: dict[str, Any],
    director: dict[str, Any],
    shot_camera: dict[str, Any],
    performance_action: dict[str, Any],
    generation_notes: str,
) -> dict[str, Any]:
    """
    Important:
    This supervisor does NOT rewrite creative intent.

    It packages the upstream masters so a downstream worker can
    translate them into the engine-specific prompt/configuration.
    """

    return {
        "character_packet": deepcopy(character),
        "environment_packet": deepcopy(environment),
        "director_packet": deepcopy(director),
        "shot_camera_packet": deepcopy(shot_camera),
        "performance_action_packet": deepcopy(
            performance_action
        ),
        "generation_notes": (
            generation_notes.strip()
            if generation_notes
            else ""
        ),
        "translation_policy": {
            "may_translate_format": True,
            "may_summarize_for_engine_limits": True,
            "may_change_character_identity": False,
            "may_change_environment_identity": False,
            "may_change_director_intent": False,
            "may_change_camera_intent": False,
            "may_change_performance_intent": False,
            "may_invent_missing_locked_decisions": False,
        },
    }


# =============================================================================
# GENERATION SUPERVISOR
# =============================================================================

class GenerationSupervisor:
    def build_job(
        self,
        character: dict[str, Any],
        environment: dict[str, Any],
        director: dict[str, Any],
        shot_camera: dict[str, Any],
        performance_action: dict[str, Any],
        job_type: str,
        requested_engine: str,
        project_id: str,
        scene_id: str,
        shot_id: str,
        duration_seconds: float,
        aspect_ratio: str,
        generation_notes: str,
    ) -> dict[str, Any]:

        validations = {
            "character": validate_upstream_packet(
                "character",
                character,
            ),
            "environment": validate_upstream_packet(
                "environment",
                environment,
            ),
            "director": validate_upstream_packet(
                "director",
                director,
            ),
            "shot_camera": validate_upstream_packet(
                "shot_camera",
                shot_camera,
            ),
            "performance_action": validate_upstream_packet(
                "performance_action",
                performance_action,
            ),
        }

        engine = choose_engine(
            job_type,
            requested_engine,
        )

        duration = validate_duration(
            job_type,
            duration_seconds,
        )

        prompt_contract = build_prompt_contract(
            character=character,
            environment=environment,
            director=director,
            shot_camera=shot_camera,
            performance_action=performance_action,
            generation_notes=generation_notes,
        )

        source_fingerprints = {
            role: info["fingerprint"]
            for role, info in validations.items()
        }

        immutable_snapshot = {
            "character": deepcopy(character),
            "environment": deepcopy(environment),
            "director": deepcopy(director),
            "shot_camera": deepcopy(shot_camera),
            "performance_action": deepcopy(
                performance_action
            ),
        }

        job_core = {
            "schema": JOB_SCHEMA,
            "job_type": job_type,
            "engine": engine,

            "project_context": {
                "project_id": project_id.strip() or None,
                "scene_id": scene_id.strip() or None,
                "shot_id": shot_id.strip() or None,
            },

            "generation_specification": {
                "duration_seconds": duration,
                "aspect_ratio": aspect_ratio,
            },

            "upstream_validation": validations,
            "source_packet_fingerprints": source_fingerprints,

            "prompt_contract": prompt_contract,

            "immutable_upstream_snapshot": immutable_snapshot,

            "continuity_policy": {
                "preserve_character_identity": True,
                "preserve_environment_identity": True,
                "preserve_director_intent": True,
                "preserve_shot_camera_intent": True,
                "preserve_performance_action_intent": True,
                "silent_creative_mutation_allowed": False,
            },

            "execution_policy": {
                "automatic_engine_routing_allowed": True,
                "fallback_engine_allowed": False,
                "upstream_registry_mutation_allowed": False,
                "human_approval_required_for_locked_change": True,
            },

            "downstream_handoff": {
                "ltx_compatible": (
                    job_type == "video"
                    and engine == "ltx"
                ),
                "image_worker_compatible": (
                    job_type == "image"
                ),
                "voice_worker_compatible": (
                    job_type == "voice"
                ),
                "audio_worker_compatible": (
                    job_type == "audio"
                ),
                "vfx_worker_compatible": (
                    job_type == "vfx"
                ),
                "ready_for_generation_worker": True,
            },
        }

        job_core["job_fingerprint"] = sha256_text(
            stable_json(job_core)
        )

        supervisor_packet = {
            "schema": PACKET_SCHEMA,
            "app_version": APP_VERSION,
            "generation_job": job_core,
            "production_ready": True,
        }

        supervisor_packet["packet_fingerprint"] = (
            sha256_text(stable_json(supervisor_packet))
        )

        return supervisor_packet

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

        character = {
            "schema": "joat.character_packet.v1",
            "character_id": "CHAR-001",
            "identity_locked": True,
            "packet_fingerprint": "CHAR-FP-001",
        }

        environment = {
            "schema": "joat.environment_packet.v1",
            "environment_id": "ENV-001",
            "environment_locked": True,
            "asset_identity_lock_ready": True,
            "packet_fingerprint": "ENV-FP-001",
        }

        director = {
            "schema": "joat.director_packet.v1",
            "director_locked": True,
            "creative_intent": {
                "tone": "cinematic",
                "emotion": "controlled tension",
            },
            "packet_fingerprint": "DIR-FP-001",
        }

        shot_camera = {
            "schema": "joat.shot_camera_packet.v1",
            "shot_camera_locked": True,
            "camera": {
                "shot_type": "medium",
                "movement": "slow push in",
            },
            "packet_fingerprint": "SHOT-FP-001",
        }

        performance = {
            "schema": "joat.performance_action_packet.v1",
            "performance_action_locked": True,
            "performance": {
                "emotion": "concerned",
                "action": "looks toward doorway",
            },
            "packet_fingerprint": "PERF-FP-001",
        }

        kwargs = {
            "character": character,
            "environment": environment,
            "director": director,
            "shot_camera": shot_camera,
            "performance_action": performance,
            "job_type": "video",
            "requested_engine": "ltx",
            "project_id": "PROJECT-001",
            "scene_id": "SCENE-001",
            "shot_id": "SHOT-001",
            "duration_seconds": 6.0,
            "aspect_ratio": "16:9",
            "generation_notes": "",
        }

        packet = self.build_job(**kwargs)
        job = packet["generation_job"]

        # 1
        add(
            "1. Generation Supervisor packet generates",
            packet.get("schema") == PACKET_SCHEMA,
        )

        # 2
        required_packet_fields = [
            "schema",
            "app_version",
            "generation_job",
            "production_ready",
            "packet_fingerprint",
        ]

        add(
            "2. Required supervisor packet fields present",
            all(x in packet for x in required_packet_fields),
        )

        # 3
        required_job_fields = [
            "schema",
            "job_type",
            "engine",
            "project_context",
            "generation_specification",
            "upstream_validation",
            "source_packet_fingerprints",
            "prompt_contract",
            "immutable_upstream_snapshot",
            "continuity_policy",
            "execution_policy",
            "downstream_handoff",
            "job_fingerprint",
        ]

        add(
            "3. Required generation job fields present",
            all(x in job for x in required_job_fields),
        )

        # 4
        add(
            "4. Character lock validated",
            job["upstream_validation"]["character"][
                "lock_verified"
            ] is True,
        )

        # 5
        add(
            "5. Environment lock validated",
            job["upstream_validation"]["environment"][
                "lock_verified"
            ] is True,
        )

        # 6
        add(
            "6. Director lock validated",
            job["upstream_validation"]["director"][
                "lock_verified"
            ] is True,
        )

        # 7
        add(
            "7. Shot/Camera lock validated",
            job["upstream_validation"]["shot_camera"][
                "lock_verified"
            ] is True,
        )

        # 8
        add(
            "8. Performance/Action lock validated",
            job["upstream_validation"]["performance_action"][
                "lock_verified"
            ] is True,
        )

        # 9
        add(
            "9. LTX video route selected",
            (
                job["job_type"] == "video"
                and job["engine"] == "ltx"
                and job["downstream_handoff"][
                    "ltx_compatible"
                ] is True
            ),
        )

        # 10
        first = self.build_job(**kwargs)
        second = self.build_job(**kwargs)

        add(
            "10. Deterministic generation fingerprints",
            (
                first["packet_fingerprint"]
                == second["packet_fingerprint"]
                and first["generation_job"][
                    "job_fingerprint"
                ]
                == second["generation_job"][
                    "job_fingerprint"
                ]
            ),
        )

        # 11
        before = stable_json(
            {
                "character": character,
                "environment": environment,
                "director": director,
                "shot_camera": shot_camera,
                "performance": performance,
            }
        )

        self.build_job(**kwargs)

        after = stable_json(
            {
                "character": character,
                "environment": environment,
                "director": director,
                "shot_camera": shot_camera,
                "performance": performance,
            }
        )

        add(
            "11. Upstream packets remain immutable",
            before == after,
        )

        # 12
        rejected = False

        bad_character = deepcopy(character)
        bad_character["identity_locked"] = False

        try:
            self.build_job(
                **{
                    **kwargs,
                    "character": bad_character,
                }
            )
        except ValueError:
            rejected = True

        add(
            "12. Unlocked character packet rejected",
            rejected,
        )

        # 13
        rejected = False

        bad_environment = deepcopy(environment)
        bad_environment[
            "asset_identity_lock_ready"
        ] = False

        try:
            self.build_job(
                **{
                    **kwargs,
                    "environment": bad_environment,
                }
            )
        except ValueError:
            rejected = True

        add(
            "13. Unlocked environment packet rejected",
            rejected,
        )

        # 14
        rejected = False

        bad_director = deepcopy(director)
        bad_director["director_locked"] = False

        try:
            self.build_job(
                **{
                    **kwargs,
                    "director": bad_director,
                }
            )
        except ValueError:
            rejected = True

        add(
            "14. Unlocked Director packet rejected",
            rejected,
        )

        # 15
        rejected = False

        bad_shot = deepcopy(shot_camera)
        bad_shot["shot_camera_locked"] = False

        try:
            self.build_job(
                **{
                    **kwargs,
                    "shot_camera": bad_shot,
                }
            )
        except ValueError:
            rejected = True

        add(
            "15. Unlocked Shot/Camera packet rejected",
            rejected,
        )

        # 16
        rejected = False

        bad_performance = deepcopy(performance)
        bad_performance[
            "performance_action_locked"
        ] = False

        try:
            self.build_job(
                **{
                    **kwargs,
                    "performance_action": bad_performance,
                }
            )
        except ValueError:
            rejected = True

        add(
            "16. Unlocked Performance/Action packet rejected",
            rejected,
        )

        # 17
        rejected = False

        try:
            self.build_job(
                **{
                    **kwargs,
                    "requested_engine": "unapproved-engine",
                }
            )
        except ValueError:
            rejected = True

        add(
            "17. Unsupported generation engine rejected",
            rejected,
        )

        # 18
        rejected = False

        try:
            self.build_job(
                **{
                    **kwargs,
                    "duration_seconds": 0,
                }
            )
        except ValueError:
            rejected = True

        add(
            "18. Invalid generation duration rejected",
            rejected,
        )

        # 19
        policy = job["prompt_contract"][
            "translation_policy"
        ]

        drift_protection = (
            policy["may_change_character_identity"] is False
            and policy[
                "may_change_environment_identity"
            ] is False
            and policy[
                "may_change_director_intent"
            ] is False
            and policy[
                "may_change_camera_intent"
            ] is False
            and policy[
                "may_change_performance_intent"
            ] is False
            and policy[
                "may_invent_missing_locked_decisions"
            ] is False
        )

        add(
            "19. Generation creative-drift protection active",
            drift_protection,
        )

        # 20
        handoff = job["downstream_handoff"]

        add(
            "20. Generation-worker handoff enabled",
            (
                handoff[
                    "ready_for_generation_worker"
                ] is True
                and handoff["ltx_compatible"] is True
            ),
        )

        all_passed = all(
            x["pass"]
            for x in tests
        )

        return {
            "acceptance_test_version": "1.0.0",
            "app_version": APP_VERSION,
            "packet_schema": PACKET_SCHEMA,
            "job_schema": JOB_SCHEMA,
            "tests": tests,
            "all_passed": all_passed,
            "production_ready": all_passed,
            "note": (
                "Generation Supervisor is production-ready when "
                "all locked upstream packets validate, routing is "
                "deterministic, creative drift is prohibited, and "
                "the approved generation worker handoff is enabled."
            ),
        }


SUPERVISOR = GenerationSupervisor()


# =============================================================================
# UI
# =============================================================================

def build_job_ui(
    character_raw: str,
    environment_raw: str,
    director_raw: str,
    shot_camera_raw: str,
    performance_raw: str,
    job_type: str,
    requested_engine: str,
    project_id: str,
    scene_id: str,
    shot_id: str,
    duration_seconds: float,
    aspect_ratio: str,
    generation_notes: str,
) -> dict[str, Any]:

    character = parse_json_object(
        character_raw,
        "Character",
    )

    environment = parse_json_object(
        environment_raw,
        "Environment",
    )

    director = parse_json_object(
        director_raw,
        "Director",
    )

    shot_camera = parse_json_object(
        shot_camera_raw,
        "Shot/Camera",
    )

    performance = parse_json_object(
        performance_raw,
        "Performance/Action",
    )

    return SUPERVISOR.build_job(
        character=character,
        environment=environment,
        director=director,
        shot_camera=shot_camera,
        performance_action=performance,
        job_type=job_type,
        requested_engine=requested_engine,
        project_id=project_id,
        scene_id=scene_id,
        shot_id=shot_id,
        duration_seconds=duration_seconds,
        aspect_ratio=aspect_ratio,
        generation_notes=generation_notes,
    )


def build_job_and_store_ui(
    character_raw: str,
    environment_raw: str,
    director_raw: str,
    shot_camera_raw: str,
    performance_raw: str,
    job_type: str,
    requested_engine: str,
    project_id: str,
    scene_id: str,
    shot_id: str,
    duration_seconds: float,
    aspect_ratio: str,
    generation_notes: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    packet = build_job_ui(
        character_raw, environment_raw, director_raw, shot_camera_raw,
        performance_raw, job_type, requested_engine, project_id,
        scene_id, shot_id, duration_seconds, aspect_ratio, generation_notes,
    )
    # State stays on the server; the JSON display can normalize 6.0 to 6.
    return packet, deepcopy(packet)


def send_to_worker_ui(
    supervisor_packet: dict,
    profile: Optional[gr.OAuthProfile],
) -> dict[str, Any]:
    """Only the authenticated studio owner can initiate manual dispatch."""
    if profile is None or profile.username.casefold() != "dezz-9-10":
        raise gr.Error("Sign in as Dezz-9-10 to send a job to the Worker.")
    try:
        return handoff_generation_packet(supervisor_packet)
    except (ValueError, RuntimeError) as exc:
        raise gr.Error(str(exc)) from None
    except Exception:
        raise gr.Error("Worker handoff could not complete; no automatic retry was made.") from None


def download_source_packet_ui(packet: dict, profile: Optional[gr.OAuthProfile]):
    if profile is None or profile.username.casefold() != "dezz-9-10":
        raise gr.Error("Sign in as Dezz-9-10 to export the original job.")
    if not isinstance(packet, dict) or packet.get("production_ready") is not True:
        raise gr.Error("Build a Generation Job first.")
    output = Path(tempfile.mkdtemp(prefix="joat-source-packet-")) / f"generation_supervisor_packet_v{APP_VERSION}.json"
    output.write_text(json.dumps(packet, ensure_ascii=False, indent=2))
    return str(output)


def tests_ui() -> dict[str, Any]:
    return SUPERVISOR.acceptance_test()


def example_packets() -> tuple[str, str, str, str, str]:
    character = {
        "schema": "joat.character_packet.v1",
        "character_id": "CHAR-001",
        "identity_locked": True,
        "packet_fingerprint": "CHAR-FP-001",
    }

    environment = {
        "schema": "joat.environment_packet.v1",
        "environment_id": "ENV-001",
        "environment_locked": True,
        "asset_identity_lock_ready": True,
        "packet_fingerprint": "ENV-FP-001",
    }

    director = {
        "schema": "joat.director_packet.v1",
        "director_locked": True,
        "creative_intent": {
            "tone": "cinematic",
            "emotion": "controlled tension",
        },
        "packet_fingerprint": "DIR-FP-001",
    }

    shot_camera = {
        "schema": "joat.shot_camera_packet.v1",
        "shot_camera_locked": True,
        "camera": {
            "shot_type": "medium",
            "movement": "slow push in",
        },
        "packet_fingerprint": "SHOT-FP-001",
    }

    performance = {
        "schema": "joat.performance_action_packet.v1",
        "performance_action_locked": True,
        "performance": {
            "emotion": "concerned",
            "action": "looks toward doorway",
        },
        "packet_fingerprint": "PERF-FP-001",
    }

    return tuple(
        json.dumps(x, indent=2)
        for x in [
            character,
            environment,
            director,
            shot_camera,
            performance,
        ]
    )


def build_app() -> gr.Blocks:
    examples = example_packets()

    with gr.Blocks(
        title=(
            "J.O.A.T. Generation Supervisor Master "
            f"v{APP_VERSION}"
        )
    ) as app:

        gr.Markdown(
            "# J.O.A.T. Generation Supervisor Master\n\n"
            f"**Version:** {APP_VERSION}  \n"
            "**Roadmap Stage #6**\n\n"
            "Validates locked upstream production packets, "
            "selects an approved generation route, and creates "
            "deterministic generation jobs without changing "
            "approved creative decisions."
        )

        with gr.Tab("Generation Job"):

            with gr.Row():
                job_type = gr.Dropdown(
                    choices=SUPPORTED_JOB_TYPES,
                    value="video",
                    label="Generation Job Type",
                )

                requested_engine = gr.Dropdown(
                    choices=[
                        "auto",
                        "ltx",
                        "image_generation",
                        "voice_generation",
                        "audio_generation",
                        "vfx_generation",
                    ],
                    value="ltx",
                    label="Requested Engine",
                )

            with gr.Row():
                project_id = gr.Textbox(
                    value="PROJECT-001",
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

            with gr.Row():
                duration_seconds = gr.Number(
                    value=6,
                    label="Duration Seconds",
                )

                aspect_ratio = gr.Dropdown(
                    choices=[
                        "16:9",
                        "9:16",
                        "1:1",
                        "4:3",
                        "21:9",
                    ],
                    value="16:9",
                    label="Aspect Ratio",
                )

            character_raw = gr.Code(
                value=examples[0],
                language="json",
                label="Character Packet",
            )

            environment_raw = gr.Code(
                value=examples[1],
                language="json",
                label="Environment Packet",
            )

            director_raw = gr.Code(
                value=examples[2],
                language="json",
                label="Director Packet",
            )

            shot_camera_raw = gr.Code(
                value=examples[3],
                language="json",
                label="Shot / Camera Packet",
            )

            performance_raw = gr.Code(
                value=examples[4],
                language="json",
                label="Performance / Action Packet",
            )

            generation_notes = gr.Textbox(
                value="",
                lines=4,
                label="Generation Notes",
                placeholder=(
                    "Optional technical notes only. "
                    "Do not use this field to override locked "
                    "creative decisions."
                ),
            )

            output = gr.JSON(
                label="Generation Supervisor Packet",
            )

            packet_state = gr.State(value=None)

            gr.Button(
                "Build Generation Job",
                variant="primary",
            ).click(
                fn=build_job_and_store_ui,
                inputs=[
                    character_raw,
                    environment_raw,
                    director_raw,
                    shot_camera_raw,
                    performance_raw,
                    job_type,
                    requested_engine,
                    project_id,
                    scene_id,
                    shot_id,
                    duration_seconds,
                    aspect_ratio,
                    generation_notes,
                ],
                outputs=[output, packet_state],
                api_name="build_job_ui",
            )

            gr.Markdown(
                "### Controlled Worker Handoff\n"
                "Build the job above, sign in as the studio owner, then send it. "
                "This returns a validated execution packet; it does not render media."
            )
            if all(os.getenv(name) for name in (
                "OAUTH_CLIENT_ID", "OAUTH_CLIENT_SECRET", "OAUTH_SCOPES",
                "OPENID_PROVIDER_URL",
            )):
                gr.LoginButton()
            else:
                gr.Markdown(
                    "Owner sign-in becomes available when Hugging Face provisions "
                    "the Space's OAuth configuration. Dispatch remains blocked until then."
                )
            source_packet_file = gr.File(label="Download original job JSON for rendering (preserves fingerprints)")
            gr.Button("Export original job JSON").click(download_source_packet_ui, inputs=packet_state, outputs=source_packet_file, api_name="download_source_packet", api_visibility="private")
            worker_response = gr.JSON(label="Validated Generation Worker Response")
            gr.Button("Send to Generation Worker").click(
                fn=send_to_worker_ui,
                inputs=packet_state,
                outputs=worker_response,
                api_name="send_to_generation_worker",
                api_visibility="private",
                concurrency_limit=1,
                trigger_mode="once",
            )

        with gr.Tab("Acceptance Tests"):

            test_output = gr.JSON(
                label="Generation Supervisor Acceptance Test",
            )

            gr.Button(
                "Run Acceptance Tests",
                variant="primary",
            ).click(
                fn=tests_ui,
                inputs=None,
                outputs=test_output,
            )

        with gr.Tab("Routing Contract"):

            gr.JSON(
                value={
                    "supported_job_types": SUPPORTED_JOB_TYPES,
                    "approved_engines": SUPPORTED_ENGINES,
                    "rules": {
                        "upstream_locks_required": True,
                        "silent_creative_mutation": False,
                        "fallback_engine": False,
                        "human_approval_for_locked_change": True,
                    },
                },
                label="Generation Routing Contract",
            )

        with gr.Tab("About"):

            gr.Markdown(
                f"""
## J.O.A.T. Generation Supervisor Master

**Version:** {APP_VERSION}

**Supervisor packet:** `{PACKET_SCHEMA}`

**Generation job:** `{JOB_SCHEMA}`

### Chain

Character Master  
+ Environment Master  
+ Director Master  
+ Shot / Camera Master  
+ Performance / Action Master  

Ã¢ÂÂ

**Generation Supervisor**

Ã¢ÂÂ

LTX / Image / Voice / Audio / VFX workers

### Authority Boundary

The Generation Supervisor may translate approved instructions
into an engine-compatible format.

It may **not**:

- redesign a locked character,
- replace a locked environment,
- reinterpret Director intent,
- change approved camera direction,
- alter approved performance,
- invent missing locked creative decisions,
- silently switch generation engines,
- modify an upstream Master.
"""
            )

    with app:
        from joat_managed_generation import add_managed_generation_api
        add_managed_generation_api('supervisor')

    return app


if __name__ == "__main__":
    demo = build_app()

    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )
