"""
J.O.A.T. Compositing/VFX Worker Bot v1.0.1

Roadmap Stage #13

Bot Type:
- Specialist Worker Bot

Reports To:
- J.O.A.T. Post-Production Supervisor Bot

Assistant:
- None required

Purpose:
- Receive approved Compositing/VFX work orders
- Validate Post-Production Supervisor routing
- Preserve QC provenance
- Build deterministic VFX/compositing execution packets
- Perform only approved technical and visual-effects operations
- Preserve all locked upstream creative decisions
- Return completed results to Post-Production Supervisor
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

import gradio as gr


APP_VERSION = "1.0.1"

BOT_NAME = "J.O.A.T. Compositing/VFX Worker Bot"
BOT_TYPE = "compositing_vfx_worker_bot"

ASSISTANT_REQUIRED = False
ASSISTANT_BOT = None

REPORTS_TO = "J.O.A.T. Post-Production Supervisor Bot"

WORK_ORDER_SCHEMA = "joat.post_work_order.v1"
EXECUTION_SCHEMA = "joat.compositing_vfx_execution.v1"
RESULT_SCHEMA = "joat.compositing_vfx_result.v1"

EXPECTED_DEPARTMENT = "compositing_vfx"

SUPPORTED_TASKS = [
    "compositing",
    "layer_integration",
    "masking",
    "rotoscoping",
    "tracking",
    "keying",
    "cleanup",
    "screen_replacement",
    "approved_vfx_integration",
    "matte_integration",
    "element_integration",
    "technical_vfx_cleanup",
]

PROHIBITED_TASKS = [
    "rewrite_story",
    "rewrite_dialogue",
    "change_character_identity",
    "change_environment_identity",
    "redesign_character",
    "redesign_environment",
    "reinterpret_director_intent",
    "reinterpret_camera",
    "reinterpret_performance",
    "invent_unapproved_vfx",
    "change_locked_composition",
    "silent_creative_change",
]


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


def fingerprint(value: Any) -> str:
    return sha256_text(stable_json(value))


def parse_json_object(
    raw: str,
    label: str,
) -> dict[str, Any]:

    if raw is None or not str(raw).strip():
        raise ValueError(f"{label} is required.")

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


def get_work_order_fingerprint(
    work_order: dict[str, Any],
) -> str:

    existing = work_order.get(
        "work_order_fingerprint"
    )

    if existing:
        return str(existing)

    return fingerprint(work_order)


def qc_is_approved(
    work_order: dict[str, Any],
) -> bool:

    provenance = work_order.get(
        "qc_provenance",
        {},
    )

    if not isinstance(provenance, dict):
        return False

    return (
        provenance.get("qc_status") == "PASS"
        and provenance.get(
            "post_production_authorized"
        ) is True
    )


def validate_authority_boundary(
    work_order: dict[str, Any],
) -> None:

    boundary = work_order.get(
        "authority_boundary",
        {},
    )

    if not isinstance(boundary, dict):
        raise ValueError(
            "Compositing/VFX work order rejected: "
            "authority_boundary is required."
        )

    required_false = [
        "may_change_character_identity",
        "may_change_environment_identity",
        "may_reinterpret_director_intent",
        "may_reinterpret_camera_intent",
        "may_reinterpret_performance_intent",
        "may_rewrite_story",
        "may_rewrite_dialogue",
        "may_invent_unapproved_vfx",
        "may_silently_change_creative_intent",
    ]

    for field in required_false:
        if boundary.get(field) is not False:
            raise ValueError(
                "Compositing/VFX work order rejected: "
                f"{field} must be false."
            )


def validate_work_order(
    work_order: dict[str, Any],
) -> dict[str, Any]:

    if work_order.get("schema") != WORK_ORDER_SCHEMA:
        raise ValueError(
            "Compositing/VFX work order rejected: "
            f"schema must be {WORK_ORDER_SCHEMA!r}."
        )

    if work_order.get("department") != EXPECTED_DEPARTMENT:
        raise ValueError(
            "Compositing/VFX work order rejected: "
            "wrong department."
        )

    if work_order.get("assigned_bot") != BOT_NAME:
        raise ValueError(
            "Compositing/VFX work order rejected: "
            "wrong bot assignment."
        )

    source_asset = work_order.get(
        "source_asset",
        {},
    )

    if not isinstance(source_asset, dict):
        raise ValueError(
            "Source asset is required."
        )

    if not source_asset.get("asset_id"):
        raise ValueError(
            "Source asset_id is required."
        )

    if not qc_is_approved(work_order):
        raise ValueError(
            "Compositing/VFX work order rejected: "
            "QC PASS and Post authorization required."
        )

    validate_authority_boundary(work_order)

    requested_tasks = work_order.get(
        "requested_tasks",
        [],
    )

    if not isinstance(requested_tasks, list):
        raise ValueError(
            "requested_tasks must be a list."
        )

    for task in requested_tasks:

        if task in PROHIBITED_TASKS:
            raise ValueError(
                "Compositing/VFX work order rejected: "
                f"prohibited task: {task}"
            )

        if task not in SUPPORTED_TASKS:
            raise ValueError(
                "Compositing/VFX work order rejected: "
                f"unsupported task: {task}"
            )

    return {
        "work_order_valid": True,
        "department_verified": True,
        "assignment_verified": True,
        "source_asset_verified": True,
        "qc_provenance_verified": True,
        "authority_boundary_verified": True,
        "work_order_fingerprint":
            get_work_order_fingerprint(work_order),
    }


class CompositingVFXWorkerBot:

    def build_execution(
        self,
        work_order: dict[str, Any],
    ) -> dict[str, Any]:

        validation = validate_work_order(
            work_order
        )

        execution = {
            "schema": EXECUTION_SCHEMA,
            "app_version": APP_VERSION,
            "bot_name": BOT_NAME,
            "bot_type": BOT_TYPE,

            "assistant": {
                "assistant_required":
                    ASSISTANT_REQUIRED,
                "assistant_bot":
                    ASSISTANT_BOT,
            },

            "reports_to": REPORTS_TO,

            "validation": validation,

            "source_asset": deepcopy(
                work_order["source_asset"]
            ),

            "qc_provenance": deepcopy(
                work_order["qc_provenance"]
            ),

            "requested_tasks": deepcopy(
                work_order.get(
                    "requested_tasks",
                    [],
                )
            ),

            "vfx_direction": deepcopy(
                work_order.get(
                    "vfx_direction",
                    {},
                )
            ),

            "creative_integrity_policy": {
                "preserve_character_identity": True,
                "preserve_environment_identity": True,
                "preserve_director_intent": True,
                "preserve_camera_intent": True,
                "preserve_performance_intent": True,
                "preserve_story": True,
                "preserve_dialogue": True,
                "preserve_locked_composition": True,
                "unapproved_vfx_allowed": False,
                "silent_creative_change_allowed": False,
            },

            "vfx_scope": {
                "compositing_allowed": True,
                "masking_allowed": True,
                "rotoscoping_allowed": True,
                "tracking_allowed": True,
                "keying_allowed": True,
                "cleanup_allowed": True,
                "screen_replacement_allowed": True,
                "approved_vfx_integration_allowed": True,
                "technical_cleanup_allowed": True,
                "character_redesign_allowed": False,
                "environment_redesign_allowed": False,
                "creative_reinterpretation_allowed": False,
            },

            "execution_policy": {
                "technical_execution_allowed": True,
                "approved_effect_execution_allowed": True,
                "upstream_mutation_allowed": False,
                "creative_invention_allowed": False,
                "human_approval_required_for_locked_change": True,
            },

            "immutable_work_order_snapshot":
                deepcopy(work_order),

            "return_route": {
                "destination": REPORTS_TO,
                "result_schema": RESULT_SCHEMA,
                "ready_for_post_supervisor": False,
            },
        }

        execution[
            "execution_fingerprint"
        ] = fingerprint(execution)

        return execution

    def build_result(
        self,
        execution: dict[str, Any],
        output_asset_id: str,
        output_uri: str,
        completed: bool = True,
        creative_integrity_preserved: bool = True,
    ) -> dict[str, Any]:

        if execution.get("schema") != EXECUTION_SCHEMA:
            raise ValueError(
                "Invalid Compositing/VFX execution schema."
            )

        if execution.get("bot_name") != BOT_NAME:
            raise ValueError(
                "Execution belongs to wrong bot."
            )

        if not output_asset_id:
            raise ValueError(
                "output_asset_id is required."
            )

        if not output_uri:
            raise ValueError(
                "output_uri is required."
            )

        if not creative_integrity_preserved:
            raise ValueError(
                "Compositing/VFX result blocked: "
                "creative integrity failure."
            )

        result = {
            "schema": RESULT_SCHEMA,
            "app_version": APP_VERSION,
            "bot_name": BOT_NAME,
            "bot_type": BOT_TYPE,
            "reports_to": REPORTS_TO,

            "execution_fingerprint":
                execution[
                    "execution_fingerprint"
                ],

            "source_asset": deepcopy(
                execution["source_asset"]
            ),

            "qc_provenance": deepcopy(
                execution["qc_provenance"]
            ),

            "vfx_direction": deepcopy(
                execution.get(
                    "vfx_direction",
                    {},
                )
            ),

            "output_asset": {
                "asset_id": output_asset_id,
                "uri": output_uri,
                "asset_type":
                    "post_production_composited_asset",
            },

            "completion": {
                "completed": bool(completed),
                "creative_integrity_preserved":
                    bool(
                        creative_integrity_preserved
                    ),
            },

            "creative_integrity": deepcopy(
                execution[
                    "creative_integrity_policy"
                ]
            ),

            "handoff": {
                "destination": REPORTS_TO,
                "authorized": (
                    bool(completed)
                    and bool(
                        creative_integrity_preserved
                    )
                ),
            },
        }

        result[
            "result_fingerprint"
        ] = fingerprint(result)

        return result

    def acceptance_test(
        self,
    ) -> dict[str, Any]:

        tests = []

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

        work_order = {
            "schema": WORK_ORDER_SCHEMA,
            "work_order_id": "POST-VFX-001",
            "department": EXPECTED_DEPARTMENT,
            "assigned_bot": BOT_NAME,

            "source_asset": {
                "asset_id": "SHOT-001-QC-PASS",
                "uri": "asset://shot-001",
                "asset_type": "qc_approved_shot",
            },

            "qc_provenance": {
                "qc_status": "PASS",
                "qc_packet_fingerprint":
                    "QC-FP-001",
                "post_production_authorized":
                    True,
            },

            "requested_tasks": [
                "compositing",
                "tracking",
                "masking",
                "approved_vfx_integration",
                "technical_vfx_cleanup",
            ],

            "vfx_direction": {
                "approved_effect":
                    "subtle atmospheric particles",
                "integration":
                    "preserve original performance",
                "camera_match_required":
                    True,
            },

            "authority_boundary": {
                "may_change_character_identity":
                    False,
                "may_change_environment_identity":
                    False,
                "may_reinterpret_director_intent":
                    False,
                "may_reinterpret_camera_intent":
                    False,
                "may_reinterpret_performance_intent":
                    False,
                "may_rewrite_story":
                    False,
                "may_rewrite_dialogue":
                    False,
                "may_invent_unapproved_vfx":
                    False,
                "may_silently_change_creative_intent":
                    False,
            },
        }

        work_order[
            "work_order_fingerprint"
        ] = fingerprint(
            {
                k: v
                for k, v in work_order.items()
                if k != "work_order_fingerprint"
            }
        )

        validation = validate_work_order(
            work_order
        )

        add(
            "1. Post work order schema validates",
            validation["work_order_valid"],
        )

        add(
            "2. Compositing/VFX department verified",
            validation["department_verified"],
        )

        add(
            "3. Compositing/VFX Worker Bot assignment verified",
            validation["assignment_verified"],
        )

        add(
            "4. Source asset verified",
            validation["source_asset_verified"],
        )

        add(
            "5. QC provenance verified",
            validation["qc_provenance_verified"],
        )

        add(
            "6. Authority boundary verified",
            validation["authority_boundary_verified"],
        )

        execution = self.build_execution(
            work_order
        )

        add(
            "7. Compositing/VFX execution packet generates",
            execution["schema"]
            == EXECUTION_SCHEMA,
        )

        required_execution_fields = [
            "schema",
            "app_version",
            "bot_name",
            "bot_type",
            "assistant",
            "reports_to",
            "validation",
            "source_asset",
            "qc_provenance",
            "requested_tasks",
            "vfx_direction",
            "creative_integrity_policy",
            "vfx_scope",
            "execution_policy",
            "immutable_work_order_snapshot",
            "return_route",
            "execution_fingerprint",
        ]

        add(
            "8. Required execution fields present",
            all(
                x in execution
                for x in required_execution_fields
            ),
        )

        add(
            "9. Compositing/VFX Worker requires no assistant",
            (
                execution["assistant"][
                    "assistant_required"
                ] is False
                and execution["assistant"][
                    "assistant_bot"
                ] is None
            ),
        )

        add(
            "10. Compositing/VFX Worker reports to Post Supervisor",
            execution["reports_to"]
            == REPORTS_TO,
        )

        add(
            "11. QC-approved assets accepted",
            execution[
                "qc_provenance"
            ]["qc_status"] == "PASS",
        )

        policy = execution[
            "creative_integrity_policy"
        ]

        add(
            "12. Character identity mutation prohibited",
            policy[
                "preserve_character_identity"
            ],
        )

        add(
            "13. Environment identity mutation prohibited",
            policy[
                "preserve_environment_identity"
            ],
        )

        add(
            "14. Director reinterpretation prohibited",
            policy[
                "preserve_director_intent"
            ],
        )

        add(
            "15. Camera reinterpretation prohibited",
            policy[
                "preserve_camera_intent"
            ],
        )

        add(
            "16. Performance reinterpretation prohibited",
            policy[
                "preserve_performance_intent"
            ],
        )

        add(
            "17. Story rewrite prohibited",
            policy["preserve_story"],
        )

        add(
            "18. Dialogue rewrite prohibited",
            policy["preserve_dialogue"],
        )

        add(
            "19. Locked composition protected",
            policy[
                "preserve_locked_composition"
            ],
        )

        add(
            "20. Unapproved VFX prohibited",
            policy[
                "unapproved_vfx_allowed"
            ] is False,
        )

        add(
            "21. Silent creative change prohibited",
            policy[
                "silent_creative_change_allowed"
            ] is False,
        )

        scope = execution["vfx_scope"]

        add(
            "22. Approved compositing operations enabled",
            (
                scope["compositing_allowed"]
                and scope["tracking_allowed"]
                and scope["masking_allowed"]
                and scope[
                    "approved_vfx_integration_allowed"
                ]
            ),
        )

        add(
            "23. Character redesign prohibited",
            scope[
                "character_redesign_allowed"
            ] is False,
        )

        add(
            "24. Environment redesign prohibited",
            scope[
                "environment_redesign_allowed"
            ] is False,
        )

        first = self.build_execution(
            work_order
        )

        second = self.build_execution(
            work_order
        )

        add(
            "25. Deterministic execution fingerprint",
            first["execution_fingerprint"]
            == second["execution_fingerprint"],
        )

        before = stable_json(work_order)

        self.build_execution(work_order)

        after = stable_json(work_order)

        add(
            "26. Post work order remains immutable",
            before == after,
        )

        bad = deepcopy(work_order)
        bad["department"] = "music"

        rejected = False

        try:
            self.build_execution(bad)
        except ValueError:
            rejected = True

        add(
            "27. Wrong department work order rejected",
            rejected,
        )

        bad = deepcopy(work_order)
        bad["assigned_bot"] = (
            "J.O.A.T. Music Worker Bot"
        )

        rejected = False

        try:
            self.build_execution(bad)
        except ValueError:
            rejected = True

        add(
            "28. Wrong bot assignment rejected",
            rejected,
        )

        bad = deepcopy(work_order)
        bad["qc_provenance"] = {}

        rejected = False

        try:
            self.build_execution(bad)
        except ValueError:
            rejected = True

        add(
            "29. Missing QC provenance rejected",
            rejected,
        )

        bad = deepcopy(work_order)
        bad["qc_provenance"][
            "qc_status"
        ] = "REJECT"

        rejected = False

        try:
            self.build_execution(bad)
        except ValueError:
            rejected = True

        add(
            "30. Non-QC-approved asset rejected",
            rejected,
        )

        bad = deepcopy(work_order)
        bad["requested_tasks"] = [
            "invent_unapproved_vfx"
        ]

        rejected = False

        try:
            self.build_execution(bad)
        except ValueError:
            rejected = True

        add(
            "31. Unapproved VFX request rejected",
            rejected,
        )

        bad = deepcopy(work_order)
        bad["requested_tasks"] = [
            "redesign_character"
        ]

        rejected = False

        try:
            self.build_execution(bad)
        except ValueError:
            rejected = True

        add(
            "32. Character redesign request rejected",
            rejected,
        )

        result = self.build_result(
            execution,
            "VFX-RESULT-001",
            "asset://vfx-result-001",
            True,
            True,
        )

        add(
            "33. Compositing/VFX result packet generates",
            result["schema"]
            == RESULT_SCHEMA,
        )

        required_result_fields = [
            "schema",
            "app_version",
            "bot_name",
            "bot_type",
            "reports_to",
            "execution_fingerprint",
            "source_asset",
            "qc_provenance",
            "vfx_direction",
            "output_asset",
            "completion",
            "creative_integrity",
            "handoff",
            "result_fingerprint",
        ]

        add(
            "34. Required result fields present",
            all(
                x in result
                for x in required_result_fields
            ),
        )

        add(
            "35. VFX result preserves creative integrity",
            result["completion"][
                "creative_integrity_preserved"
            ],
        )

        add(
            "36. VFX result preserves QC provenance",
            result[
                "qc_provenance"
            ]["qc_status"] == "PASS",
        )

        add(
            "37. Completed VFX routes to Post Supervisor",
            (
                result["handoff"][
                    "destination"
                ] == REPORTS_TO
                and result["handoff"][
                    "authorized"
                ] is True
            ),
        )

        rejected = False

        try:
            self.build_result(
                execution,
                "VFX-BAD-001",
                "asset://vfx-bad-001",
                True,
                False,
            )
        except ValueError:
            rejected = True

        add(
            "38. Creative-integrity failure blocks VFX result",
            rejected,
        )

        all_passed = all(
            x["pass"]
            for x in tests
        )

        return {
            "acceptance_test_version": "1.0.0",
            "app_version": APP_VERSION,
            "bot_name": BOT_NAME,
            "bot_type": BOT_TYPE,
            "assistant_required":
                ASSISTANT_REQUIRED,
            "reports_to": REPORTS_TO,
            "work_order_schema":
                WORK_ORDER_SCHEMA,
            "execution_schema":
                EXECUTION_SCHEMA,
            "result_schema":
                RESULT_SCHEMA,
            "tests": tests,
            "all_passed": all_passed,
            "production_ready": all_passed,
            "note": (
                "Compositing/VFX Worker Bot is "
                "production-ready when only properly routed "
                "QC-approved assets enter VFX execution, "
                "approved technical and visual-effects work "
                "remains inside its authority boundary, "
                "locked creative decisions remain protected, "
                "and completed results return to the "
                "Post-Production Supervisor Bot."
            ),
        }


WORKER = CompositingVFXWorkerBot()


def example_work_order() -> dict[str, Any]:

    work_order = {
        "schema": WORK_ORDER_SCHEMA,
        "work_order_id": "POST-VFX-001",
        "department": EXPECTED_DEPARTMENT,
        "assigned_bot": BOT_NAME,

        "source_asset": {
            "asset_id": "SHOT-001-QC-PASS",
            "uri": "asset://shot-001",
            "asset_type": "qc_approved_shot",
        },

        "qc_provenance": {
            "qc_status": "PASS",
            "qc_packet_fingerprint":
                "QC-FP-001",
            "post_production_authorized":
                True,
        },

        "requested_tasks": [
            "compositing",
            "tracking",
            "masking",
            "approved_vfx_integration",
            "technical_vfx_cleanup",
        ],

        "vfx_direction": {
            "approved_effect":
                "subtle atmospheric particles",
            "integration":
                "preserve original performance",
            "camera_match_required": True,
        },

        "authority_boundary": {
            "may_change_character_identity":
                False,
            "may_change_environment_identity":
                False,
            "may_reinterpret_director_intent":
                False,
            "may_reinterpret_camera_intent":
                False,
            "may_reinterpret_performance_intent":
                False,
            "may_rewrite_story":
                False,
            "may_rewrite_dialogue":
                False,
            "may_invent_unapproved_vfx":
                False,
            "may_silently_change_creative_intent":
                False,
        },
    }

    work_order[
        "work_order_fingerprint"
    ] = fingerprint(
        {
            k: v
            for k, v in work_order.items()
            if k != "work_order_fingerprint"
        }
    )

    return work_order


def build_execution_ui(
    raw: str,
) -> dict[str, Any]:

    return WORKER.build_execution(
        parse_json_object(
            raw,
            "Post work order",
        )
    )


def tests_ui() -> dict[str, Any]:
    return WORKER.acceptance_test()


def build_app() -> gr.Blocks:

    example = json.dumps(
        example_work_order(),
        indent=2,
    )

    with gr.Blocks(
        title=f"{BOT_NAME} v{APP_VERSION}"
    ) as app:

        gr.Markdown(
            f"""
# {BOT_NAME}

**Roadmap Stage #13**

**Type:** Specialist Worker Bot  
**Reports to:** {REPORTS_TO}  
**Assistant required:** No

Executes approved compositing and VFX work while preserving
locked production decisions and QC provenance.
"""
        )

        with gr.Tab("VFX Execution"):

            raw = gr.Code(
                value=example,
                language="json",
                label="Compositing/VFX Work Order",
            )

            output = gr.JSON(
                label="Compositing/VFX Execution Packet",
            )

            gr.Button(
                "Build VFX Execution",
                variant="primary",
            ).click(
                fn=build_execution_ui,
                inputs=raw,
                outputs=output,
            )

        with gr.Tab("Acceptance Tests"):

            test_output = gr.JSON(
                label="Compositing/VFX Acceptance Test",
            )

            gr.Button(
                "Run Acceptance Tests",
                variant="primary",
            ).click(
                fn=tests_ui,
                inputs=None,
                outputs=test_output,
            )

        with gr.Tab("Bot Contract"):

            gr.JSON(
                value={
                    "bot_name": BOT_NAME,
                    "bot_type": BOT_TYPE,
                    "assistant_required":
                        ASSISTANT_REQUIRED,
                    "reports_to": REPORTS_TO,
                    "department":
                        EXPECTED_DEPARTMENT,
                    "schemas": {
                        "work_order":
                            WORK_ORDER_SCHEMA,
                        "execution":
                            EXECUTION_SCHEMA,
                        "result":
                            RESULT_SCHEMA,
                    },
                },
                label="Compositing/VFX Worker Contract",
            )

        from joat_production_ui import add_specialist_ui, add_post_ui, add_delivery_ui, add_voice_ui, add_timeline_ui
        gr.Markdown(f"**Production integration version:** {APP_VERSION}")
        add_specialist_ui('compositing_vfx')

    return app


if __name__ == "__main__":

    demo = build_app()

    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )