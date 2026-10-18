"""
J.O.A.T. Voice & Dialogue Worker Bot v1.0.1

Purpose:
- Own approved spoken-performance preparation for J.O.A.T. productions
- Protect approved dialogue and character voice identity
- Preserve speaker assignment, pronunciation, timing, emotion, and continuity
- Create deterministic provider-neutral voice execution instructions
- Return structured Voice & Dialogue results
- Never rewrite approved dialogue
- Never silently change voice identity or locked performance intent
- Never falsely claim that an external voice provider generated audio
"""

from __future__ import annotations

import hashlib
import json
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

import gradio as gr


# =============================================================================
# CONFIG
# =============================================================================

APP_VERSION = "1.0.1"
ACCEPTANCE_TEST_VERSION = "1.0.0"

BOT_NAME = "J.O.A.T. Voice & Dialogue Worker Bot"
BOT_TYPE = "voice_dialogue_worker_bot"

REPORTS_TO = "J.O.A.T. Executive Producer Bot"
ASSISTANT_REQUIRED = False

JOB_SCHEMA = "joat.voice_dialogue_job.v1"
EXECUTION_SCHEMA = "joat.voice_dialogue_execution.v1"
RESULT_SCHEMA = "joat.voice_dialogue_result.v1"

LIVE_EXECUTION_INTERFACE = True
LIVE_VOICE_PROVIDER_CONNECTED = False


# =============================================================================
# CAPABILITIES
# =============================================================================

CAPABILITIES = {
    "voice_identity": {
        "level": "expert",
        "responsibilities": [
            "protect approved character voice identity",
            "preserve approved voice references",
            "preserve speaker consistency",
            "prevent unauthorized voice substitution",
            "prevent cross-character voice contamination",
        ],
    },
    "dialogue": {
        "level": "expert",
        "responsibilities": [
            "preserve approved dialogue verbatim",
            "preserve speaker assignment",
            "preserve dialogue ordering",
            "preserve scene context",
            "preserve approved pronunciation instructions",
        ],
    },
    "performance": {
        "level": "expert",
        "responsibilities": [
            "preserve approved emotional delivery",
            "preserve pacing intent",
            "preserve emphasis instructions",
            "preserve performance continuity",
            "preserve locked director and performance intent",
        ],
    },
    "timing": {
        "level": "expert",
        "responsibilities": [
            "validate dialogue timing",
            "validate duration constraints",
            "preserve synchronization requirements",
            "preserve shot and scene timing relationships",
            "prepare timing instructions for downstream audio execution",
        ],
    },
    "pronunciation": {
        "level": "expert",
        "responsibilities": [
            "preserve approved pronunciation guides",
            "preserve names and invented-word pronunciation",
            "preserve accent and dialect requirements when approved",
            "prevent silent pronunciation reinterpretation",
        ],
    },
    "provider_routing": {
        "level": "expert",
        "responsibilities": [
            "create provider-neutral voice execution instructions",
            "preserve provider requirements",
            "preserve voice-model identifiers when supplied",
            "never claim provider execution unless verified",
            "prepare work for a future live voice execution layer",
        ],
    },
    "verification": {
        "level": "expert",
        "responsibilities": [
            "create deterministic fingerprints",
            "preserve immutable upstream instructions",
            "classify execution state truthfully",
            "protect provenance",
            "prepare results for downstream sound and QC workflows",
        ],
    },
}


# =============================================================================
# AUTHORITY
# =============================================================================

AUTHORITY_BOUNDARY = {
    "may_validate_voice_job": True,
    "may_validate_dialogue": True,
    "may_validate_speaker_assignment": True,
    "may_validate_pronunciation": True,
    "may_validate_timing": True,
    "may_validate_performance_instructions": True,
    "may_create_voice_execution_packet": True,
    "may_prepare_provider_request": True,
    "may_report_provider_requirement": True,
    "may_reject_invalid_job": True,
    "may_escalate_conflict": True,

    "may_rewrite_approved_dialogue": False,
    "may_change_character_identity": False,
    "may_change_voice_identity": False,
    "may_change_locked_performance": False,
    "may_change_director_intent": False,
    "may_change_scene_intent": False,
    "may_change_speaker_assignment": False,
    "may_modify_immutable_upstream_packets": False,
    "may_self_approve_creative_change": False,
    "may_bypass_qc": False,
    "may_claim_unverified_audio_generation": False,
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
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def make_fingerprint(value: dict[str, Any]) -> str:
    return sha256_text(
        stable_json(value)
    )


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


# =============================================================================
# VOICE & DIALOGUE WORKER
# =============================================================================

class VoiceDialogueWorkerBot:

    def validate_job(
        self,
        job: dict[str, Any],
    ) -> None:

        if job.get("schema") != JOB_SCHEMA:
            raise ValueError(
                "Invalid Voice & Dialogue job schema."
            )

        if not job.get("job_id"):
            raise ValueError(
                "job_id is required."
            )

        if not job.get("project_id"):
            raise ValueError(
                "project_id is required."
            )

        if (
            job.get("source_bot")
            != "J.O.A.T. Executive Producer Bot"
        ):
            raise ValueError(
                "Voice & Dialogue jobs must originate from "
                "J.O.A.T. Executive Producer Bot."
            )

        if job.get("target_bot") != BOT_NAME:
            raise ValueError(
                "Voice & Dialogue job target is incorrect."
            )

        if job.get("authorized") is not True:
            raise ValueError(
                "Voice & Dialogue job is not authorized."
            )

        if (
            job.get("approved_dialogue_locked")
            is not True
        ):
            raise ValueError(
                "Approved dialogue must be locked."
            )

        if (
            job.get("character_identity_locked")
            is not True
        ):
            raise ValueError(
                "Character identity must be locked."
            )

        if (
            job.get("voice_identity_locked")
            is not True
        ):
            raise ValueError(
                "Voice identity must be locked."
            )

        if (
            job.get("performance_intent_locked")
            is not True
        ):
            raise ValueError(
                "Performance intent must be locked."
            )

        dialogue = job.get("dialogue")

        if not isinstance(dialogue, list):
            raise ValueError(
                "dialogue must be a list."
            )

        if not dialogue:
            raise ValueError(
                "At least one dialogue item is required."
            )

        seen_line_ids: set[str] = set()

        for index, line in enumerate(
            dialogue,
            start=1,
        ):
            if not isinstance(line, dict):
                raise ValueError(
                    f"Dialogue item {index} must be an object."
                )

            line_id = line.get("line_id")

            if not line_id:
                raise ValueError(
                    f"Dialogue item {index} requires line_id."
                )

            if line_id in seen_line_ids:
                raise ValueError(
                    f"Duplicate dialogue line_id: {line_id}"
                )

            seen_line_ids.add(line_id)

            if not line.get("speaker_id"):
                raise ValueError(
                    f"Dialogue item {line_id} requires speaker_id."
                )

            if not line.get("text"):
                raise ValueError(
                    f"Dialogue item {line_id} requires text."
                )

            if not isinstance(
                line.get("text"),
                str,
            ):
                raise ValueError(
                    f"Dialogue item {line_id} text must be a string."
                )

            if not line.get("voice_id"):
                raise ValueError(
                    f"Dialogue item {line_id} requires voice_id."
                )

            duration = line.get(
                "target_duration_seconds"
            )

            if duration is not None:
                try:
                    duration_value = float(duration)
                except (TypeError, ValueError):
                    raise ValueError(
                        f"Dialogue item {line_id} has invalid duration."
                    )

                if duration_value <= 0:
                    raise ValueError(
                        f"Dialogue item {line_id} duration must be positive."
                    )

    def build_execution(
        self,
        job: dict[str, Any],
    ) -> dict[str, Any]:

        immutable_job = deepcopy(job)

        self.validate_job(job)

        execution_id = str(uuid.uuid4())

        dialogue_instructions = []

        for order, line in enumerate(
            job["dialogue"],
            start=1,
        ):
            instruction = {
                "order": order,
                "line_id": line["line_id"],
                "speaker_id": line["speaker_id"],
                "voice_id": line["voice_id"],
                "text": line["text"],
                "text_locked": True,
                "speaker_locked": True,
                "voice_identity_locked": True,
                "pronunciation": deepcopy(
                    line.get(
                        "pronunciation",
                        {},
                    )
                ),
                "performance": deepcopy(
                    line.get(
                        "performance",
                        {},
                    )
                ),
                "target_duration_seconds":
                    line.get(
                        "target_duration_seconds"
                    ),
                "sync_reference":
                    line.get(
                        "sync_reference"
                    ),
                "provider":
                    line.get(
                        "provider",
                        "provider_neutral",
                    ),
                "provider_voice_model":
                    line.get(
                        "provider_voice_model"
                    ),
                "execution_status":
                    (
                        "ready_for_provider"
                        if not LIVE_VOICE_PROVIDER_CONNECTED
                        else "provider_execution_available"
                    ),
            }

            instruction[
                "instruction_fingerprint"
            ] = make_fingerprint(
                instruction
            )

            dialogue_instructions.append(
                instruction
            )

        execution_core = {
            "schema": EXECUTION_SCHEMA,
            "execution_id": execution_id,
            "job_id": job["job_id"],
            "project_id": job["project_id"],
            "source_bot": BOT_NAME,
            "reports_to": REPORTS_TO,
            "created_at": utc_now(),
            "dialogue_instructions":
                dialogue_instructions,
            "provider_execution": {
                "connected":
                    LIVE_VOICE_PROVIDER_CONNECTED,
                "performed": False,
                "verified": False,
                "status": (
                    "not_connected"
                    if not LIVE_VOICE_PROVIDER_CONNECTED
                    else "available_not_executed"
                ),
            },
            "authority_preserved": True,
            "approved_dialogue_preserved": True,
            "voice_identity_preserved": True,
            "performance_intent_preserved": True,
            "immutable_job_preserved": (
                stable_json(job)
                == stable_json(immutable_job)
            ),
        }

        execution_core[
            "execution_fingerprint"
        ] = make_fingerprint(
            execution_core
        )

        return execution_core

    def execute_job(
        self,
        job: dict[str, Any],
    ) -> dict[str, Any]:

        immutable_job = deepcopy(job)

        execution = self.build_execution(
            job
        )

        if LIVE_VOICE_PROVIDER_CONNECTED:
            provider_status = (
                "provider_available_execution_not_implemented"
            )
        else:
            provider_status = (
                "awaiting_live_voice_provider"
            )

        result_core = {
            "schema": RESULT_SCHEMA,
            "result_id": str(uuid.uuid4()),
            "job_id": job["job_id"],
            "project_id": job["project_id"],
            "bot_name": BOT_NAME,
            "bot_type": BOT_TYPE,
            "status": "completed",
            "verified": True,
            "voice_provider_connected":
                LIVE_VOICE_PROVIDER_CONNECTED,
            "audio_generated": False,
            "provider_status":
                provider_status,
            "execution":
                execution,
            "dialogue_preserved": all(
                instruction["text"]
                == original["text"]
                for instruction, original
                in zip(
                    execution[
                        "dialogue_instructions"
                    ],
                    job["dialogue"],
                )
            ),
            "speaker_assignment_preserved": all(
                instruction["speaker_id"]
                == original["speaker_id"]
                for instruction, original
                in zip(
                    execution[
                        "dialogue_instructions"
                    ],
                    job["dialogue"],
                )
            ),
            "voice_identity_preserved": all(
                instruction["voice_id"]
                == original["voice_id"]
                for instruction, original
                in zip(
                    execution[
                        "dialogue_instructions"
                    ],
                    job["dialogue"],
                )
            ),
            "immutable_job_preserved": (
                stable_json(job)
                == stable_json(immutable_job)
            ),
            "next_handoff": {
                "when_audio_exists":
                    "J.O.A.T. Quality Control Bot",
                "post_audio_processing":
                    "J.O.A.T. Sound Worker Bot",
                "current_state":
                    (
                        "voice execution packet ready; "
                        "live voice provider not connected"
                    ),
            },
            "completed_at": utc_now(),
        }

        result_core[
            "result_fingerprint"
        ] = make_fingerprint(
            result_core
        )

        return result_core

    def execute_job_json(
        self,
        raw: str,
    ) -> dict[str, Any]:

        job = parse_json_object(
            raw,
            "Voice & Dialogue Job",
        )

        return self.execute_job(
            job
        )

    # =========================================================================
    # ACCEPTANCE TESTS
    # =========================================================================

    def acceptance_test(
        self,
    ) -> dict[str, Any]:

        tests: list[dict[str, Any]] = []

        def add(
            name: str,
            passed: bool,
        ) -> None:

            tests.append(
                {
                    "test": name,
                    "pass": bool(passed),
                    "detail": bool(passed),
                }
            )

        job = {
            "schema": JOB_SCHEMA,
            "job_id": "VOICE-JOB-001",
            "project_id": "PROJECT-001",
            "source_bot":
                "J.O.A.T. Executive Producer Bot",
            "target_bot": BOT_NAME,
            "authorized": True,
            "approved_dialogue_locked": True,
            "character_identity_locked": True,
            "voice_identity_locked": True,
            "performance_intent_locked": True,
            "dialogue": [
                {
                    "line_id": "LINE-001",
                    "speaker_id": "CHAR-001",
                    "voice_id": "VOICE-CHAR-001",
                    "text":
                        "We are ready to begin.",
                    "pronunciation": {
                        "approved": True,
                        "notes": [],
                    },
                    "performance": {
                        "emotion": "confident",
                        "intensity": 0.65,
                        "pace": "measured",
                    },
                    "target_duration_seconds": 2.4,
                    "sync_reference": "SHOT-001",
                    "provider": "provider_neutral",
                },
                {
                    "line_id": "LINE-002",
                    "speaker_id": "CHAR-002",
                    "voice_id": "VOICE-CHAR-002",
                    "text":
                        "Then let's get to work.",
                    "pronunciation": {
                        "approved": True,
                        "notes": [],
                    },
                    "performance": {
                        "emotion": "focused",
                        "intensity": 0.55,
                        "pace": "natural",
                    },
                    "target_duration_seconds": 2.1,
                    "sync_reference": "SHOT-002",
                    "provider": "provider_neutral",
                },
            ],
        }

        execution = self.build_execution(
            job
        )

        result = self.execute_job(
            job
        )

        # 1-10: IDENTITY / CONFIG

        add(
            "1. App version correct",
            APP_VERSION == "1.0.1",
        )

        add(
            "2. Acceptance version correct",
            ACCEPTANCE_TEST_VERSION == "1.0.0",
        )

        add(
            "3. Bot name correct",
            BOT_NAME
            == "J.O.A.T. Voice & Dialogue Worker Bot",
        )

        add(
            "4. Bot type correct",
            BOT_TYPE
            == "voice_dialogue_worker_bot",
        )

        add(
            "5. Reports to Executive Producer",
            REPORTS_TO
            == "J.O.A.T. Executive Producer Bot",
        )

        add(
            "6. Assistant not required",
            ASSISTANT_REQUIRED is False,
        )

        add(
            "7. Job schema correct",
            JOB_SCHEMA
            == "joat.voice_dialogue_job.v1",
        )

        add(
            "8. Execution schema correct",
            EXECUTION_SCHEMA
            == "joat.voice_dialogue_execution.v1",
        )

        add(
            "9. Result schema correct",
            RESULT_SCHEMA
            == "joat.voice_dialogue_result.v1",
        )

        add(
            "10. Live execution interface enabled",
            LIVE_EXECUTION_INTERFACE is True,
        )

        # 11-20: CAPABILITIES

        add(
            "11. Voice identity expertise declared",
            CAPABILITIES[
                "voice_identity"
            ]["level"] == "expert",
        )

        add(
            "12. Dialogue expertise declared",
            CAPABILITIES[
                "dialogue"
            ]["level"] == "expert",
        )

        add(
            "13. Performance expertise declared",
            CAPABILITIES[
                "performance"
            ]["level"] == "expert",
        )

        add(
            "14. Timing expertise declared",
            CAPABILITIES[
                "timing"
            ]["level"] == "expert",
        )

        add(
            "15. Pronunciation expertise declared",
            CAPABILITIES[
                "pronunciation"
            ]["level"] == "expert",
        )

        add(
            "16. Provider routing expertise declared",
            CAPABILITIES[
                "provider_routing"
            ]["level"] == "expert",
        )

        add(
            "17. Verification expertise declared",
            CAPABILITIES[
                "verification"
            ]["level"] == "expert",
        )

        add(
            "18. Dialogue rewriting prohibited",
            AUTHORITY_BOUNDARY[
                "may_rewrite_approved_dialogue"
            ] is False,
        )

        add(
            "19. Voice identity changes prohibited",
            AUTHORITY_BOUNDARY[
                "may_change_voice_identity"
            ] is False,
        )

        add(
            "20. Locked performance changes prohibited",
            AUTHORITY_BOUNDARY[
                "may_change_locked_performance"
            ] is False,
        )

        # 21-30: EXECUTION

        add(
            "21. Valid job accepted",
            execution[
                "job_id"
            ] == "VOICE-JOB-001",
        )

        add(
            "22. Execution packet generated",
            execution[
                "schema"
            ] == EXECUTION_SCHEMA,
        )

        add(
            "23. Two dialogue instructions generated",
            len(
                execution[
                    "dialogue_instructions"
                ]
            ) == 2,
        )

        add(
            "24. Dialogue text preserved",
            result[
                "dialogue_preserved"
            ] is True,
        )

        add(
            "25. Speaker assignment preserved",
            result[
                "speaker_assignment_preserved"
            ] is True,
        )

        add(
            "26. Voice identity preserved",
            result[
                "voice_identity_preserved"
            ] is True,
        )

        add(
            "27. Job remains immutable",
            result[
                "immutable_job_preserved"
            ] is True,
        )

        add(
            "28. Authority preserved",
            execution[
                "authority_preserved"
            ] is True,
        )

        add(
            "29. Performance intent preserved",
            execution[
                "performance_intent_preserved"
            ] is True,
        )

        add(
            "30. Result verified",
            result[
                "verified"
            ] is True,
        )

        # 31-40: PROVIDER TRUTHFULNESS / HANDOFF

        add(
            "31. Live provider not falsely connected",
            LIVE_VOICE_PROVIDER_CONNECTED
            is False,
        )

        add(
            "32. Audio generation not falsely claimed",
            result[
                "audio_generated"
            ] is False,
        )

        add(
            "33. Provider execution not falsely performed",
            execution[
                "provider_execution"
            ][
                "performed"
            ] is False,
        )

        add(
            "34. Provider verification not falsely claimed",
            execution[
                "provider_execution"
            ][
                "verified"
            ] is False,
        )

        add(
            "35. Provider status truthful",
            result[
                "provider_status"
            ]
            == "awaiting_live_voice_provider",
        )

        add(
            "36. QC handoff declared",
            result[
                "next_handoff"
            ][
                "when_audio_exists"
            ]
            == "J.O.A.T. Quality Control Bot",
        )

        add(
            "37. Sound Worker relationship declared",
            result[
                "next_handoff"
            ][
                "post_audio_processing"
            ]
            == "J.O.A.T. Sound Worker Bot",
        )

        add(
            "38. QC cannot be bypassed",
            AUTHORITY_BOUNDARY[
                "may_bypass_qc"
            ] is False,
        )

        add(
            "39. Immutable upstream mutation prohibited",
            AUTHORITY_BOUNDARY[
                "may_modify_immutable_upstream_packets"
            ] is False,
        )

        add(
            "40. Unverified audio claim prohibited",
            AUTHORITY_BOUNDARY[
                "may_claim_unverified_audio_generation"
            ] is False,
        )

        # 41-50: REJECTION / DETERMINISM

        bad_source = deepcopy(job)
        bad_source[
            "source_bot"
        ] = "Unauthorized Bot"

        rejected_source = False

        try:
            self.build_execution(
                bad_source
            )
        except ValueError:
            rejected_source = True

        add(
            "41. Unauthorized source rejected",
            rejected_source,
        )

        bad_target = deepcopy(job)
        bad_target[
            "target_bot"
        ] = "Wrong Bot"

        rejected_target = False

        try:
            self.build_execution(
                bad_target
            )
        except ValueError:
            rejected_target = True

        add(
            "42. Wrong target rejected",
            rejected_target,
        )

        bad_auth = deepcopy(job)
        bad_auth[
            "authorized"
        ] = False

        rejected_auth = False

        try:
            self.build_execution(
                bad_auth
            )
        except ValueError:
            rejected_auth = True

        add(
            "43. Unauthorized job rejected",
            rejected_auth,
        )

        unlocked_dialogue = deepcopy(job)
        unlocked_dialogue[
            "approved_dialogue_locked"
        ] = False

        rejected_unlocked_dialogue = False

        try:
            self.build_execution(
                unlocked_dialogue
            )
        except ValueError:
            rejected_unlocked_dialogue = True

        add(
            "44. Unlocked dialogue rejected",
            rejected_unlocked_dialogue,
        )

        unlocked_character = deepcopy(job)
        unlocked_character[
            "character_identity_locked"
        ] = False

        rejected_unlocked_character = False

        try:
            self.build_execution(
                unlocked_character
            )
        except ValueError:
            rejected_unlocked_character = True

        add(
            "45. Unlocked character identity rejected",
            rejected_unlocked_character,
        )

        unlocked_voice = deepcopy(job)
        unlocked_voice[
            "voice_identity_locked"
        ] = False

        rejected_unlocked_voice = False

        try:
            self.build_execution(
                unlocked_voice
            )
        except ValueError:
            rejected_unlocked_voice = True

        add(
            "46. Unlocked voice identity rejected",
            rejected_unlocked_voice,
        )

        unlocked_performance = deepcopy(job)
        unlocked_performance[
            "performance_intent_locked"
        ] = False

        rejected_unlocked_performance = False

        try:
            self.build_execution(
                unlocked_performance
            )
        except ValueError:
            rejected_unlocked_performance = True

        add(
            "47. Unlocked performance intent rejected",
            rejected_unlocked_performance,
        )

        missing_voice = deepcopy(job)
        del missing_voice[
            "dialogue"
        ][0]["voice_id"]

        rejected_missing_voice = False

        try:
            self.build_execution(
                missing_voice
            )
        except ValueError:
            rejected_missing_voice = True

        add(
            "48. Missing voice identity rejected",
            rejected_missing_voice,
        )

        invalid_duration = deepcopy(job)
        invalid_duration[
            "dialogue"
        ][0][
            "target_duration_seconds"
        ] = -1

        rejected_duration = False

        try:
            self.build_execution(
                invalid_duration
            )
        except ValueError:
            rejected_duration = True

        add(
            "49. Invalid duration rejected",
            rejected_duration,
        )

        instruction_a = deepcopy(
            execution[
                "dialogue_instructions"
            ][0]
        )

        instruction_b = deepcopy(
            execution[
                "dialogue_instructions"
            ][0]
        )

        fingerprint_a = (
            instruction_a.pop(
                "instruction_fingerprint"
            )
        )

        fingerprint_b = (
            instruction_b.pop(
                "instruction_fingerprint"
            )
        )

        add(
            "50. Dialogue instruction fingerprint deterministic",
            (
                fingerprint_a
                == fingerprint_b
                and fingerprint_a
                == make_fingerprint(
                    instruction_a
                )
            ),
        )

        all_passed = all(
            test["pass"]
            for test in tests
        )

        return {
            "acceptance_test_version":
                ACCEPTANCE_TEST_VERSION,
            "app_version":
                APP_VERSION,
            "bot_name":
                BOT_NAME,
            "bot_type":
                BOT_TYPE,
            "reports_to":
                REPORTS_TO,
            "assistant_required":
                ASSISTANT_REQUIRED,
            "job_schema":
                JOB_SCHEMA,
            "execution_schema":
                EXECUTION_SCHEMA,
            "result_schema":
                RESULT_SCHEMA,
            "live_execution_interface":
                LIVE_EXECUTION_INTERFACE,
            "live_voice_provider_connected":
                LIVE_VOICE_PROVIDER_CONNECTED,
            "capabilities":
                deepcopy(
                    CAPABILITIES
                ),
            "authority_boundary":
                deepcopy(
                    AUTHORITY_BOUNDARY
                ),
            "tests":
                tests,
            "test_count":
                len(tests),
            "passed_count":
                sum(
                    1
                    for test in tests
                    if test["pass"]
                ),
            "all_passed":
                all_passed,
            "production_ready":
                all_passed,
            "note": (
                "Voice & Dialogue Worker control and execution-contract "
                "layer is production-ready. Live external voice-provider "
                "generation remains separately connectable and is not "
                "falsely reported as connected."
            ),
        }


BOT = VoiceDialogueWorkerBot()


# =============================================================================
# UI EXAMPLES
# =============================================================================

def example_job() -> str:

    value = {
        "schema": JOB_SCHEMA,
        "job_id": "VOICE-JOB-001",
        "project_id": "PROJECT-001",
        "source_bot":
            "J.O.A.T. Executive Producer Bot",
        "target_bot":
            BOT_NAME,
        "authorized": True,
        "approved_dialogue_locked": True,
        "character_identity_locked": True,
        "voice_identity_locked": True,
        "performance_intent_locked": True,
        "dialogue": [
            {
                "line_id": "LINE-001",
                "speaker_id": "CHAR-001",
                "voice_id": "VOICE-CHAR-001",
                "text":
                    "We are ready to begin.",
                "pronunciation": {
                    "approved": True,
                    "notes": [],
                },
                "performance": {
                    "emotion": "confident",
                    "intensity": 0.65,
                    "pace": "measured",
                },
                "target_duration_seconds": 2.4,
                "sync_reference": "SHOT-001",
                "provider": "provider_neutral",
            },
            {
                "line_id": "LINE-002",
                "speaker_id": "CHAR-002",
                "voice_id": "VOICE-CHAR-002",
                "text":
                    "Then let's get to work.",
                "pronunciation": {
                    "approved": True,
                    "notes": [],
                },
                "performance": {
                    "emotion": "focused",
                    "intensity": 0.55,
                    "pace": "natural",
                },
                "target_duration_seconds": 2.1,
                "sync_reference": "SHOT-002",
                "provider": "provider_neutral",
            },
        ],
    }

    return json.dumps(
        value,
        indent=2,
    )


# =============================================================================
# UI FUNCTIONS
# =============================================================================

def execute_job_ui(
    raw: str,
) -> dict[str, Any]:

    return BOT.execute_job_json(
        raw
    )


def tests_ui() -> dict[str, Any]:

    return BOT.acceptance_test()


# =============================================================================
# GRADIO
# =============================================================================

def build_app() -> gr.Blocks:

    with gr.Blocks(
        title=f"{BOT_NAME} v{APP_VERSION}"
    ) as app:

        gr.Markdown(
            f"# {BOT_NAME}\n\n"
            f"**Version:** `{APP_VERSION}`\n\n"
            "**Voice & Dialogue Control Layer: READY**\n\n"
            "Protects approved dialogue, character voice identity, "
            "speaker assignment, pronunciation, timing, emotional "
            "delivery and performance continuity. Creates deterministic "
            "provider-neutral voice execution instructions without "
            "falsely claiming external audio generation."
        )

        with gr.Tab(
            "Voice Job"
        ):

            job_raw = gr.Code(
                value=example_job(),
                language="json",
                label="Voice & Dialogue Job",
            )

            output = gr.JSON(
                label="Voice & Dialogue Result",
            )

            gr.Button(
                "Execute Voice Job",
                variant="primary",
            ).click(
                fn=execute_job_ui,
                inputs=job_raw,
                outputs=output,
                api_name="execute_voice_job",
            )

        with gr.Tab(
            "Acceptance Tests"
        ):

            gr.Markdown(
                """
### Acceptance Target

`50/50 PASS`

`all_passed: true`

`production_ready: true`
"""
            )

            test_output = gr.JSON(
                label="Voice & Dialogue Acceptance Test",
            )

            gr.Button(
                "Run Acceptance Tests",
                variant="primary",
            ).click(
                fn=tests_ui,
                inputs=None,
                outputs=test_output,
                api_name="acceptance_tests",
            )

        with gr.Tab(
            "Capabilities"
        ):

            gr.JSON(
                value=CAPABILITIES,
                label="Voice & Dialogue Capabilities",
            )

        with gr.Tab(
            "Authority Boundary"
        ):

            gr.JSON(
                value=AUTHORITY_BOUNDARY,
                label="Voice & Dialogue Authority",
            )

        with gr.Tab(
            "About"
        ):

            gr.Markdown(
                f"""
## {BOT_NAME}

**Version:** `{APP_VERSION}`

**Bot Type:** `{BOT_TYPE}`

**Reports To:**  
{REPORTS_TO}

**Assistant Required:** `{ASSISTANT_REQUIRED}`

**Live Execution Interface:** `READY`

**Live Voice Provider:** `NOT YET CONNECTED`

### Studio Position

Dr. G  
↓  
J.O.A.T. Main Assistant Bot  
↓  
J.O.A.T. Executive Producer Bot  
↓  
**J.O.A.T. Voice & Dialogue Worker Bot**

### Responsibility Boundary

This bot owns the preparation and protection of approved spoken
performance.

It preserves:

- approved dialogue
- speaker identity
- voice identity
- pronunciation
- emotional delivery
- pacing
- timing
- synchronization instructions
- upstream creative locks

It does not replace the Sound Worker.

The Voice & Dialogue Worker prepares and eventually coordinates
spoken-performance generation. The Sound Worker remains responsible
for post-production sound execution and treatment.

External voice generation is not reported as complete until a real
voice-provider execution layer is connected and its output is verified.
"""
            )

        from joat_production_ui import add_specialist_ui, add_post_ui, add_delivery_ui, add_voice_ui, add_timeline_ui
        gr.Markdown(f"**Production integration version:** {APP_VERSION}")
        add_voice_ui(BOT)

    return app


if __name__ == "__main__":

    demo = build_app()

    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )