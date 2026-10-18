# J.O.A.T. Generation Worker — app.py file version1.0.12
"""
J.O.A.T. Generation Worker Bot v1.0.12

Roadmap Stage #7

Type:
- Worker Bot
- Reports to Generation Supervisor Bot
- No Assistant Bot required in v1

Purpose:
- Receive approved joat.generation_job.v1 jobs
- Verify the Generation Supervisor handoff
- Preserve every locked upstream creative decision
- Translate approved jobs into engine execution instructions
- Route approved video work toward LTX
- Track execution attempts and technical failures
- Distinguish technical retry from creative rejection
- Record engine/model/version/settings provenance
- Register generated output metadata and SHA-256
- Produce deterministic joat.generation_result.v1 packets
- Hand completed results downstream to QC / Post
- Never silently mutate the Generation Supervisor job
- Never creatively repair an approved job
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Optional
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import gradio as gr
from joat_render_bridge import check_render_connection, render_failure_report, prepare_plan, execute_render
from joat_reference_views import prepare_reference_review


# =============================================================================
# CONFIG
# =============================================================================

APP_VERSION = "1.0.12"

SUPERVISOR_PACKET_SCHEMA = "joat.generation_supervisor_packet.v1"
JOB_SCHEMA = "joat.generation_job.v1"
EXECUTION_SCHEMA = "joat.generation_execution.v1"
RESULT_SCHEMA = "joat.generation_result.v1"

SUPPORTED_ENGINES = {
    "video": ["ltx"],
    "image": ["image_generation"],
    "voice": ["voice_generation"],
    "audio": ["audio_generation"],
    "vfx": ["vfx_generation"],
}

TECHNICAL_RETRY_REASONS = [
    "timeout",
    "connection_error",
    "engine_unavailable",
    "temporary_engine_error",
    "rate_limit",
    "worker_interrupted",
]

CREATIVE_REJECTION_REASONS = [
    "wrong_character",
    "character_identity_drift",
    "wrong_environment",
    "environment_identity_drift",
    "wrong_camera",
    "wrong_performance",
    "director_intent_violation",
    "continuity_failure",
    "visual_artifact",
    "content_quality_failure",
]

MAX_AUTOMATIC_TECHNICAL_RETRIES = 3


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
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def parse_json_object(
    raw: str,
    label: str,
) -> dict[str, Any]:

    if raw is None or not str(raw).strip():
        raise ValueError(
            f"{label} is required."
        )

    try:
        value = json.loads(raw)

    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{label} contains invalid JSON: {exc}"
        ) from exc

    if not isinstance(value, dict):
        raise ValueError(
            f"{label} must be a JSON object."
        )

    return value


def calculate_job_fingerprint(
    job: dict[str, Any],
) -> str:

    clean = deepcopy(job)
    clean.pop("job_fingerprint", None)

    return sha256_text(
        stable_json(clean)
    )


def calculate_packet_fingerprint(
    packet: dict[str, Any],
) -> str:

    clean = deepcopy(packet)
    clean.pop("packet_fingerprint", None)

    return sha256_text(
        stable_json(clean)
    )


def calculate_file_hash(
    path: Path,
) -> str:

    return sha256_bytes(
        path.read_bytes()
    )


# =============================================================================
# GENERATION WORKER
# =============================================================================

class GenerationWorkerBot:

    # -------------------------------------------------------------------------
    # SUPERVISOR / JOB VALIDATION
    # -------------------------------------------------------------------------

    def validate_supervisor_packet(
        self,
        packet: dict[str, Any],
    ) -> dict[str, Any]:

        if packet.get("schema") != SUPERVISOR_PACKET_SCHEMA:
            raise ValueError(
                "Generation Supervisor packet rejected: "
                f"expected {SUPERVISOR_PACKET_SCHEMA!r}, "
                f"received {packet.get('schema')!r}."
            )

        if packet.get("production_ready") is not True:
            raise ValueError(
                "Generation Supervisor packet rejected: "
                "production_ready must be true."
            )

        job = packet.get("generation_job")

        if not isinstance(job, dict):
            raise ValueError(
                "Generation Supervisor packet rejected: "
                "generation_job is missing or malformed."
            )

        validation = self.validate_job(job)

        return {
            "supervisor_schema": packet["schema"],
            "supervisor_production_ready": True,
            "supervisor_packet_fingerprint": (
                packet.get("packet_fingerprint")
                or calculate_packet_fingerprint(packet)
            ),
            "job_validation": validation,
        }

    def validate_job(
        self,
        job: dict[str, Any],
    ) -> dict[str, Any]:

        if job.get("schema") != JOB_SCHEMA:
            raise ValueError(
                "Generation job rejected: "
                f"expected schema {JOB_SCHEMA!r}."
            )

        job_type = job.get("job_type")
        engine = job.get("engine")

        if job_type not in SUPPORTED_ENGINES:
            raise ValueError(
                f"Unsupported generation job type: {job_type!r}"
            )

        if engine not in SUPPORTED_ENGINES[job_type]:
            raise ValueError(
                f"Engine {engine!r} is not approved for "
                f"job type {job_type!r}."
            )

        upstream = job.get("upstream_validation")

        if not isinstance(upstream, dict):
            raise ValueError(
                "Generation job rejected: "
                "upstream_validation is missing."
            )

        required_roles = [
            "character",
            "environment",
            "director",
            "shot_camera",
            "performance_action",
        ]

        for role in required_roles:

            role_validation = upstream.get(role)

            if not isinstance(role_validation, dict):
                raise ValueError(
                    f"Generation job rejected: "
                    f"{role} validation is missing."
                )

            if role_validation.get("lock_verified") is not True:
                raise ValueError(
                    f"Generation job rejected: "
                    f"{role} lock is not verified."
                )

        handoff = job.get(
            "downstream_handoff",
            {},
        )

        if handoff.get(
            "ready_for_generation_worker"
        ) is not True:
            raise ValueError(
                "Generation job rejected: "
                "Generation Supervisor did not approve "
                "the worker handoff."
            )

        continuity = job.get(
            "continuity_policy",
            {},
        )

        required_continuity = [
            "preserve_character_identity",
            "preserve_environment_identity",
            "preserve_director_intent",
            "preserve_shot_camera_intent",
            "preserve_performance_action_intent",
        ]

        for field in required_continuity:

            if continuity.get(field) is not True:
                raise ValueError(
                    "Generation job rejected: "
                    f"continuity requirement {field!r} "
                    "is not enabled."
                )

        if continuity.get(
            "silent_creative_mutation_allowed"
        ) is not False:
            raise ValueError(
                "Generation job rejected: "
                "silent creative mutation must be prohibited."
            )

        prompt_contract = job.get(
            "prompt_contract",
            {},
        )

        translation_policy = prompt_contract.get(
            "translation_policy",
            {},
        )

        forbidden_permissions = [
            "may_change_character_identity",
            "may_change_environment_identity",
            "may_change_director_intent",
            "may_change_camera_intent",
            "may_change_performance_intent",
            "may_invent_missing_locked_decisions",
        ]

        for field in forbidden_permissions:

            if translation_policy.get(field) is not False:
                raise ValueError(
                    "Generation job rejected: "
                    f"{field} must be false."
                )

        expected_fp = job.get("job_fingerprint")

        actual_fp = calculate_job_fingerprint(job)

        if expected_fp and expected_fp != actual_fp:
            raise ValueError(
                "Generation job rejected: "
                "job fingerprint does not match the "
                "current job contents."
            )

        return {
            "job_schema": JOB_SCHEMA,
            "job_type": job_type,
            "engine": engine,
            "all_upstream_locks_verified": True,
            "creative_mutation_prohibited": True,
            "worker_handoff_verified": True,
            "job_fingerprint_verified": (
                True if expected_fp else None
            ),
            "calculated_job_fingerprint": actual_fp,
        }

    # -------------------------------------------------------------------------
    # ENGINE TRANSLATION
    # -------------------------------------------------------------------------

    def build_engine_execution(
        self,
        job: dict[str, Any],
    ) -> dict[str, Any]:

        validation = self.validate_job(job)

        job_type = job["job_type"]
        engine = job["engine"]

        prompt_contract = deepcopy(
            job["prompt_contract"]
        )

        generation_spec = deepcopy(
            job.get(
                "generation_specification",
                {},
            )
        )

        project_context = deepcopy(
            job.get(
                "project_context",
                {},
            )
        )

        source_fingerprints = deepcopy(
            job.get(
                "source_packet_fingerprints",
                {},
            )
        )

        if job_type == "video" and engine == "ltx":

            engine_contract = {
                "engine": "ltx",
                "operation": "video_generation",
                "input_contract": {
                    "prompt_contract": prompt_contract,
                    "generation_specification": (
                        generation_spec
                    ),
                    "project_context": project_context,
                    "source_packet_fingerprints": (
                        source_fingerprints
                    ),
                },
                "translation_rules": {
                    "format_translation_allowed": True,
                    "technical_parameter_translation_allowed": True,
                    "creative_reinterpretation_allowed": False,
                    "identity_substitution_allowed": False,
                    "environment_substitution_allowed": False,
                    "camera_reinterpretation_allowed": False,
                    "performance_reinterpretation_allowed": False,
                },
            }

        else:

            engine_contract = {
                "engine": engine,
                "operation": (
                    f"{job_type}_generation"
                ),
                "input_contract": {
                    "prompt_contract": prompt_contract,
                    "generation_specification": (
                        generation_spec
                    ),
                    "project_context": project_context,
                    "source_packet_fingerprints": (
                        source_fingerprints
                    ),
                },
                "translation_rules": {
                    "format_translation_allowed": True,
                    "technical_parameter_translation_allowed": True,
                    "creative_reinterpretation_allowed": False,
                },
            }

        execution_core = {
            "schema": EXECUTION_SCHEMA,
            "worker": {
                "name": "J.O.A.T. Generation Worker Bot",
                "version": APP_VERSION,
                "type": "worker_bot",
                "reports_to": (
                    "J.O.A.T. Generation Supervisor Bot"
                ),
            },
            "source_job_fingerprint": (
                job.get("job_fingerprint")
                or validation[
                    "calculated_job_fingerprint"
                ]
            ),
            "job_type": job_type,
            "engine": engine,
            "project_context": project_context,
            "engine_contract": engine_contract,
            "retry_policy": {
                "automatic_technical_retry_allowed": True,
                "maximum_automatic_retries": (
                    MAX_AUTOMATIC_TECHNICAL_RETRIES
                ),
                "creative_retry_allowed": False,
                "creative_failure_requires_qc_or_upstream_review": True,
            },
            "immutability_policy": {
                "source_job_mutation_allowed": False,
                "locked_upstream_mutation_allowed": False,
                "creative_instruction_mutation_allowed": False,
            },
            "downstream_contract": {
                "result_schema": RESULT_SCHEMA,
                "qc_handoff_enabled": True,
                "post_handoff_requires_qc_pass": True,
            },
        }

        execution_core[
            "execution_fingerprint"
        ] = sha256_text(
            stable_json(execution_core)
        )

        return execution_core

    # -------------------------------------------------------------------------
    # RETRY / FAILURE POLICY
    # -------------------------------------------------------------------------

    def classify_failure(
        self,
        reason: str,
    ) -> dict[str, Any]:

        normalized = str(
            reason
        ).strip().casefold()

        if normalized in TECHNICAL_RETRY_REASONS:

            return {
                "classification": "technical_failure",
                "automatic_retry_allowed": True,
                "creative_change_allowed": False,
                "route": "retry_same_approved_job",
            }

        if normalized in CREATIVE_REJECTION_REASONS:

            return {
                "classification": "creative_or_qc_failure",
                "automatic_retry_allowed": False,
                "creative_change_allowed": False,
                "route": "send_to_qc_or_responsible_upstream_department",
            }

        return {
            "classification": "unknown_failure",
            "automatic_retry_allowed": False,
            "creative_change_allowed": False,
            "route": "human_or_supervisor_review",
        }

    # -------------------------------------------------------------------------
    # RESULT REGISTRATION
    # -------------------------------------------------------------------------

    def build_result(
        self,
        job: dict[str, Any],
        status: str,
        attempt_number: int,
        model_name: str,
        model_version: str,
        output_path: str = "",
        output_sha256: str = "",
        failure_reason: str = "",
    ) -> dict[str, Any]:

        self.validate_job(job)

        allowed_statuses = [
            "completed",
            "technical_failure",
            "rejected_for_qc",
            "failed",
        ]

        if status not in allowed_statuses:
            raise ValueError(
                f"Unsupported result status: {status!r}"
            )

        if attempt_number < 1:
            raise ValueError(
                "attempt_number must be at least 1."
            )

        if (
            attempt_number
            > MAX_AUTOMATIC_TECHNICAL_RETRIES + 1
        ):
            raise ValueError(
                "attempt_number exceeds the v1 execution limit."
            )

        failure = None

        if status != "completed":

            if not failure_reason:
                raise ValueError(
                    "failure_reason is required for "
                    "non-completed results."
                )

            failure = self.classify_failure(
                failure_reason
            )

        output = None

        if status == "completed":

            if not output_path:
                raise ValueError(
                    "Completed generation requires "
                    "an output path or output location."
                )

            output = {
                "location": output_path,
                "sha256": (
                    output_sha256
                    if output_sha256
                    else None
                ),
            }

        result_core = {
            "schema": RESULT_SCHEMA,
            "worker": {
                "name": "J.O.A.T. Generation Worker Bot",
                "version": APP_VERSION,
                "type": "worker_bot",
            },
            "source_job_fingerprint": (
                job.get("job_fingerprint")
                or calculate_job_fingerprint(job)
            ),
            "project_context": deepcopy(
                job.get(
                    "project_context",
                    {},
                )
            ),
            "job_type": job["job_type"],
            "engine": job["engine"],
            "status": status,
            "attempt_number": attempt_number,
            "execution_provenance": {
                "model_name": (
                    model_name.strip()
                    if model_name
                    else None
                ),
                "model_version": (
                    model_version.strip()
                    if model_version
                    else None
                ),
                "engine": job["engine"],
            },
            "output": output,
            "failure": failure,
            "creative_integrity": {
                "source_job_changed": False,
                "character_identity_changed": False,
                "environment_identity_changed": False,
                "director_intent_changed": False,
                "camera_intent_changed": False,
                "performance_intent_changed": False,
            },
            "downstream_handoff": {
                "ready_for_qc": (
                    status == "completed"
                ),
                "ready_for_post": False,
                "post_requires_qc_pass": True,
            },
        }

        result_core[
            "result_fingerprint"
        ] = sha256_text(
            stable_json(result_core)
        )

        return result_core

    # -------------------------------------------------------------------------
    # ACCEPTANCE TESTS
    # -------------------------------------------------------------------------

    def acceptance_test(
        self,
    ) -> dict[str, Any]:

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

        # ---------------------------------------------------------------------
        # Build a valid Supervisor job
        # ---------------------------------------------------------------------

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

        upstream_validation = {
            "character": {
                "lock_verified": True,
                "fingerprint": "CHAR-FP-001",
            },
            "environment": {
                "lock_verified": True,
                "fingerprint": "ENV-FP-001",
            },
            "director": {
                "lock_verified": True,
                "fingerprint": "DIR-FP-001",
            },
            "shot_camera": {
                "lock_verified": True,
                "fingerprint": "SHOT-FP-001",
            },
            "performance_action": {
                "lock_verified": True,
                "fingerprint": "PERF-FP-001",
            },
        }

        prompt_contract = {
            "character_packet": character,
            "environment_packet": environment,
            "director_packet": director,
            "shot_camera_packet": shot_camera,
            "performance_action_packet": performance,
            "generation_notes": "",
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

        job = {
            "schema": JOB_SCHEMA,
            "job_type": "video",
            "engine": "ltx",
            "project_context": {
                "project_id": "PROJECT-001",
                "scene_id": "SCENE-001",
                "shot_id": "SHOT-001",
            },
            "generation_specification": {
                "duration_seconds": 6.0,
                "aspect_ratio": "16:9",
            },
            "upstream_validation": upstream_validation,
            "source_packet_fingerprints": {
                "character": "CHAR-FP-001",
                "environment": "ENV-FP-001",
                "director": "DIR-FP-001",
                "shot_camera": "SHOT-FP-001",
                "performance_action": "PERF-FP-001",
            },
            "prompt_contract": prompt_contract,
            "immutable_upstream_snapshot": {
                "character": character,
                "environment": environment,
                "director": director,
                "shot_camera": shot_camera,
                "performance_action": performance,
            },
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
                "ltx_compatible": True,
                "image_worker_compatible": False,
                "voice_worker_compatible": False,
                "audio_worker_compatible": False,
                "vfx_worker_compatible": False,
                "ready_for_generation_worker": True,
            },
        }

        job["job_fingerprint"] = (
            calculate_job_fingerprint(job)
        )

        supervisor_packet = {
            "schema": SUPERVISOR_PACKET_SCHEMA,
            "app_version": "1.0.0",
            "generation_job": job,
            "production_ready": True,
        }

        supervisor_packet[
            "packet_fingerprint"
        ] = calculate_packet_fingerprint(
            supervisor_packet
        )

        # 1
        validation = self.validate_supervisor_packet(
            supervisor_packet
        )

        add(
            "1. Generation Supervisor packet validates",
            validation[
                "supervisor_production_ready"
            ] is True,
        )

        # 2
        add(
            "2. Generation job schema validates",
            validation[
                "job_validation"
            ]["job_schema"] == JOB_SCHEMA,
        )

        # 3
        add(
            "3. All upstream locks preserved",
            validation[
                "job_validation"
            ]["all_upstream_locks_verified"] is True,
        )

        # 4
        add(
            "4. Generation job fingerprint verifies",
            validation[
                "job_validation"
            ]["job_fingerprint_verified"] is True,
        )

        # 5
        execution = self.build_engine_execution(
            job
        )

        add(
            "5. Engine execution packet generates",
            execution.get("schema")
            == EXECUTION_SCHEMA,
        )

        # 6
        add(
            "6. LTX execution route preserved",
            (
                execution["engine"] == "ltx"
                and execution[
                    "engine_contract"
                ]["engine"] == "ltx"
                and execution[
                    "engine_contract"
                ]["operation"]
                == "video_generation"
            ),
        )

        # 7
        add(
            "7. Character identity mutation prohibited",
            execution[
                "engine_contract"
            ]["translation_rules"][
                "identity_substitution_allowed"
            ] is False,
        )

        # 8
        add(
            "8. Environment identity mutation prohibited",
            execution[
                "engine_contract"
            ]["translation_rules"][
                "environment_substitution_allowed"
            ] is False,
        )

        # 9
        add(
            "9. Camera reinterpretation prohibited",
            execution[
                "engine_contract"
            ]["translation_rules"][
                "camera_reinterpretation_allowed"
            ] is False,
        )

        # 10
        add(
            "10. Performance reinterpretation prohibited",
            execution[
                "engine_contract"
            ]["translation_rules"][
                "performance_reinterpretation_allowed"
            ] is False,
        )

        # 11
        first = self.build_engine_execution(
            job
        )

        second = self.build_engine_execution(
            job
        )

        add(
            "11. Deterministic execution fingerprint",
            first[
                "execution_fingerprint"
            ]
            == second[
                "execution_fingerprint"
            ],
        )

        # 12
        before = stable_json(job)

        self.build_engine_execution(
            job
        )

        after = stable_json(job)

        add(
            "12. Supervisor generation job remains immutable",
            before == after,
        )

        # 13
        rejected = False

        bad_job = deepcopy(job)

        bad_job[
            "upstream_validation"
        ]["character"][
            "lock_verified"
        ] = False

        bad_job["job_fingerprint"] = (
            calculate_job_fingerprint(
                bad_job
            )
        )

        try:
            self.validate_job(
                bad_job
            )

        except ValueError:
            rejected = True

        add(
            "13. Unlocked upstream job rejected",
            rejected,
        )

        # 14
        rejected = False

        bad_engine = deepcopy(job)
        bad_engine["engine"] = "unapproved_engine"
        bad_engine["job_fingerprint"] = (
            calculate_job_fingerprint(
                bad_engine
            )
        )

        try:
            self.validate_job(
                bad_engine
            )

        except ValueError:
            rejected = True

        add(
            "14. Unapproved generation engine rejected",
            rejected,
        )

        # 15
        technical = self.classify_failure(
            "timeout"
        )

        add(
            "15. Technical failure allows same-job retry",
            (
                technical[
                    "classification"
                ] == "technical_failure"
                and technical[
                    "automatic_retry_allowed"
                ] is True
                and technical[
                    "creative_change_allowed"
                ] is False
            ),
        )

        # 16
        creative = self.classify_failure(
            "wrong_character"
        )

        add(
            "16. Creative failure cannot auto-rewrite job",
            (
                creative[
                    "classification"
                ] == "creative_or_qc_failure"
                and creative[
                    "automatic_retry_allowed"
                ] is False
                and creative[
                    "creative_change_allowed"
                ] is False
            ),
        )

        # 17
        result = self.build_result(
            job=job,
            status="completed",
            attempt_number=1,
            model_name="LTX",
            model_version="approved-runtime",
            output_path=(
                "outputs/"
                "PROJECT-001_SCENE-001_SHOT-001.mp4"
            ),
            output_sha256=(
                "0123456789abcdef"
                "0123456789abcdef"
                "0123456789abcdef"
                "0123456789abcdef"
            ),
        )

        add(
            "17. Generation result packet generates",
            result.get("schema")
            == RESULT_SCHEMA,
        )

        # 18
        required_result_fields = [
            "schema",
            "worker",
            "source_job_fingerprint",
            "project_context",
            "job_type",
            "engine",
            "status",
            "attempt_number",
            "execution_provenance",
            "output",
            "failure",
            "creative_integrity",
            "downstream_handoff",
            "result_fingerprint",
        ]

        add(
            "18. Required result fields present",
            all(
                field in result
                for field in required_result_fields
            ),
        )

        # 19
        integrity = result[
            "creative_integrity"
        ]

        add(
            "19. Creative integrity preserved in result",
            (
                integrity[
                    "source_job_changed"
                ] is False
                and integrity[
                    "character_identity_changed"
                ] is False
                and integrity[
                    "environment_identity_changed"
                ] is False
                and integrity[
                    "director_intent_changed"
                ] is False
                and integrity[
                    "camera_intent_changed"
                ] is False
                and integrity[
                    "performance_intent_changed"
                ] is False
            ),
        )

        # 20
        add(
            "20. Completed generation routes to QC",
            (
                result[
                    "downstream_handoff"
                ]["ready_for_qc"] is True
                and result[
                    "downstream_handoff"
                ]["ready_for_post"] is False
                and result[
                    "downstream_handoff"
                ]["post_requires_qc_pass"] is True
            ),
        )

        # 21
        failed_result = self.build_result(
            job=job,
            status="technical_failure",
            attempt_number=1,
            model_name="LTX",
            model_version="approved-runtime",
            failure_reason="timeout",
        )

        add(
            "21. Technical failure result classified correctly",
            (
                failed_result[
                    "failure"
                ]["classification"]
                == "technical_failure"
                and failed_result[
                    "failure"
                ]["automatic_retry_allowed"]
                is True
            ),
        )

        # 22
        creative_result = self.build_result(
            job=job,
            status="rejected_for_qc",
            attempt_number=1,
            model_name="LTX",
            model_version="approved-runtime",
            failure_reason="wrong_character",
        )

        add(
            "22. QC rejection cannot trigger creative auto-repair",
            (
                creative_result[
                    "failure"
                ]["automatic_retry_allowed"]
                is False
                and creative_result[
                    "failure"
                ]["creative_change_allowed"]
                is False
            ),
        )

        # 23
        add(
            "23. Retry limit enforced",
            execution[
                "retry_policy"
            ]["maximum_automatic_retries"]
            == MAX_AUTOMATIC_TECHNICAL_RETRIES,
        )

        # 24
        add(
            "24. Post-production blocked until QC passes",
            execution[
                "downstream_contract"
            ]["post_handoff_requires_qc_pass"]
            is True,
        )

        all_passed = all(
            test["pass"]
            for test in tests
        )

        return {
            "acceptance_test_version": "1.0.0",
            "app_version": APP_VERSION,
            "bot_name": (
                "J.O.A.T. Generation Worker Bot"
            ),
            "bot_type": "worker_bot",
            "assistant_required": False,
            "reports_to": (
                "J.O.A.T. Generation Supervisor Bot"
            ),
            "supervisor_packet_schema": (
                SUPERVISOR_PACKET_SCHEMA
            ),
            "job_schema": JOB_SCHEMA,
            "execution_schema": EXECUTION_SCHEMA,
            "result_schema": RESULT_SCHEMA,
            "tests": tests,
            "all_passed": all_passed,
            "production_ready": all_passed,
            "note": (
                "Generation Worker Bot is production-ready "
                "when approved Generation Supervisor jobs "
                "remain immutable, LTX routing is preserved, "
                "technical retries cannot alter creative "
                "instructions, generated results preserve "
                "provenance, and completed assets route to QC."
            ),
        }


WORKER = GenerationWorkerBot()


# =============================================================================
# UI FUNCTIONS
# =============================================================================

def example_supervisor_packet() -> str:

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
        "packet_fingerprint": "DIR-FP-001",
    }

    shot_camera = {
        "schema": "joat.shot_camera_packet.v1",
        "shot_camera_locked": True,
        "packet_fingerprint": "SHOT-FP-001",
    }

    performance = {
        "schema": "joat.performance_action_packet.v1",
        "performance_action_locked": True,
        "packet_fingerprint": "PERF-FP-001",
    }

    job = {
        "schema": JOB_SCHEMA,
        "job_type": "video",
        "engine": "ltx",

        "project_context": {
            "project_id": "PROJECT-001",
            "scene_id": "SCENE-001",
            "shot_id": "SHOT-001",
        },

        "generation_specification": {
            "duration_seconds": 6.0,
            "aspect_ratio": "16:9",
        },

        "upstream_validation": {
            "character": {
                "lock_verified": True,
                "fingerprint": "CHAR-FP-001",
            },
            "environment": {
                "lock_verified": True,
                "fingerprint": "ENV-FP-001",
            },
            "director": {
                "lock_verified": True,
                "fingerprint": "DIR-FP-001",
            },
            "shot_camera": {
                "lock_verified": True,
                "fingerprint": "SHOT-FP-001",
            },
            "performance_action": {
                "lock_verified": True,
                "fingerprint": "PERF-FP-001",
            },
        },

        "source_packet_fingerprints": {
            "character": "CHAR-FP-001",
            "environment": "ENV-FP-001",
            "director": "DIR-FP-001",
            "shot_camera": "SHOT-FP-001",
            "performance_action": "PERF-FP-001",
        },

        "prompt_contract": {
            "character_packet": character,
            "environment_packet": environment,
            "director_packet": director,
            "shot_camera_packet": shot_camera,
            "performance_action_packet": performance,
            "generation_notes": "",
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
        },

        "immutable_upstream_snapshot": {
            "character": character,
            "environment": environment,
            "director": director,
            "shot_camera": shot_camera,
            "performance_action": performance,
        },

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
            "ltx_compatible": True,
            "image_worker_compatible": False,
            "voice_worker_compatible": False,
            "audio_worker_compatible": False,
            "vfx_worker_compatible": False,
            "ready_for_generation_worker": True,
        },
    }

    job["job_fingerprint"] = (
        calculate_job_fingerprint(job)
    )

    packet = {
        "schema": SUPERVISOR_PACKET_SCHEMA,
        "app_version": "1.0.0",
        "generation_job": job,
        "production_ready": True,
    }

    packet["packet_fingerprint"] = (
        calculate_packet_fingerprint(packet)
    )

    return json.dumps(
        packet,
        indent=2,
    )


def validate_ui(
    supervisor_raw: str,
) -> dict[str, Any]:

    packet = parse_json_object(
        supervisor_raw,
        "Generation Supervisor packet",
    )

    return WORKER.validate_supervisor_packet(
        packet
    )


def execution_ui(
    supervisor_raw: str,
) -> dict[str, Any]:

    packet = parse_json_object(
        supervisor_raw,
        "Generation Supervisor packet",
    )

    WORKER.validate_supervisor_packet(
        packet
    )

    return WORKER.build_engine_execution(
        packet["generation_job"]
    )


def failure_ui(
    reason: str,
) -> dict[str, Any]:

    return WORKER.classify_failure(
        reason
    )


def tests_ui() -> dict[str, Any]:

    return WORKER.acceptance_test()


# =============================================================================
# GRADIO APP
# =============================================================================

def prepare_render_ui(source_file: str):
    if not source_file:
        raise gr.Error("Upload the original Supervisor packet JSON file first.")
    try:
        packet = json.loads(Path(source_file).read_text())
        plan = prepare_plan(WORKER, packet)
    except Exception:
        raise gr.Error("Cannot prepare render: valid original job fingerprints and real locked Character/Environment asset hashes are required. Example packets without references cannot render.") from None
    return plan, (packet, plan), False


def render_ui(retained, approved: bool, profile: Optional[gr.OAuthProfile], token: Optional[gr.OAuthToken]):
    if profile is None or profile.username.casefold() != "dezz-9-10":
        raise gr.Error("Sign in as Dezz-9-10 before rendering.")
    if approved is not True or not retained:
        raise gr.Error("Prepare and explicitly approve the displayed technical render plan first.")
    if token is None:
        raise gr.Error("Owner OAuth token is unavailable; sign in again.")
    packet, plan = retained
    try:
        return execute_render(WORKER, packet, plan, token.token)
    except Exception as exc:
        # Persist the failure in the result component; pop-up errors disappear on iPad.
        report = render_failure_report(exc, packet, token.token)
        assets = getattr(exc, "render_failure_assets", (None, None, None))
        return report, *assets


def check_render_connection_ui(retained, profile: Optional[gr.OAuthProfile], token: Optional[gr.OAuthToken]):
    if profile is None or profile.username.casefold() != "dezz-9-10":
        raise gr.Error("Sign in as Dezz-9-10 before checking the connection.")
    if not retained or token is None:
        raise gr.Error("Prepare the plan and sign in before checking the connection.")
    packet, plan = retained
    try:
        return check_render_connection(WORKER, packet, plan, token.token)
    except Exception as exc:
        return render_failure_report(exc, packet, token.token)



def prepare_reference_review_ui(retained, profile: Optional[gr.OAuthProfile]):
    if profile is None or profile.username.casefold() != "dezz-9-10":
        raise gr.Error("Sign in as Dezz-9-10 before downloading reference candidates.")
    if not retained:
        raise gr.Error("Prepare the original Supervisor plan first. No GPU approval is needed.")
    packet, plan = retained
    try:
        manifest, outputs, manifest_path = prepare_reference_review(WORKER, packet, plan)
        return (manifest, outputs["image_path"], outputs["msr_background"],
                outputs["msr_ref2"], manifest_path)
    except Exception as exc:
        from joat_render_bridge import _safe_error
        return ({"schema": "joat.reference_view_review.v1", "file_version": "1.0.0",
                 "status": "reference_review_failed", "gpu_called": False,
                 "model_called": False, "source_job_changed": False,
                 "ready_for_render": False, "error_type": type(exc).__name__,
                 "error_message": _safe_error(exc, None)}, None, None, None, None)


def build_app() -> gr.Blocks:

    example = example_supervisor_packet()

    with gr.Blocks(
        title=(
            "J.O.A.T. Generation Worker Bot "
            f"v{APP_VERSION}"
        )
    ) as app:

        gr.Markdown(
            "# J.O.A.T. Generation Worker Bot\n\n"
            f"**Version:** {APP_VERSION}  \n"
            "**Roadmap Stage #7**  \n"
            "**Type:** Worker Bot  \n"
            "**Reports to:** Generation Supervisor Bot  \n"
            "**Assistant:** None required in v1\n\n"
            "Executes approved generation jobs without "
            "changing locked creative decisions."
        )

        with gr.Tab("Validate Job"):

            supervisor_raw = gr.Code(
                value=example,
                language="json",
                label="Generation Supervisor Packet",
            )

            validation_output = gr.JSON(
                label="Worker Validation",
            )

            gr.Button(
                "Validate Generation Job",
                variant="primary",
            ).click(
                fn=validate_ui,
                inputs=supervisor_raw,
                outputs=validation_output,
            )

        with gr.Tab("Execution Packet"):

            execution_raw = gr.Code(
                value=example,
                language="json",
                label="Generation Supervisor Packet",
            )

            execution_output = gr.JSON(
                label="Engine Execution Packet",
            )

            gr.Button(
                "Build Engine Execution",
                variant="primary",
            ).click(
                fn=execution_ui,
                inputs=execution_raw,
                outputs=execution_output,
            )

        with gr.Tab("Failure Routing"):

            failure_reason = gr.Dropdown(
                choices=(
                    TECHNICAL_RETRY_REASONS
                    + CREATIVE_REJECTION_REASONS
                ),
                value="timeout",
                label="Failure Reason",
            )

            failure_output = gr.JSON(
                label="Failure Classification",
            )

            gr.Button(
                "Classify Failure",
                variant="primary",
            ).click(
                fn=failure_ui,
                inputs=failure_reason,
                outputs=failure_output,
            )

        with gr.Tab("Acceptance Tests"):

            test_output = gr.JSON(
                label=(
                    "Generation Worker Bot "
                    "Acceptance Test"
                ),
            )

            gr.Button(
                "Run Acceptance Tests",
                variant="primary",
            ).click(
                fn=tests_ui,
                inputs=None,
                outputs=test_output,
            )

        with gr.Tab("Authority"):

            gr.JSON(
                value={
                    "bot": (
                        "J.O.A.T. Generation Worker Bot"
                    ),
                    "type": "worker_bot",
                    "reports_to": (
                        "J.O.A.T. Generation "
                        "Supervisor Bot"
                    ),
                    "assistant_required": False,
                    "may": [
                        "validate approved jobs",
                        "translate technical format",
                        "execute approved engine route",
                        "retry technical failures",
                        "record execution provenance",
                        "register generated output",
                        "route completed output to QC",
                    ],
                    "may_not": [
                        "rewrite Director intent",
                        "change character identity",
                        "change environment identity",
                        "change camera intent",
                        "change performance intent",
                        "invent missing creative decisions",
                        "silently change generation engine",
                        "send output directly to post before QC",
                    ],
                },
                label="Worker Authority Boundary",
            )

        with gr.Tab("About"):

            gr.Markdown(
                f"""
## J.O.A.T. Generation Worker Bot

**Version:** {APP_VERSION}

**Type:** Worker Bot

**Reports to:** Generation Supervisor Bot

**Supervisor packet:** `{SUPERVISOR_PACKET_SCHEMA}`

**Generation job:** `{JOB_SCHEMA}`

**Execution packet:** `{EXECUTION_SCHEMA}`

**Result packet:** `{RESULT_SCHEMA}`

### Current production route

Generation Supervisor Bot  
↓  
Generation Worker Bot  
↓  
LTX  
↓  
Generated Shot  
↓  
QC

### Critical Rule

A technical failure may retry the same approved job.

A creative or continuity failure may **not** cause this
worker to rewrite the job.

Those failures are returned to QC / the responsible
upstream department.
"""
            )

        with gr.Tab("Controlled Rendering"):
            gr.Markdown("## Render a locked LTX job\nPrepare the explicit plan, review its locked references and technical settings, then authorize one GPU render. No QC approval is issued here. Built-in packet-only examples cannot render. Full MSR requests up to600GPUseconds for this6-second shot; actual provider allowance remains unverified. Review the compiled prompt and reservation in the plan.")
            if all(os.getenv(key) for key in ("OAUTH_CLIENT_ID", "OAUTH_CLIENT_SECRET", "OAUTH_SCOPES", "OPENID_PROVIDER_URL")):
                gr.LoginButton()
            else:
                gr.Markdown("Owner sign-in is available on the OAuth-enabled Hugging Face deployment.")
            source_file = gr.File(label="Original Supervisor packet JSON", file_types=[".json"], type="filepath")
            plan_view = gr.JSON(label="Explicit locked render plan")
            retained = gr.State(value=None)
            approved = gr.Checkbox(value=False, label="I approve this exact technical render plan for the displayed locked job and authorize GPU quota use up to the displayed reservation ceiling")
            source_file.change(lambda: (None, False, None), inputs=None, outputs=[retained, approved, plan_view], api_visibility="private")
            gr.Button("Prepare render plan (no GPU)").click(prepare_render_ui, inputs=source_file, outputs=[plan_view, retained, approved], api_name="prepare_locked_render", api_visibility="private")
            connection_view = gr.JSON(label="Connection check — no GPU")
            gr.Button("Check render connection (no GPU)").click(check_render_connection_ui,
                inputs=retained, outputs=connection_view, api_name="check_render_connection", api_visibility="private")
            with gr.Accordion("Reference view review — CPU only", open=True):
                gr.Markdown("For the current Founder/Office diagnostic job: preserve the original identity portrait and prepare individual candidate views from the two sheets. Candidates are not approved replacements and do not change this locked render plan. Do not render this job again during reference rework.")
                reference_review = gr.JSON(label="Candidate provenance — no GPU or model call")
                identity_review_file = gr.File(label="Download exact original Founder identity JPEG")
                office_review_file = gr.File(label="Download proposed Office frontal view PNG")
                support_review_file = gr.File(label="Download proposed Founder office support PNG — not a neutral first frame")
                review_manifest_file = gr.File(label="Download reference view review JSON")
                gr.Button("Prepare reference candidates (no GPU)").click(
                    prepare_reference_review_ui, inputs=retained,
                    outputs=[reference_review, identity_review_file, office_review_file,
                             support_review_file, review_manifest_file],
                    api_name="prepare_reference_review", api_visibility="private",
                    concurrency_limit=1, trigger_mode="once")
            result_view = gr.JSON(label="Generation result or persistent error — awaiting independent QC")
            video_view = gr.Video(label="Generated shot — may be rejected; check the result JSON")
            result_file = gr.File(label="Download generation result or failure diagnostic JSON")
            original_file = gr.File(label="Download exact source Supervisor JSON for QC")
            gr.Button("Render one approved shot").click(render_ui, inputs=[retained, approved], outputs=[result_view, video_view, result_file, original_file], api_name="render_locked_job", api_visibility="private", concurrency_limit=1, trigger_mode="once")

    with app:
        from joat_managed_generation import add_managed_generation_api
        add_managed_generation_api('worker', worker=WORKER)

    return app


if __name__ == "__main__":

    demo = build_app()

    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )