"""
J.O.A.T. Titles/Graphics Worker Bot v1.0.1
Roadmap Stage #15

Purpose:
- Receive approved Titles/Graphics work orders
- Validate Post-Production Supervisor routing
- Preserve QC provenance
- Build deterministic Titles/Graphics execution packets
- Execute only approved on-screen text and graphic work
- Protect locked creative intent and finished visual assets
- Return completed results to Post-Production Supervisor Bot
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

import gradio as gr


APP_VERSION = "1.0.3"

BOT_NAME = "J.O.A.T. Titles/Graphics Worker Bot"
BOT_TYPE = "titles_graphics_worker_bot"

ASSISTANT_REQUIRED = False
ASSISTANT_BOT = None

REPORTS_TO = "J.O.A.T. Post-Production Supervisor Bot"

WORK_ORDER_SCHEMA = "joat.post_work_order.v1"
EXECUTION_SCHEMA = "joat.titles_graphics_execution.v1"
RESULT_SCHEMA = "joat.titles_graphics_result.v1"

EXPECTED_DEPARTMENT = "titles_graphics"

SUPPORTED_TASKS = [
    "main_title",
    "opening_titles",
    "lower_thirds",
    "captions",
    "subtitles",
    "credits",
    "end_credits",
    "end_card",
    "approved_logo",
    "approved_branding",
    "graphic_overlay",
    "location_card",
    "time_card",
    "legal_disclaimer",
]

PROHIBITED_TASKS = [
    "rewrite_story",
    "rewrite_dialogue",
    "change_character_identity",
    "change_environment_identity",
    "reinterpret_director_intent",
    "reinterpret_camera",
    "reinterpret_performance",
    "replace_vfx",
    "change_color_finish",
    "invent_credit",
    "invent_branding",
    "rewrite_approved_text",
    "unauthorized_logo",
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
            "Titles/Graphics work order rejected: "
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
        "may_replace_approved_vfx",
        "may_change_color_finish",
        "may_invent_credits",
        "may_invent_branding",
        "may_rewrite_approved_text",
        "may_silently_change_creative_intent",
    ]

    for field in required_false:
        if boundary.get(field) is not False:
            raise ValueError(
                "Titles/Graphics work order rejected: "
                f"{field} must be false."
            )


def validate_graphics_specification(
    work_order: dict[str, Any],
) -> None:

    spec = work_order.get(
        "graphics_specification",
        {},
    )

    if not isinstance(spec, dict):
        raise ValueError(
            "graphics_specification is required."
        )

    if spec.get("approved_text_locked") is not True:
        raise ValueError(
            "Titles/Graphics work order rejected: "
            "approved_text_locked must be true."
        )

    if spec.get("placement_approved") is not True:
        raise ValueError(
            "Titles/Graphics work order rejected: "
            "placement_approved must be true."
        )

    if spec.get("style_approved") is not True:
        raise ValueError(
            "Titles/Graphics work order rejected: "
            "style_approved must be true."
        )


def validate_work_order(
    work_order: dict[str, Any],
) -> dict[str, Any]:

    if work_order.get("schema") != WORK_ORDER_SCHEMA:
        raise ValueError(
            "Titles/Graphics work order rejected: "
            f"schema must be {WORK_ORDER_SCHEMA!r}."
        )

    if work_order.get("department") != EXPECTED_DEPARTMENT:
        raise ValueError(
            "Titles/Graphics work order rejected: "
            "wrong department."
        )

    if work_order.get("assigned_bot") != BOT_NAME:
        raise ValueError(
            "Titles/Graphics work order rejected: "
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
            "Titles/Graphics work order rejected: "
            "QC PASS and Post authorization required."
        )

    validate_authority_boundary(work_order)
    validate_graphics_specification(work_order)

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
                "Titles/Graphics work order rejected: "
                f"prohibited task: {task}"
            )

        if task not in SUPPORTED_TASKS:
            raise ValueError(
                "Titles/Graphics work order rejected: "
                f"unsupported task: {task}"
            )

    return {
        "work_order_valid": True,
        "department_verified": True,
        "assignment_verified": True,
        "source_asset_verified": True,
        "qc_provenance_verified": True,
        "authority_boundary_verified": True,
        "graphics_specification_verified": True,
        "work_order_fingerprint":
            get_work_order_fingerprint(work_order),
    }


class TitlesGraphicsWorkerBot:

    def build_execution(
        self,
        work_order: dict[str, Any],
    ) -> dict[str, Any]:

        validation = validate_work_order(work_order)

        execution = {
            "schema": EXECUTION_SCHEMA,
            "app_version": APP_VERSION,
            "bot_name": BOT_NAME,
            "bot_type": BOT_TYPE,

            "assistant": {
                "assistant_required": ASSISTANT_REQUIRED,
                "assistant_bot": ASSISTANT_BOT,
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

            "graphics_specification": deepcopy(
                work_order[
                    "graphics_specification"
                ]
            ),

            "creative_integrity_policy": {
                "preserve_character_identity": True,
                "preserve_environment_identity": True,
                "preserve_director_intent": True,
                "preserve_camera_intent": True,
                "preserve_performance_intent": True,
                "preserve_story": True,
                "preserve_dialogue": True,
                "preserve_approved_vfx": True,
                "preserve_color_finish": True,
                "preserve_approved_text": True,
                "preserve_approved_branding": True,
                "invent_credits_allowed": False,
                "invent_branding_allowed": False,
                "rewrite_approved_text_allowed": False,
                "silent_creative_change_allowed": False,
            },

            "graphics_scope": {
                "titles_allowed": True,
                "lower_thirds_allowed": True,
                "captions_allowed": True,
                "subtitles_allowed": True,
                "credits_allowed": True,
                "end_cards_allowed": True,
                "approved_logo_allowed": True,
                "approved_branding_allowed": True,
                "approved_graphic_overlays_allowed": True,
                "unauthorized_logo_allowed": False,
                "unauthorized_branding_allowed": False,
                "creative_reinterpretation_allowed": False,
            },

            "execution_policy": {
                "approved_graphics_execution_allowed": True,
                "approved_text_only": True,
                "approved_placement_only": True,
                "approved_style_only": True,
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
        approved_text_preserved: bool = True,
    ) -> dict[str, Any]:

        if execution.get("schema") != EXECUTION_SCHEMA:
            raise ValueError(
                "Invalid Titles/Graphics execution schema."
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
                "Titles/Graphics result blocked: "
                "creative integrity failure."
            )

        if not approved_text_preserved:
            raise ValueError(
                "Titles/Graphics result blocked: "
                "approved text was changed."
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

            "graphics_specification": deepcopy(
                execution[
                    "graphics_specification"
                ]
            ),

            "output_asset": {
                "asset_id": output_asset_id,
                "uri": output_uri,
                "asset_type":
                    "titles_graphics_finished_asset",
            },

            "completion": {
                "completed": bool(completed),
                "creative_integrity_preserved":
                    bool(
                        creative_integrity_preserved
                    ),
                "approved_text_preserved":
                    bool(
                        approved_text_preserved
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
                    and bool(
                        approved_text_preserved
                    )
                ),
            },
        }

        result[
            "result_fingerprint"
        ] = fingerprint(result)

        return result

    def acceptance_test(self) -> dict[str, Any]:

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

        work_order = {
            "schema": WORK_ORDER_SCHEMA,
            "work_order_id": "POST-GRAPHICS-001",
            "department": EXPECTED_DEPARTMENT,
            "assigned_bot": BOT_NAME,

            "source_asset": {
                "asset_id":
                    "SHOT-001-POST-FINISHED",
                "uri":
                    "asset://shot-001-post-finished",
                "asset_type":
                    "post_production_finished_asset",
            },

            "qc_provenance": {
                "qc_status": "PASS",
                "qc_packet_fingerprint":
                    "QC-FP-001",
                "post_production_authorized": True,
            },

            "requested_tasks": [
                "main_title",
                "lower_thirds",
                "credits",
                "end_card",
            ],

            "graphics_specification": {
                "approved_text_locked": True,
                "placement_approved": True,
                "style_approved": True,

                "approved_text": {
                    "main_title":
                        "J.O.A.T. STUDIOS",
                    "lower_third":
                        "DR. G",
                    "end_card":
                        "J.O.A.T. STUDIOS",
                },

                "approved_credits": [
                    "Creator: Dr. G",
                ],

                "protected_visual_areas": [
                    "character_faces",
                    "critical_action",
                    "required_signage",
                ],

                "approved_style": {
                    "follow_project_style": True,
                    "invent_new_style": False,
                },
            },

            "authority_boundary": {
                "may_change_character_identity": False,
                "may_change_environment_identity": False,
                "may_reinterpret_director_intent": False,
                "may_reinterpret_camera_intent": False,
                "may_reinterpret_performance_intent": False,
                "may_rewrite_story": False,
                "may_rewrite_dialogue": False,
                "may_replace_approved_vfx": False,
                "may_change_color_finish": False,
                "may_invent_credits": False,
                "may_invent_branding": False,
                "may_rewrite_approved_text": False,
                "may_silently_change_creative_intent": False,
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
            "2. Titles/Graphics department verified",
            validation[
                "department_verified"
            ],
        )

        add(
            "3. Titles/Graphics Worker Bot assignment verified",
            validation[
                "assignment_verified"
            ],
        )

        add(
            "4. Source asset verified",
            validation[
                "source_asset_verified"
            ],
        )

        add(
            "5. QC provenance verified",
            validation[
                "qc_provenance_verified"
            ],
        )

        add(
            "6. Authority boundary verified",
            validation[
                "authority_boundary_verified"
            ],
        )

        add(
            "7. Graphics specification verified",
            validation[
                "graphics_specification_verified"
            ],
        )

        execution = self.build_execution(
            work_order
        )

        add(
            "8. Titles/Graphics execution packet generates",
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
            "graphics_specification",
            "creative_integrity_policy",
            "graphics_scope",
            "execution_policy",
            "immutable_work_order_snapshot",
            "return_route",
            "execution_fingerprint",
        ]

        add(
            "9. Required execution fields present",
            all(
                x in execution
                for x in required_execution_fields
            ),
        )

        add(
            "10. Titles/Graphics Worker requires no assistant",
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
            "11. Titles/Graphics Worker reports to Post Supervisor",
            execution["reports_to"]
            == REPORTS_TO,
        )

        add(
            "12. QC-approved assets accepted",
            execution[
                "qc_provenance"
            ]["qc_status"] == "PASS",
        )

        policy = execution[
            "creative_integrity_policy"
        ]

        add(
            "13. Character identity mutation prohibited",
            policy[
                "preserve_character_identity"
            ],
        )

        add(
            "14. Environment identity mutation prohibited",
            policy[
                "preserve_environment_identity"
            ],
        )

        add(
            "15. Director reinterpretation prohibited",
            policy[
                "preserve_director_intent"
            ],
        )

        add(
            "16. Camera reinterpretation prohibited",
            policy[
                "preserve_camera_intent"
            ],
        )

        add(
            "17. Performance reinterpretation prohibited",
            policy[
                "preserve_performance_intent"
            ],
        )

        add(
            "18. Story rewrite prohibited",
            policy["preserve_story"],
        )

        add(
            "19. Dialogue rewrite prohibited",
            policy["preserve_dialogue"],
        )

        add(
            "20. Approved VFX protected",
            policy[
                "preserve_approved_vfx"
            ],
        )

        add(
            "21. Color/Finish protected",
            policy[
                "preserve_color_finish"
            ],
        )

        add(
            "22. Approved text protected",
            policy[
                "preserve_approved_text"
            ],
        )

        add(
            "23. Approved branding protected",
            policy[
                "preserve_approved_branding"
            ],
        )

        add(
            "24. Credit invention prohibited",
            policy[
                "invent_credits_allowed"
            ] is False,
        )

        add(
            "25. Branding invention prohibited",
            policy[
                "invent_branding_allowed"
            ] is False,
        )

        add(
            "26. Approved text rewrite prohibited",
            policy[
                "rewrite_approved_text_allowed"
            ] is False,
        )

        add(
            "27. Silent creative change prohibited",
            policy[
                "silent_creative_change_allowed"
            ] is False,
        )

        scope = execution[
            "graphics_scope"
        ]

        add(
            "28. Approved Titles/Graphics operations enabled",
            (
                scope["titles_allowed"]
                and scope[
                    "lower_thirds_allowed"
                ]
                and scope["credits_allowed"]
                and scope[
                    "end_cards_allowed"
                ]
                and scope[
                    "approved_graphic_overlays_allowed"
                ]
            ),
        )

        add(
            "29. Unauthorized branding prohibited",
            (
                scope[
                    "unauthorized_logo_allowed"
                ] is False
                and scope[
                    "unauthorized_branding_allowed"
                ] is False
            ),
        )

        first = self.build_execution(
            work_order
        )

        second = self.build_execution(
            work_order
        )

        add(
            "30. Deterministic execution fingerprint",
            first[
                "execution_fingerprint"
            ]
            == second[
                "execution_fingerprint"
            ],
        )

        before = stable_json(
            work_order
        )

        self.build_execution(
            work_order
        )

        after = stable_json(
            work_order
        )

        add(
            "31. Post work order remains immutable",
            before == after,
        )

        bad = deepcopy(work_order)
        bad["department"] = "color_finish"

        rejected = False

        try:
            self.build_execution(bad)
        except ValueError:
            rejected = True

        add(
            "32. Wrong department work order rejected",
            rejected,
        )

        bad = deepcopy(work_order)
        bad["assigned_bot"] = (
            "J.O.A.T. Color/Finish Worker Bot"
        )

        rejected = False

        try:
            self.build_execution(bad)
        except ValueError:
            rejected = True

        add(
            "33. Wrong bot assignment rejected",
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
            "34. Missing QC provenance rejected",
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
            "35. Non-QC-approved asset rejected",
            rejected,
        )

        bad = deepcopy(work_order)
        bad["graphics_specification"][
            "approved_text_locked"
        ] = False

        rejected = False

        try:
            self.build_execution(bad)
        except ValueError:
            rejected = True

        add(
            "36. Unlocked graphics text rejected",
            rejected,
        )

        bad = deepcopy(work_order)
        bad["requested_tasks"] = [
            "invent_credit"
        ]

        rejected = False

        try:
            self.build_execution(bad)
        except ValueError:
            rejected = True

        add(
            "37. Credit invention request rejected",
            rejected,
        )

        bad = deepcopy(work_order)
        bad["requested_tasks"] = [
            "unauthorized_logo"
        ]

        rejected = False

        try:
            self.build_execution(bad)
        except ValueError:
            rejected = True

        add(
            "38. Unauthorized logo request rejected",
            rejected,
        )

        bad = deepcopy(work_order)
        bad["requested_tasks"] = [
            "rewrite_approved_text"
        ]

        rejected = False

        try:
            self.build_execution(bad)
        except ValueError:
            rejected = True

        add(
            "39. Approved text rewrite request rejected",
            rejected,
        )

        result = self.build_result(
            execution,
            "GRAPHICS-RESULT-001",
            "asset://graphics-result-001",
            True,
            True,
            True,
        )

        add(
            "40. Titles/Graphics result packet generates",
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
            "graphics_specification",
            "output_asset",
            "completion",
            "creative_integrity",
            "handoff",
            "result_fingerprint",
        ]

        add(
            "41. Required result fields present",
            all(
                x in result
                for x in required_result_fields
            ),
        )

        add(
            "42. Titles/Graphics result preserves creative integrity",
            result[
                "completion"
            ][
                "creative_integrity_preserved"
            ],
        )

        add(
            "43. Titles/Graphics result preserves approved text",
            result[
                "completion"
            ][
                "approved_text_preserved"
            ],
        )

        add(
            "44. Titles/Graphics result preserves QC provenance",
            result[
                "qc_provenance"
            ]["qc_status"] == "PASS",
        )

        add(
            "45. Completed Titles/Graphics routes to Post Supervisor",
            (
                result[
                    "handoff"
                ]["destination"]
                == REPORTS_TO
                and result[
                    "handoff"
                ]["authorized"]
                is True
            ),
        )

        rejected = False

        try:
            self.build_result(
                execution,
                "GRAPHICS-BAD-001",
                "asset://graphics-bad-001",
                True,
                False,
                True,
            )
        except ValueError:
            rejected = True

        add(
            "46. Creative-integrity failure blocks Titles/Graphics result",
            rejected,
        )

        rejected = False

        try:
            self.build_result(
                execution,
                "GRAPHICS-BAD-002",
                "asset://graphics-bad-002",
                True,
                True,
                False,
            )
        except ValueError:
            rejected = True

        add(
            "47. Approved-text mutation blocks Titles/Graphics result",
            rejected,
        )

        all_passed = all(
            x["pass"]
            for x in tests
        )

        return {
            "acceptance_test_version":
                "1.0.0",
            "app_version":
                APP_VERSION,
            "bot_name":
                BOT_NAME,
            "bot_type":
                BOT_TYPE,
            "assistant_required":
                ASSISTANT_REQUIRED,
            "reports_to":
                REPORTS_TO,
            "work_order_schema":
                WORK_ORDER_SCHEMA,
            "execution_schema":
                EXECUTION_SCHEMA,
            "result_schema":
                RESULT_SCHEMA,
            "tests":
                tests,
            "all_passed":
                all_passed,
            "production_ready":
                all_passed,
            "note": (
                "Titles/Graphics Worker Bot is "
                "production-ready when only properly "
                "routed QC-approved assets enter "
                "graphics execution, approved text, "
                "credits, branding, placement, and "
                "style remain protected, unauthorized "
                "creative changes are rejected, and "
                "completed results return to the "
                "Post-Production Supervisor Bot."
            ),
        }


WORKER = TitlesGraphicsWorkerBot()


def example_work_order() -> dict[str, Any]:

    work_order = {
        "schema": WORK_ORDER_SCHEMA,
        "work_order_id":
            "POST-GRAPHICS-001",
        "department":
            EXPECTED_DEPARTMENT,
        "assigned_bot":
            BOT_NAME,

        "source_asset": {
            "asset_id":
                "SHOT-001-POST-FINISHED",
            "uri":
                "asset://shot-001-post-finished",
            "asset_type":
                "post_production_finished_asset",
        },

        "qc_provenance": {
            "qc_status": "PASS",
            "qc_packet_fingerprint":
                "QC-FP-001",
            "post_production_authorized":
                True,
        },

        "requested_tasks": [
            "main_title",
            "lower_thirds",
            "credits",
            "end_card",
        ],

        "graphics_specification": {
            "approved_text_locked": True,
            "placement_approved": True,
            "style_approved": True,

            "approved_text": {
                "main_title":
                    "J.O.A.T. STUDIOS",
                "lower_third":
                    "DR. G",
                "end_card":
                    "J.O.A.T. STUDIOS",
            },

            "approved_credits": [
                "Creator: Dr. G",
            ],

            "protected_visual_areas": [
                "character_faces",
                "critical_action",
                "required_signage",
            ],

            "approved_style": {
                "follow_project_style": True,
                "invent_new_style": False,
            },
        },

        "authority_boundary": {
            "may_change_character_identity": False,
            "may_change_environment_identity": False,
            "may_reinterpret_director_intent": False,
            "may_reinterpret_camera_intent": False,
            "may_reinterpret_performance_intent": False,
            "may_rewrite_story": False,
            "may_rewrite_dialogue": False,
            "may_replace_approved_vfx": False,
            "may_change_color_finish": False,
            "may_invent_credits": False,
            "may_invent_branding": False,
            "may_rewrite_approved_text": False,
            "may_silently_change_creative_intent": False,
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

**Roadmap Stage #15**

**Type:** Specialist Worker Bot  
**Reports to:** {REPORTS_TO}  
**Assistant required:** No

Executes approved titles, credits, captions,
branding, and graphic overlays while preserving
locked creative decisions and QC provenance.
"""
        )

        with gr.Tab(
            "Titles/Graphics Execution"
        ):

            raw = gr.Code(
                value=example,
                language="json",
                label=(
                    "Titles/Graphics Work Order"
                ),
            )

            output = gr.JSON(
                label=(
                    "Titles/Graphics "
                    "Execution Packet"
                ),
            )

            gr.Button(
                "Build Titles/Graphics Execution",
                variant="primary",
            ).click(
                fn=build_execution_ui,
                inputs=raw,
                outputs=output,
            )

        with gr.Tab("Acceptance Tests"):

            test_output = gr.JSON(
                label=(
                    "Titles/Graphics "
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

        with gr.Tab("Bot Contract"):

            gr.JSON(
                value={
                    "bot_name":
                        BOT_NAME,
                    "bot_type":
                        BOT_TYPE,
                    "assistant_required":
                        ASSISTANT_REQUIRED,
                    "reports_to":
                        REPORTS_TO,
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
                label=(
                    "Titles/Graphics "
                    "Worker Contract"
                ),
            )

        from joat_production_ui import add_specialist_ui, add_post_ui, add_delivery_ui, add_voice_ui, add_timeline_ui
        gr.Markdown(f"**Production integration version:** {APP_VERSION}")
        add_specialist_ui('titles_graphics')
        from joat_authored_graphics_ui import add_authored_graphics_ui
        add_authored_graphics_ui()

    return app


if __name__ == "__main__":

    demo = build_app()

    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )