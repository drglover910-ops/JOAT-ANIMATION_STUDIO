"""
J.O.A.T. Quality Control Bot v1.0.2

Roadmap Stage #8

Type:
- Quality Control / Department Control Bot
- QC Assistant Bot will operate underneath it

Purpose:
- Receive completed Generation Worker results
- Verify source-job and production provenance
- Compare generated assets against locked production requirements
- Classify QC findings
- Issue PASS / REJECT / ESCALATE decisions
- Route failures to the department that owns the failed requirement
- Permit Post-Production handoff only after QC PASS
- Never creatively repair rejected assets
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Optional
from copy import deepcopy
from typing import Any

import gradio as gr
from joat_production_qc import inspect_production


# =============================================================================
# CONFIG
# =============================================================================

APP_VERSION = "1.0.3"

GENERATION_RESULT_SCHEMA = "joat.generation_result.v1"
QC_PACKET_SCHEMA = "joat.quality_control_packet.v1"

VALID_DECISIONS = [
    "PASS",
    "REJECT",
    "ESCALATE",
]

FAILURE_ROUTES = {
    "character_identity": "J.O.A.T. Character/Casting Bot",
    "character_wardrobe": "J.O.A.T. Character/Casting Bot",

    "environment_identity": "J.O.A.T. Production Design Bot",
    "environment_continuity": "J.O.A.T. Production Design Bot",
    "prop_continuity": "J.O.A.T. Production Design Bot",

    "director_intent": "J.O.A.T. Director Bot",

    "camera_framing": "J.O.A.T. Cinematography Bot",
    "camera_movement": "J.O.A.T. Cinematography Bot",
    "shot_composition": "J.O.A.T. Cinematography Bot",

    "performance": "J.O.A.T. Performance/Action Bot",
    "action_continuity": "J.O.A.T. Performance/Action Bot",

    "generation_artifact": "J.O.A.T. Generation Supervisor Bot",
    "technical_corruption": "J.O.A.T. Generation Supervisor Bot",
    "missing_output": "J.O.A.T. Generation Worker Bot",

    "unknown": "J.O.A.T. Executive Producer Bot",
}


# =============================================================================
# HELPERS
# =============================================================================

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


def calculate_result_fingerprint(
    result: dict[str, Any],
) -> str:

    clean = deepcopy(result)
    clean.pop("result_fingerprint", None)

    return sha256_text(
        stable_json(clean)
    )


def calculate_qc_fingerprint(
    packet: dict[str, Any],
) -> str:

    clean = deepcopy(packet)
    clean.pop("qc_fingerprint", None)

    return sha256_text(
        stable_json(clean)
    )


# =============================================================================
# QUALITY CONTROL BOT
# =============================================================================

class QualityControlBot:

    def validate_generation_result(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any]:

        if result.get("schema") != GENERATION_RESULT_SCHEMA:
            raise ValueError(
                "Generation result rejected: invalid schema."
            )

        if result.get("status") != "completed":
            raise ValueError(
                "Generation result rejected: "
                "only completed assets may enter QC."
            )

        output = result.get("output")

        if not isinstance(output, dict):
            raise ValueError(
                "Generation result rejected: output missing."
            )

        if not output.get("location"):
            raise ValueError(
                "Generation result rejected: "
                "output location missing."
            )

        integrity = result.get(
            "creative_integrity",
            {},
        )

        prohibited_changes = [
            "source_job_changed",
            "character_identity_changed",
            "environment_identity_changed",
            "director_intent_changed",
            "camera_intent_changed",
            "performance_intent_changed",
        ]

        for field in prohibited_changes:
            if integrity.get(field) is not False:
                raise ValueError(
                    "Generation result rejected: "
                    f"creative integrity field {field!r} "
                    "does not confirm preservation."
                )

        handoff = result.get(
            "downstream_handoff",
            {},
        )

        if handoff.get("ready_for_qc") is not True:
            raise ValueError(
                "Generation result rejected: "
                "asset was not approved for QC handoff."
            )

        expected = result.get(
            "result_fingerprint"
        )

        actual = calculate_result_fingerprint(
            result
        )

        if expected and expected != actual:
            raise ValueError(
                "Generation result rejected: "
                "result fingerprint mismatch."
            )

        return {
            "generation_result_valid": True,
            "completed_asset_verified": True,
            "creative_integrity_verified": True,
            "qc_handoff_verified": True,
            "result_fingerprint_verified": (
                True if expected else None
            ),
            "calculated_result_fingerprint": actual,
        }

    def classify_finding(
        self,
        finding_type: str,
    ) -> dict[str, Any]:

        normalized = (
            str(finding_type)
            .strip()
            .casefold()
        )

        route = FAILURE_ROUTES.get(
            normalized,
            FAILURE_ROUTES["unknown"],
        )

        return {
            "finding_type": normalized,
            "responsible_department": route,
            "qc_may_fix": False,
            "requires_return": True,
        }

    def inspect(
        self,
        result: dict[str, Any],
        character_ok: bool,
        environment_ok: bool,
        director_ok: bool,
        camera_ok: bool,
        performance_ok: bool,
        technical_ok: bool,
        continuity_ok: bool,
        finding_type: str = "",
        notes: str = "",
    ) -> dict[str, Any]:

        validation = self.validate_generation_result(
            result
        )

        checks = {
            "character_identity": bool(character_ok),
            "environment_identity": bool(environment_ok),
            "director_intent": bool(director_ok),
            "camera_intent": bool(camera_ok),
            "performance_action": bool(performance_ok),
            "technical_integrity": bool(technical_ok),
            "continuity": bool(continuity_ok),
        }

        all_checks_pass = all(
            checks.values()
        )

        if all_checks_pass:

            decision = "PASS"
            failure = None

            routing = {
                "destination": (
                    "J.O.A.T. Post-Production "
                    "Supervisor Bot"
                ),
                "return_to_department": False,
                "post_production_authorized": True,
            }

        else:

            decision = "REJECT"

            normalized = (
                finding_type.strip().casefold()
                if finding_type
                else "unknown"
            )

            failure = self.classify_finding(
                normalized
            )

            routing = {
                "destination": failure[
                    "responsible_department"
                ],
                "return_to_department": True,
                "post_production_authorized": False,
            }

        qc_core = {
            "schema": QC_PACKET_SCHEMA,
            "app_version": APP_VERSION,

            "bot": {
                "name": "J.O.A.T. Quality Control Bot",
                "type": "quality_control_bot",
                "assistant": (
                    "J.O.A.T. QC Assistant Bot"
                ),
            },

            "source_generation_result_fingerprint": (
                result.get("result_fingerprint")
                or validation[
                    "calculated_result_fingerprint"
                ]
            ),

            "project_context": deepcopy(
                result.get(
                    "project_context",
                    {},
                )
            ),

            "inspection": {
                "checks": checks,
                "all_checks_pass": all_checks_pass,
                "notes": (
                    notes.strip()
                    if notes
                    else ""
                ),
            },

            "decision": decision,
            "failure": failure,
            "routing": routing,

            "authority_policy": {
                "qc_may_create_assets": False,
                "qc_may_rewrite_creative_intent": False,
                "qc_may_change_locked_identity": False,
                "qc_may_change_camera_direction": False,
                "qc_may_change_performance": False,
                "qc_may_fix_own_rejection": False,
                "qc_may_pass_asset": True,
                "qc_may_reject_asset": True,
                "qc_may_escalate_asset": True,
            },
        }

        qc_core[
            "qc_fingerprint"
        ] = calculate_qc_fingerprint(
            qc_core
        )

        return qc_core

    # =========================================================================
    # ACCEPTANCE TEST
    # =========================================================================

    def acceptance_test(
        self,
    ) -> dict[str, Any]:

        tests = []

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

        result = {
            "schema": GENERATION_RESULT_SCHEMA,

            "worker": {
                "name": (
                    "J.O.A.T. Generation Worker Bot"
                ),
                "version": "1.0.0",
                "type": "worker_bot",
            },

            "source_job_fingerprint": "JOB-FP-001",

            "project_context": {
                "project_id": "PROJECT-001",
                "scene_id": "SCENE-001",
                "shot_id": "SHOT-001",
            },

            "job_type": "video",
            "engine": "ltx",
            "status": "completed",
            "attempt_number": 1,

            "execution_provenance": {
                "model_name": "LTX",
                "model_version": "approved-runtime",
                "engine": "ltx",
            },

            "output": {
                "location": (
                    "outputs/"
                    "PROJECT-001_SCENE-001_SHOT-001.mp4"
                ),
                "sha256": (
                    "0123456789abcdef"
                    "0123456789abcdef"
                    "0123456789abcdef"
                    "0123456789abcdef"
                ),
            },

            "failure": None,

            "creative_integrity": {
                "source_job_changed": False,
                "character_identity_changed": False,
                "environment_identity_changed": False,
                "director_intent_changed": False,
                "camera_intent_changed": False,
                "performance_intent_changed": False,
            },

            "downstream_handoff": {
                "ready_for_qc": True,
                "ready_for_post": False,
                "post_requires_qc_pass": True,
            },
        }

        result[
            "result_fingerprint"
        ] = calculate_result_fingerprint(
            result
        )

        # 1
        validation = self.validate_generation_result(
            result
        )

        add(
            "1. Generation result validates",
            validation[
                "generation_result_valid"
            ] is True,
        )

        # 2
        add(
            "2. Completed asset verified",
            validation[
                "completed_asset_verified"
            ] is True,
        )

        # 3
        add(
            "3. Creative integrity verified",
            validation[
                "creative_integrity_verified"
            ] is True,
        )

        # 4
        add(
            "4. QC handoff verified",
            validation[
                "qc_handoff_verified"
            ] is True,
        )

        # 5
        add(
            "5. Generation result fingerprint verifies",
            validation[
                "result_fingerprint_verified"
            ] is True,
        )

        # 6
        passed_packet = self.inspect(
            result=result,
            character_ok=True,
            environment_ok=True,
            director_ok=True,
            camera_ok=True,
            performance_ok=True,
            technical_ok=True,
            continuity_ok=True,
        )

        add(
            "6. QC packet generates",
            passed_packet.get("schema")
            == QC_PACKET_SCHEMA,
        )

        # 7
        add(
            "7. Correct asset receives PASS",
            passed_packet["decision"]
            == "PASS",
        )

        # 8
        add(
            "8. PASS authorizes Post-Production",
            (
                passed_packet[
                    "routing"
                ][
                    "post_production_authorized"
                ] is True
                and passed_packet[
                    "routing"
                ]["destination"]
                == (
                    "J.O.A.T. Post-Production "
                    "Supervisor Bot"
                )
            ),
        )

        # 9
        rejected = self.inspect(
            result=result,
            character_ok=False,
            environment_ok=True,
            director_ok=True,
            camera_ok=True,
            performance_ok=True,
            technical_ok=True,
            continuity_ok=True,
            finding_type="character_identity",
        )

        add(
            "9. Character failure receives REJECT",
            rejected["decision"]
            == "REJECT",
        )

        # 10
        add(
            "10. Character failure routes correctly",
            rejected[
                "routing"
            ]["destination"]
            == "J.O.A.T. Character/Casting Bot",
        )

        # 11
        environment_failure = self.inspect(
            result=result,
            character_ok=True,
            environment_ok=False,
            director_ok=True,
            camera_ok=True,
            performance_ok=True,
            technical_ok=True,
            continuity_ok=True,
            finding_type="environment_identity",
        )

        add(
            "11. Environment failure routes correctly",
            environment_failure[
                "routing"
            ]["destination"]
            == "J.O.A.T. Production Design Bot",
        )

        # 12
        camera_failure = self.inspect(
            result=result,
            character_ok=True,
            environment_ok=True,
            director_ok=True,
            camera_ok=False,
            performance_ok=True,
            technical_ok=True,
            continuity_ok=True,
            finding_type="camera_framing",
        )

        add(
            "12. Camera failure routes correctly",
            camera_failure[
                "routing"
            ]["destination"]
            == "J.O.A.T. Cinematography Bot",
        )

        # 13
        performance_failure = self.inspect(
            result=result,
            character_ok=True,
            environment_ok=True,
            director_ok=True,
            camera_ok=True,
            performance_ok=False,
            technical_ok=True,
            continuity_ok=True,
            finding_type="performance",
        )

        add(
            "13. Performance failure routes correctly",
            performance_failure[
                "routing"
            ]["destination"]
            == "J.O.A.T. Performance/Action Bot",
        )

        # 14
        director_failure = self.inspect(
            result=result,
            character_ok=True,
            environment_ok=True,
            director_ok=False,
            camera_ok=True,
            performance_ok=True,
            technical_ok=True,
            continuity_ok=True,
            finding_type="director_intent",
        )

        add(
            "14. Director-intent failure routes correctly",
            director_failure[
                "routing"
            ]["destination"]
            == "J.O.A.T. Director Bot",
        )

        # 15
        technical_failure = self.inspect(
            result=result,
            character_ok=True,
            environment_ok=True,
            director_ok=True,
            camera_ok=True,
            performance_ok=True,
            technical_ok=False,
            continuity_ok=True,
            finding_type="generation_artifact",
        )

        add(
            "15. Generation artifact routes correctly",
            technical_failure[
                "routing"
            ]["destination"]
            == "J.O.A.T. Generation Supervisor Bot",
        )

        # 16
        add(
            "16. Rejected asset blocked from Post-Production",
            technical_failure[
                "routing"
            ][
                "post_production_authorized"
            ] is False,
        )

        # 17
        authority = passed_packet[
            "authority_policy"
        ]

        add(
            "17. QC cannot create assets",
            authority[
                "qc_may_create_assets"
            ] is False,
        )

        # 18
        add(
            "18. QC cannot rewrite creative intent",
            authority[
                "qc_may_rewrite_creative_intent"
            ] is False,
        )

        # 19
        add(
            "19. QC cannot fix its own rejection",
            authority[
                "qc_may_fix_own_rejection"
            ] is False,
        )

        # 20
        first = self.inspect(
            result=result,
            character_ok=True,
            environment_ok=True,
            director_ok=True,
            camera_ok=True,
            performance_ok=True,
            technical_ok=True,
            continuity_ok=True,
        )

        second = self.inspect(
            result=result,
            character_ok=True,
            environment_ok=True,
            director_ok=True,
            camera_ok=True,
            performance_ok=True,
            technical_ok=True,
            continuity_ok=True,
        )

        add(
            "20. Deterministic QC fingerprint",
            first[
                "qc_fingerprint"
            ] == second[
                "qc_fingerprint"
            ],
        )

        # 21
        before = stable_json(
            result
        )

        self.inspect(
            result=result,
            character_ok=True,
            environment_ok=True,
            director_ok=True,
            camera_ok=True,
            performance_ok=True,
            technical_ok=True,
            continuity_ok=True,
        )

        after = stable_json(
            result
        )

        add(
            "21. Generation result remains immutable",
            before == after,
        )

        # 22
        invalid = deepcopy(
            result
        )

        invalid[
            "creative_integrity"
        ][
            "character_identity_changed"
        ] = True

        invalid[
            "result_fingerprint"
        ] = calculate_result_fingerprint(
            invalid
        )

        rejected_invalid = False

        try:
            self.validate_generation_result(
                invalid
            )

        except ValueError:
            rejected_invalid = True

        add(
            "22. Creative-integrity violation rejected",
            rejected_invalid,
        )

        # 23
        incomplete = deepcopy(
            result
        )

        incomplete[
            "status"
        ] = "technical_failure"

        incomplete[
            "result_fingerprint"
        ] = calculate_result_fingerprint(
            incomplete
        )

        rejected_incomplete = False

        try:
            self.validate_generation_result(
                incomplete
            )

        except ValueError:
            rejected_incomplete = True

        add(
            "23. Incomplete generation blocked from QC",
            rejected_incomplete,
        )

        # 24
        unknown_failure = self.inspect(
            result=result,
            character_ok=False,
            environment_ok=True,
            director_ok=True,
            camera_ok=True,
            performance_ok=True,
            technical_ok=True,
            continuity_ok=True,
            finding_type="unknown",
        )

        add(
            "24. Unknown failure escalates safely",
            unknown_failure[
                "routing"
            ]["destination"]
            == "J.O.A.T. Executive Producer Bot",
        )

        # 25
        add(
            "25. QC Assistant relationship declared",
            passed_packet[
                "bot"
            ]["assistant"]
            == "J.O.A.T. QC Assistant Bot",
        )

        # 26
        add(
            "26. QC PASS is sole authorization for Post handoff",
            (
                passed_packet[
                    "routing"
                ][
                    "post_production_authorized"
                ] is True
                and rejected[
                    "routing"
                ][
                    "post_production_authorized"
                ] is False
            ),
        )

        all_passed = all(
            test["pass"]
            for test in tests
        )

        return {
            "acceptance_test_version": "1.0.0",
            "app_version": APP_VERSION,

            "bot_name": (
                "J.O.A.T. Quality Control Bot"
            ),

            "bot_type": (
                "quality_control_bot"
            ),

            "assistant_bot": (
                "J.O.A.T. QC Assistant Bot"
            ),

            "receives_from": (
                "J.O.A.T. Generation Worker Bot"
            ),

            "successful_handoff": (
                "J.O.A.T. Post-Production "
                "Supervisor Bot"
            ),

            "generation_result_schema": (
                GENERATION_RESULT_SCHEMA
            ),

            "qc_packet_schema": (
                QC_PACKET_SCHEMA
            ),

            "tests": tests,

            "all_passed": all_passed,
            "production_ready": all_passed,

            "note": (
                "Quality Control Bot is production-ready "
                "when completed generation results validate, "
                "creative and continuity failures route to "
                "their responsible departments, QC cannot "
                "repair its own rejection, and only a QC PASS "
                "authorizes Post-Production handoff."
            ),
        }


QC = QualityControlBot()


# =============================================================================
# UI
# =============================================================================

def example_result() -> str:

    result = {
        "schema": GENERATION_RESULT_SCHEMA,

        "worker": {
            "name": "J.O.A.T. Generation Worker Bot",
            "version": "1.0.0",
            "type": "worker_bot",
        },

        "source_job_fingerprint": "JOB-FP-001",

        "project_context": {
            "project_id": "PROJECT-001",
            "scene_id": "SCENE-001",
            "shot_id": "SHOT-001",
        },

        "job_type": "video",
        "engine": "ltx",
        "status": "completed",
        "attempt_number": 1,

        "execution_provenance": {
            "model_name": "LTX",
            "model_version": "approved-runtime",
            "engine": "ltx",
        },

        "output": {
            "location": (
                "outputs/"
                "PROJECT-001_SCENE-001_SHOT-001.mp4"
            ),
            "sha256": (
                "0123456789abcdef"
                "0123456789abcdef"
                "0123456789abcdef"
                "0123456789abcdef"
            ),
        },

        "failure": None,

        "creative_integrity": {
            "source_job_changed": False,
            "character_identity_changed": False,
            "environment_identity_changed": False,
            "director_intent_changed": False,
            "camera_intent_changed": False,
            "performance_intent_changed": False,
        },

        "downstream_handoff": {
            "ready_for_qc": True,
            "ready_for_post": False,
            "post_requires_qc_pass": True,
        },
    }

    result[
        "result_fingerprint"
    ] = calculate_result_fingerprint(
        result
    )

    return json.dumps(
        result,
        indent=2,
    )


def validate_ui(
    result_raw: str,
) -> dict[str, Any]:

    result = parse_json_object(
        result_raw,
        "Generation Result",
    )

    return QC.validate_generation_result(
        result
    )


def inspect_ui(
    result_raw: str,
    character_ok: bool,
    environment_ok: bool,
    director_ok: bool,
    camera_ok: bool,
    performance_ok: bool,
    technical_ok: bool,
    continuity_ok: bool,
    finding_type: str,
    notes: str,
) -> dict[str, Any]:

    result = parse_json_object(
        result_raw,
        "Generation Result",
    )

    return QC.inspect(
        result=result,
        character_ok=character_ok,
        environment_ok=environment_ok,
        director_ok=director_ok,
        camera_ok=camera_ok,
        performance_ok=performance_ok,
        technical_ok=technical_ok,
        continuity_ok=continuity_ok,
        finding_type=finding_type,
        notes=notes,
    )


def tests_ui() -> dict[str, Any]:

    return QC.acceptance_test()


def production_qc_ui(result_file: str, source_file: str, media_file: str, reviewed: list[str], notes: str,
                     profile: Optional[gr.OAuthProfile], oauth: Optional[gr.OAuthToken], request: gr.Request):
    from joat_production_ui import require_owner
    reviewer = require_owner(profile, request, oauth)
    if not result_file or not source_file:
        raise gr.Error("Upload the exact Worker result and source Supervisor JSON files.")
    try:
        result = json.loads(Path(result_file).read_text())
        source = json.loads(Path(source_file).read_text())
        checks = {key: key in (reviewed or []) for key in ("character", "environment", "director", "camera", "performance", "continuity")}
        packet = inspect_production(QC, result, source, media_file, checks, notes, reviewer=reviewer)
        output = Path(tempfile.mkdtemp(prefix="joat-qc-")) / "quality_control_packet.json"
        output.write_text(json.dumps(packet, ensure_ascii=False, indent=2))
        return packet, str(output)
    except ValueError as exc:
        raise gr.Error(str(exc)) from None
    except Exception:
        raise gr.Error("Production QC could not validate the supplied inputs.") from None


def build_app() -> gr.Blocks:

    example = example_result()

    with gr.Blocks(
        title=(
            "J.O.A.T. Quality Control Bot "
            f"v{APP_VERSION}"
        )
    ) as app:

        gr.Markdown(
            "# J.O.A.T. Quality Control Bot\n\n"
            f"**Version:** {APP_VERSION}  \n"
            "**Roadmap Stage #8**  \n"
            "**Type:** Quality Control Bot  \n"
            "**Assistant:** J.O.A.T. QC Assistant Bot  \n"
            "**Receives from:** Generation Worker Bot  \n"
            "**PASS →** Post-Production Supervisor Bot\n\n"
            "QC inspects production output. "
            "It does not creatively repair it."
        )

        with gr.Tab("Validate Result"):

            result_raw = gr.Code(
                value=example,
                language="json",
                label="Generation Result",
            )

            validation_output = gr.JSON(
                label="Validation",
            )

            gr.Button(
                "Validate Generation Result",
                variant="primary",
            ).click(
                fn=validate_ui,
                inputs=result_raw,
                outputs=validation_output,
            )

        with gr.Tab("QC Inspection"):

            inspection_raw = gr.Code(
                value=example,
                language="json",
                label="Generation Result",
            )

            character_ok = gr.Checkbox(
                value=True,
                label="Character Correct",
            )

            environment_ok = gr.Checkbox(
                value=True,
                label="Environment Correct",
            )

            director_ok = gr.Checkbox(
                value=True,
                label="Director Intent Correct",
            )

            camera_ok = gr.Checkbox(
                value=True,
                label="Camera Correct",
            )

            performance_ok = gr.Checkbox(
                value=True,
                label="Performance Correct",
            )

            technical_ok = gr.Checkbox(
                value=True,
                label="Technical Integrity Correct",
            )

            continuity_ok = gr.Checkbox(
                value=True,
                label="Continuity Correct",
            )

            finding_type = gr.Dropdown(
                choices=list(
                    FAILURE_ROUTES.keys()
                ),
                value="unknown",
                label="Primary Failure Type",
            )

            notes = gr.Textbox(
                lines=4,
                label="QC Notes",
            )

            inspection_output = gr.JSON(
                label="QC Decision Packet",
            )

            gr.Button(
                "Run QC Inspection",
                variant="primary",
            ).click(
                fn=inspect_ui,
                inputs=[
                    inspection_raw,
                    character_ok,
                    environment_ok,
                    director_ok,
                    camera_ok,
                    performance_ok,
                    technical_ok,
                    continuity_ok,
                    finding_type,
                    notes,
                ],
                outputs=inspection_output,
            )

        with gr.Tab("Acceptance Tests"):

            test_output = gr.JSON(
                label=(
                    "Quality Control Bot "
                    "Acceptance Tests"
                )
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
                        "J.O.A.T. Quality Control Bot"
                    ),

                    "assistant": (
                        "J.O.A.T. QC Assistant Bot"
                    ),

                    "may": [
                        "inspect",
                        "compare against locked requirements",
                        "pass",
                        "reject",
                        "escalate",
                        "route failure",
                        "authorize post-production after pass",
                    ],

                    "may_not": [
                        "create replacement assets",
                        "rewrite creative intent",
                        "change character identity",
                        "change environment identity",
                        "change camera direction",
                        "change performance",
                        "fix its own rejection",
                    ],
                },

                label="QC Authority Boundary",
            )

        with gr.Tab("Production Media QC"):
            gr.Markdown("## Independent review of actual rendered media\nDownload the exact JSON files and MP4 from Generation Worker. Upload them here. Technical validation decodes the video and checks its hash, timing and aspect. Watch the entire shot before confirming each creative requirement. Unchecked requirements produce REJECT and owner routing; this bot never repairs the shot.")
            if all(os.getenv(key) for key in ("OAUTH_CLIENT_ID", "OAUTH_CLIENT_SECRET", "OAUTH_SCOPES", "OPENID_PROVIDER_URL")):
                gr.LoginButton()
            else:
                gr.Markdown("Owner sign-in is available on the OAuth-enabled Hugging Face deployment.")
            production_result = gr.File(label="Exact Generation result JSON", file_types=[".json"], type="filepath")
            production_source = gr.File(label="Exact original Supervisor JSON", file_types=[".json"], type="filepath")
            production_media = gr.File(label="Actual generated MP4", file_types=[".mp4"], type="filepath")
            preview = gr.Video(label="Watch the full generated shot before reviewing")
            production_media.change(lambda path: path, inputs=production_media, outputs=preview, api_visibility="private")
            reviewed = gr.CheckboxGroup(choices=["character", "environment", "director", "camera", "performance", "continuity"], value=[], label="Requirements independently inspected and confirmed")
            review_notes = gr.Textbox(label="Inspection notes and requested rework", lines=3)
            production_packet = gr.JSON(label="Independent QC decision and responsible-owner routing")
            packet_file = gr.File(label="Download exact QC JSON for Post")
            gr.Button("Inspect actual media and issue QC decision").click(production_qc_ui, inputs=[production_result, production_source, production_media, reviewed, review_notes], outputs=[production_packet, packet_file], api_name="inspect_production_media", api_visibility="public", concurrency_limit=1)

        from joat_production_ui import add_final_review_ui
        add_final_review_ui()
        from joat_authored_qc_ui import add_authored_qc_ui
        add_authored_qc_ui()

    return app


if __name__ == "__main__":

    demo = build_app()

    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )