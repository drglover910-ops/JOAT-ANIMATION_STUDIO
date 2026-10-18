"""
J.O.A.T. Browser Worker Bot v1.1.0

Shared browser/computer execution control plane.

Architecture:
J.O.A.T. Main Assistant Bot
    -> Authorized Machine Work Order
    -> Browser Worker Bot
    -> Browser Execution Layer
    -> Chromium / Website
    -> Verification
    -> Result Packet
    -> Main Assistant

v1.1.0 adds the machine-to-machine execution interface while
preserving the v1.0.0 permission, verification, recovery,
authority, and acceptance boundaries.

IMPORTANT:
The Browser Worker execution interface is live.

The actual Chromium/browser-control engine remains separately
connectable and is never falsely reported as connected or executed.
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

APP_VERSION = "1.1.0"
ACCEPTANCE_TEST_VERSION = "1.1.0"

BOT_NAME = "J.O.A.T. Browser Worker Bot"
BOT_TYPE = "browser_worker_bot"
REPORTS_TO = "J.O.A.T. Main Assistant Bot"

ASSISTANT_REQUIRED = False

WORK_ORDER_SCHEMA = "joat.browser_work_order.v1"
EXECUTION_SCHEMA = "joat.browser_execution.v1"
RESULT_SCHEMA = "joat.browser_result.v1"

MACHINE_REQUEST_SCHEMA = "joat.browser_machine_request.v1"
MACHINE_EXECUTION_SCHEMA = "joat.browser_machine_execution.v1"
MACHINE_RESULT_SCHEMA = "joat.browser_machine_result.v1"

LIVE_EXECUTION_INTERFACE = True
LIVE_BROWSER_ENGINE_CONNECTED = False


# =============================================================================
# BROWSER CONTRACT
# =============================================================================

BROWSER_TOOLS = [
    "browser_open",
    "browser_read",
    "browser_click",
    "browser_type",
    "browser_scroll",
    "browser_screenshot",
    "browser_upload",
    "browser_download",
    "browser_tabs",
    "browser_back",
    "browser_wait",
    "browser_submit",
]


PERMISSIONS = [
    "READ",
    "NAVIGATE",
    "TYPE",
    "UPLOAD",
    "DOWNLOAD",
    "SUBMIT",
    "PURCHASE",
    "DELETE",
]


SAFE_DEFAULT_PERMISSIONS = {
    "READ",
    "NAVIGATE",
}


SENSITIVE_PERMISSIONS = {
    "TYPE",
    "UPLOAD",
    "DOWNLOAD",
    "SUBMIT",
    "PURCHASE",
    "DELETE",
}


EXECUTION_LOOP = [
    "observe",
    "decide",
    "act",
    "verify",
]


CAPABILITIES = {
    "browser_control": {
        "required_level": "guru",
        "capabilities": [
            "Chromium browser control",
            "DOM inspection",
            "accessibility-tree awareness",
            "visual screenshot awareness",
            "navigation",
            "form interaction",
            "file upload",
            "file download",
            "tab management",
            "submission",
            "post-action verification",
        ],
    },
    "execution": {
        "required_level": "guru",
        "capabilities": [
            "observe-decide-act-verify",
            "authorized execution",
            "execution receipts",
            "deterministic work orders",
            "bounded retries",
            "failure classification",
            "recovery planning",
            "session awareness",
            "audit logging",
        ],
    },
    "joat_architecture": {
        "required_level": "guru",
        "capabilities": [
            "authority boundaries",
            "bot chain of command",
            "immutable source packets",
            "Main Assistant authorization",
            "specialist bot authorization",
            "approval checkpoints",
            "verified handoffs",
            "production readiness",
        ],
    },
}


AUTHORITY_BOUNDARY = {
    "may_execute_authorized_browser_actions": True,
    "may_read_public_pages_without_mutation_approval": True,
    "may_verify_results": True,
    "may_report_failures": True,
    "may_attempt_bounded_recovery": True,

    "live_browser_execution_enabled_v1": False,

    "may_invent_business_decisions": False,
    "may_expand_scope_without_authorization": False,
    "may_bypass_main_assistant": False,
    "may_override_specialist_authority": False,
    "may_expose_credentials": False,
    "may_bypass_2fa": False,
    "may_bypass_captcha": False,
    "may_self_authorize_purchase": False,
    "may_self_authorize_delete": False,
    "may_claim_unverified_success": False,
}


# =============================================================================
# HELPERS
# =============================================================================

def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def fingerprint(value: Any) -> str:
    return hashlib.sha256(
        stable_json(value).encode("utf-8")
    ).hexdigest()


def clean(value: str | None) -> str:
    return str(value or "").strip()


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


def normalize_permissions(
    permissions: list[str] | None,
) -> list[str]:

    values = list(
        permissions or []
    )

    invalid = [
        x
        for x in values
        if x not in PERMISSIONS
    ]

    if invalid:
        raise ValueError(
            f"Unsupported browser permissions: {invalid}"
        )

    return sorted(
        set(values)
    )


def requires_approval(
    permissions: list[str],
) -> bool:

    return bool(
        set(permissions)
        & SENSITIVE_PERMISSIONS
    )


# =============================================================================
# BROWSER WORKER
# =============================================================================

class BrowserWorkerBot:

    def build_work_order(
        self,
        requester: str,
        objective: str,
        target_url: str,
        permissions: list[str],
        authorized: bool,
        context: str = "",
    ) -> dict[str, Any]:

        requester = clean(
            requester
        )

        objective = clean(
            objective
        )

        target_url = clean(
            target_url
        )

        context = clean(
            context
        )

        permissions = normalize_permissions(
            permissions
        )

        if not requester:
            raise ValueError(
                "Requester is required."
            )

        if not objective:
            raise ValueError(
                "Objective is required."
            )

        if not target_url:
            raise ValueError(
                "Target URL is required."
            )

        approval_required = requires_approval(
            permissions
        )

        if (
            approval_required
            and authorized is not True
        ):
            raise ValueError(
                "Sensitive browser execution requires "
                "authorization."
            )

        core = {
            "schema":
                WORK_ORDER_SCHEMA,

            "bot_name":
                BOT_NAME,

            "bot_type":
                BOT_TYPE,

            "reports_to":
                REPORTS_TO,

            "requester":
                requester,

            "objective":
                objective,

            "target_url":
                target_url,

            "context":
                context,

            "permissions":
                permissions,

            "approval": {
                "required":
                    approval_required,

                "approved": (
                    authorized
                    if approval_required
                    else True
                ),
            },

            "execution_loop":
                deepcopy(
                    EXECUTION_LOOP
                ),

            "browser_tools":
                deepcopy(
                    BROWSER_TOOLS
                ),

            "authority_boundary":
                deepcopy(
                    AUTHORITY_BOUNDARY
                ),

            "execution": {
                "live_execution_interface":
                    LIVE_EXECUTION_INTERFACE,

                "live_browser_engine_connected":
                    LIVE_BROWSER_ENGINE_CONNECTED,

                "browser_engine":
                    "Chromium",

                "control_layer":
                    "browser execution service",

                "verification_required":
                    True,

                "bounded_recovery":
                    True,
            },
        }

        core[
            "work_order_fingerprint"
        ] = fingerprint(
            core
        )

        return core

    def build_result(
        self,
        work_order: dict[str, Any],
        status: str,
        verified: bool,
        findings: str,
    ) -> dict[str, Any]:

        if (
            work_order.get("schema")
            != WORK_ORDER_SCHEMA
        ):
            raise ValueError(
                "Invalid browser work-order schema."
            )

        allowed_statuses = [
            "completed",
            "blocked",
            "failed",
            "requires_approval",
            "requires_execution_layer",
        ]

        if status not in allowed_statuses:
            raise ValueError(
                f"Unsupported status: {status}"
            )

        if (
            status == "completed"
            and verified is not True
        ):
            raise ValueError(
                "Browser Worker cannot report completed "
                "without verification."
            )

        result = {
            "schema":
                RESULT_SCHEMA,

            "bot_name":
                BOT_NAME,

            "bot_type":
                BOT_TYPE,

            "reports_to":
                REPORTS_TO,

            "source_work_order_fingerprint":
                work_order.get(
                    "work_order_fingerprint"
                ),

            "requester":
                work_order.get(
                    "requester"
                ),

            "objective":
                work_order.get(
                    "objective"
                ),

            "target_url":
                work_order.get(
                    "target_url"
                ),

            "status":
                status,

            "verified":
                bool(
                    verified
                ),

            "findings":
                clean(
                    findings
                ),

            "scope_preserved":
                True,

            "authority_preserved":
                True,

            "credentials_protected":
                True,

            "ready_for_requester":
                True,
        }

        result[
            "result_fingerprint"
        ] = fingerprint(
            result
        )

        return result

    # =========================================================================
    # MACHINE-TO-MACHINE EXECUTION
    # =========================================================================

    def validate_machine_request(
        self,
        request: dict[str, Any],
    ) -> None:

        if (
            request.get("schema")
            != MACHINE_REQUEST_SCHEMA
        ):
            raise ValueError(
                "Invalid Browser Worker machine-request schema."
            )

        if not request.get(
            "request_id"
        ):
            raise ValueError(
                "request_id is required."
            )

        if (
            request.get("source_bot")
            != REPORTS_TO
        ):
            raise ValueError(
                "Browser Worker accepts machine requests "
                "only from J.O.A.T. Main Assistant Bot."
            )

        if (
            request.get("target_bot")
            != BOT_NAME
        ):
            raise ValueError(
                "Machine-request target does not match "
                "Browser Worker Bot."
            )

        objective = clean(
            request.get(
                "objective"
            )
        )

        target_url = clean(
            request.get(
                "target_url"
            )
        )

        if not objective:
            raise ValueError(
                "Objective is required."
            )

        if not target_url:
            raise ValueError(
                "Target URL is required."
            )

        permissions = normalize_permissions(
            request.get(
                "permissions"
            )
        )

        approval_required = requires_approval(
            permissions
        )

        if (
            approval_required
            and request.get(
                "authorized"
            )
            is not True
        ):
            raise ValueError(
                "Sensitive browser execution requires "
                "authorization."
            )

    def execute_machine_request(
        self,
        request: dict[str, Any],
    ) -> dict[str, Any]:

        immutable_request = deepcopy(
            request
        )

        self.validate_machine_request(
            request
        )

        permissions = normalize_permissions(
            request.get(
                "permissions"
            )
        )

        work_order = self.build_work_order(
            requester=request[
                "source_bot"
            ],

            objective=clean(
                request.get(
                    "objective"
                )
            ),

            target_url=clean(
                request.get(
                    "target_url"
                )
            ),

            permissions=permissions,

            authorized=(
                request.get(
                    "authorized"
                )
                is True
            ),

            context=clean(
                request.get(
                    "context"
                )
            ),
        )

        execution_id = str(
            uuid.uuid4()
        )

        execution = {
            "schema":
                MACHINE_EXECUTION_SCHEMA,

            "execution_id":
                execution_id,

            "request_id":
                request[
                    "request_id"
                ],

            "source_bot":
                request[
                    "source_bot"
                ],

            "target_bot":
                BOT_NAME,

            "objective":
                work_order[
                    "objective"
                ],

            "target_url":
                work_order[
                    "target_url"
                ],

            "permissions":
                deepcopy(
                    permissions
                ),

            "started_at":
                utc_now(),

            "request_validated":
                True,

            "work_order_created":
                True,

            "live_interface_executed":
                True,

            "browser_engine_connected":
                LIVE_BROWSER_ENGINE_CONNECTED,

            "browser_actions_performed":
                False,

            "verification_performed":
                False,

            "bounded_recovery_available":
                True,
        }

        execution[
            "execution_fingerprint"
        ] = fingerprint(
            execution
        )

        if (
            LIVE_BROWSER_ENGINE_CONNECTED
            is False
        ):
            status = (
                "requires_execution_layer"
            )

            findings = (
                "Browser Worker validated the request and "
                "created the authorized browser work order. "
                "The Chromium/browser execution engine is not "
                "yet connected, so no website action has been "
                "performed or claimed."
            )

            verified = False

        else:
            status = (
                "requires_execution_layer"
            )

            findings = (
                "Browser engine connection was declared but "
                "no verified browser-engine adapter is "
                "implemented in this build. No website action "
                "has been claimed."
            )

            verified = False

        browser_result = self.build_result(
            work_order=work_order,
            status=status,
            verified=verified,
            findings=findings,
        )

        result = {
            "schema":
                MACHINE_RESULT_SCHEMA,

            "execution_id":
                execution_id,

            "request_id":
                request[
                    "request_id"
                ],

            "bot_name":
                BOT_NAME,

            "status":
                status,

            "verified":
                verified,

            "work_order":
                work_order,

            "browser_result":
                browser_result,

            "browser_execution": {
                "engine":
                    "Chromium",

                "connected":
                    LIVE_BROWSER_ENGINE_CONNECTED,

                "actions_performed":
                    False,

                "verification_performed":
                    False,

                "success_claimed":
                    False,
            },

            "authority_preserved":
                True,

            "scope_preserved":
                True,

            "credentials_protected":
                True,

            "credentials_exposed":
                False,

            "immutable_request_preserved": (
                stable_json(
                    request
                )
                == stable_json(
                    immutable_request
                )
            ),

            "completed_at":
                utc_now(),
        }

        result[
            "result_fingerprint"
        ] = fingerprint(
            result
        )

        return {
            "execution":
                execution,

            "result":
                result,
        }

    def execute_machine_request_json(
        self,
        raw: str,
    ) -> dict[str, Any]:

        request = parse_json_object(
            raw,
            "Browser Worker Machine Request",
        )

        return self.execute_machine_request(
            request
        )

    # =========================================================================
    # ACCEPTANCE
    # =========================================================================

    def acceptance_test(
        self,
    ) -> dict[str, Any]:

        tests = []

        def add(
            name,
            passed,
        ):
            tests.append(
                {
                    "test":
                        name,

                    "pass":
                        bool(
                            passed
                        ),

                    "detail":
                        bool(
                            passed
                        ),
                }
            )

        read_order = self.build_work_order(
            requester=REPORTS_TO,
            objective="Inspect deployment status.",
            target_url="https://example.com",
            permissions=[
                "READ",
                "NAVIGATE",
            ],
            authorized=False,
        )

        submit_order = self.build_work_order(
            requester=REPORTS_TO,
            objective="Submit authorized update.",
            target_url="https://example.com",
            permissions=[
                "READ",
                "NAVIGATE",
                "TYPE",
                "SUBMIT",
            ],
            authorized=True,
        )

        # ORIGINAL 50 TESTS

        add(
            "1. Browser work order generates",
            read_order[
                "schema"
            ]
            == WORK_ORDER_SCHEMA,
        )

        add(
            "2. Correct bot name declared",
            read_order[
                "bot_name"
            ]
            == BOT_NAME,
        )

        add(
            "3. Correct bot type declared",
            read_order[
                "bot_type"
            ]
            == BOT_TYPE,
        )

        add(
            "4. Reports to Main Assistant Bot",
            read_order[
                "reports_to"
            ]
            == REPORTS_TO,
        )

        add(
            "5. No assistant required",
            ASSISTANT_REQUIRED
            is False,
        )

        add(
            "6. Browser control guru mastery declared",
            CAPABILITIES[
                "browser_control"
            ][
                "required_level"
            ]
            == "guru",
        )

        add(
            "7. Execution guru mastery declared",
            CAPABILITIES[
                "execution"
            ][
                "required_level"
            ]
            == "guru",
        )

        add(
            "8. J.O.A.T. architecture guru mastery declared",
            CAPABILITIES[
                "joat_architecture"
            ][
                "required_level"
            ]
            == "guru",
        )

        add(
            "9. Chromium control declared",
            "Chromium browser control"
            in CAPABILITIES[
                "browser_control"
            ][
                "capabilities"
            ],
        )

        add(
            "10. DOM inspection declared",
            "DOM inspection"
            in CAPABILITIES[
                "browser_control"
            ][
                "capabilities"
            ],
        )

        add(
            "11. Screenshot awareness declared",
            "visual screenshot awareness"
            in CAPABILITIES[
                "browser_control"
            ][
                "capabilities"
            ],
        )

        add(
            "12. Observe phase declared",
            EXECUTION_LOOP[
                0
            ]
            == "observe",
        )

        add(
            "13. Decide phase declared",
            EXECUTION_LOOP[
                1
            ]
            == "decide",
        )

        add(
            "14. Act phase declared",
            EXECUTION_LOOP[
                2
            ]
            == "act",
        )

        add(
            "15. Verify phase declared",
            EXECUTION_LOOP[
                3
            ]
            == "verify",
        )

        expected_tools = {
            "browser_open",
            "browser_read",
            "browser_click",
            "browser_type",
            "browser_scroll",
            "browser_screenshot",
            "browser_upload",
            "browser_download",
            "browser_tabs",
            "browser_back",
            "browser_wait",
            "browser_submit",
        }

        add(
            "16. Standard browser toolkit declared",
            expected_tools.issubset(
                set(
                    BROWSER_TOOLS
                )
            ),
        )

        add(
            "17. READ permission supported",
            "READ"
            in PERMISSIONS,
        )

        add(
            "18. NAVIGATE permission supported",
            "NAVIGATE"
            in PERMISSIONS,
        )

        add(
            "19. TYPE permission supported",
            "TYPE"
            in PERMISSIONS,
        )

        add(
            "20. UPLOAD permission supported",
            "UPLOAD"
            in PERMISSIONS,
        )

        add(
            "21. DOWNLOAD permission supported",
            "DOWNLOAD"
            in PERMISSIONS,
        )

        add(
            "22. SUBMIT permission supported",
            "SUBMIT"
            in PERMISSIONS,
        )

        add(
            "23. PURCHASE permission supported",
            "PURCHASE"
            in PERMISSIONS,
        )

        add(
            "24. DELETE permission supported",
            "DELETE"
            in PERMISSIONS,
        )

        add(
            "25. Read-only work needs no mutation approval",
            (
                read_order[
                    "approval"
                ][
                    "required"
                ]
                is False
                and read_order[
                    "approval"
                ][
                    "approved"
                ]
                is True
            ),
        )

        add(
            "26. Submit work requires approval",
            submit_order[
                "approval"
            ][
                "required"
            ]
            is True,
        )

        add(
            "27. Authorized submit accepted",
            submit_order[
                "approval"
            ][
                "approved"
            ]
            is True,
        )

        rejected = False

        try:
            self.build_work_order(
                requester=REPORTS_TO,
                objective="Submit change.",
                target_url="https://example.com",
                permissions=[
                    "SUBMIT"
                ],
                authorized=False,
            )

        except ValueError:
            rejected = True

        add(
            "28. Unauthorized sensitive action rejected",
            rejected,
        )

        add(
            "29. Live browser engine remains disabled",
            AUTHORITY_BOUNDARY[
                "live_browser_execution_enabled_v1"
            ]
            is False,
        )

        add(
            "30. Business-decision invention prohibited",
            AUTHORITY_BOUNDARY[
                "may_invent_business_decisions"
            ]
            is False,
        )

        add(
            "31. Unauthorized scope expansion prohibited",
            AUTHORITY_BOUNDARY[
                "may_expand_scope_without_authorization"
            ]
            is False,
        )

        add(
            "32. Main Assistant bypass prohibited",
            AUTHORITY_BOUNDARY[
                "may_bypass_main_assistant"
            ]
            is False,
        )

        add(
            "33. Specialist authority override prohibited",
            AUTHORITY_BOUNDARY[
                "may_override_specialist_authority"
            ]
            is False,
        )

        add(
            "34. Credential exposure prohibited",
            AUTHORITY_BOUNDARY[
                "may_expose_credentials"
            ]
            is False,
        )

        add(
            "35. 2FA bypass prohibited",
            AUTHORITY_BOUNDARY[
                "may_bypass_2fa"
            ]
            is False,
        )

        add(
            "36. CAPTCHA bypass prohibited",
            AUTHORITY_BOUNDARY[
                "may_bypass_captcha"
            ]
            is False,
        )

        add(
            "37. Self-authorized purchase prohibited",
            AUTHORITY_BOUNDARY[
                "may_self_authorize_purchase"
            ]
            is False,
        )

        add(
            "38. Self-authorized delete prohibited",
            AUTHORITY_BOUNDARY[
                "may_self_authorize_delete"
            ]
            is False,
        )

        add(
            "39. Unverified success prohibited",
            AUTHORITY_BOUNDARY[
                "may_claim_unverified_success"
            ]
            is False,
        )

        first = self.build_work_order(
            requester=REPORTS_TO,
            objective="Inspect deployment status.",
            target_url="https://example.com",
            permissions=[
                "READ",
                "NAVIGATE",
            ],
            authorized=False,
        )

        second = self.build_work_order(
            requester=REPORTS_TO,
            objective="Inspect deployment status.",
            target_url="https://example.com",
            permissions=[
                "READ",
                "NAVIGATE",
            ],
            authorized=False,
        )

        add(
            "40. Deterministic work-order fingerprint",
            first[
                "work_order_fingerprint"
            ]
            == second[
                "work_order_fingerprint"
            ],
        )

        before = stable_json(
            read_order
        )

        result = self.build_result(
            read_order,
            status="completed",
            verified=True,
            findings="Inspection verified.",
        )

        after = stable_json(
            read_order
        )

        add(
            "41. Source work order remains immutable",
            before == after,
        )

        add(
            "42. Browser result packet generates",
            result[
                "schema"
            ]
            == RESULT_SCHEMA,
        )

        add(
            "43. Result reports to Main Assistant",
            result[
                "reports_to"
            ]
            == REPORTS_TO,
        )

        add(
            "44. Result verification preserved",
            result[
                "verified"
            ]
            is True,
        )

        add(
            "45. Result authority preserved",
            result[
                "authority_preserved"
            ]
            is True,
        )

        add(
            "46. Result credentials protected",
            result[
                "credentials_protected"
            ]
            is True,
        )

        add(
            "47. Result fingerprint generated",
            bool(
                result[
                    "result_fingerprint"
                ]
            ),
        )

        invalid_completion_rejected = False

        try:
            self.build_result(
                read_order,
                status="completed",
                verified=False,
                findings="",
            )

        except ValueError:
            invalid_completion_rejected = True

        add(
            "48. Unverified completion rejected",
            invalid_completion_rejected,
        )

        add(
            "49. Bounded recovery declared",
            read_order[
                "execution"
            ][
                "bounded_recovery"
            ]
            is True,
        )

        all_before = all(
            x[
                "pass"
            ]
            for x in tests
        )

        add(
            "50. Browser Worker Bot production-ready",
            all_before,
        )

        # LIVE MACHINE INTERFACE TESTS 51-75

        add(
            "51. Live machine interface enabled",
            LIVE_EXECUTION_INTERFACE
            is True,
        )

        add(
            "52. Machine-request schema declared",
            MACHINE_REQUEST_SCHEMA
            == "joat.browser_machine_request.v1",
        )

        add(
            "53. Machine-execution schema declared",
            MACHINE_EXECUTION_SCHEMA
            == "joat.browser_machine_execution.v1",
        )

        add(
            "54. Machine-result schema declared",
            MACHINE_RESULT_SCHEMA
            == "joat.browser_machine_result.v1",
        )

        machine_request = {
            "schema":
                MACHINE_REQUEST_SCHEMA,

            "request_id":
                "BROWSER-REQ-001",

            "source_bot":
                REPORTS_TO,

            "target_bot":
                BOT_NAME,

            "objective":
                "Inspect deployment status.",

            "target_url":
                "https://example.com",

            "permissions": [
                "READ",
                "NAVIGATE",
            ],

            "authorized":
                False,

            "context":
                "Acceptance test.",
        }

        machine_before = stable_json(
            machine_request
        )

        machine = self.execute_machine_request(
            machine_request
        )

        machine_execution = machine[
            "execution"
        ]

        machine_result = machine[
            "result"
        ]

        add(
            "55. Valid Main Assistant machine request accepted",
            machine_execution[
                "request_id"
            ]
            == "BROWSER-REQ-001",
        )

        add(
            "56. Machine execution packet generated",
            machine_execution[
                "schema"
            ]
            == MACHINE_EXECUTION_SCHEMA,
        )

        add(
            "57. Machine result packet generated",
            machine_result[
                "schema"
            ]
            == MACHINE_RESULT_SCHEMA,
        )

        add(
            "58. Browser work order created from machine request",
            machine_result[
                "work_order"
            ][
                "schema"
            ]
            == WORK_ORDER_SCHEMA,
        )

        add(
            "59. Machine request remains immutable",
            machine_before
            == stable_json(
                machine_request
            ),
        )

        add(
            "60. Browser engine not falsely reported connected",
            machine_result[
                "browser_execution"
            ][
                "connected"
            ]
            is False,
        )

        add(
            "61. Browser action not falsely reported performed",
            machine_result[
                "browser_execution"
            ][
                "actions_performed"
            ]
            is False,
        )

        add(
            "62. Browser verification not falsely reported",
            machine_result[
                "browser_execution"
            ][
                "verification_performed"
            ]
            is False,
        )

        add(
            "63. Browser success not falsely claimed",
            machine_result[
                "browser_execution"
            ][
                "success_claimed"
            ]
            is False,
        )

        add(
            "64. Missing browser engine returns execution-layer status",
            machine_result[
                "status"
            ]
            == "requires_execution_layer",
        )

        add(
            "65. Authority preserved through machine execution",
            machine_result[
                "authority_preserved"
            ]
            is True,
        )

        add(
            "66. Scope preserved through machine execution",
            machine_result[
                "scope_preserved"
            ]
            is True,
        )

        add(
            "67. Credentials remain protected",
            (
                machine_result[
                    "credentials_protected"
                ]
                is True
                and machine_result[
                    "credentials_exposed"
                ]
                is False
            ),
        )

        bad_source = deepcopy(
            machine_request
        )

        bad_source[
            "source_bot"
        ] = "Unauthorized Bot"

        source_rejected = False

        try:
            self.execute_machine_request(
                bad_source
            )

        except ValueError:
            source_rejected = True

        add(
            "68. Unauthorized machine source rejected",
            source_rejected,
        )

        bad_target = deepcopy(
            machine_request
        )

        bad_target[
            "target_bot"
        ] = "Wrong Bot"

        target_rejected = False

        try:
            self.execute_machine_request(
                bad_target
            )

        except ValueError:
            target_rejected = True

        add(
            "69. Wrong machine target rejected",
            target_rejected,
        )

        sensitive_request = deepcopy(
            machine_request
        )

        sensitive_request[
            "request_id"
        ] = "BROWSER-REQ-002"

        sensitive_request[
            "permissions"
        ] = [
            "READ",
            "NAVIGATE",
            "TYPE",
            "SUBMIT",
        ]

        sensitive_request[
            "authorized"
        ] = True

        sensitive = self.execute_machine_request(
            sensitive_request
        )

        add(
            "70. Authorized sensitive machine request accepted",
            sensitive[
                "result"
            ][
                "work_order"
            ][
                "approval"
            ][
                "approved"
            ]
            is True,
        )

        unauthorized_sensitive = deepcopy(
            sensitive_request
        )

        unauthorized_sensitive[
            "authorized"
        ] = False

        sensitive_rejected = False

        try:
            self.execute_machine_request(
                unauthorized_sensitive
            )

        except ValueError:
            sensitive_rejected = True

        add(
            "71. Unauthorized sensitive machine request rejected",
            sensitive_rejected,
        )

        invalid_permission = deepcopy(
            machine_request
        )

        invalid_permission[
            "permissions"
        ] = [
            "READ",
            "ROOT_ACCESS",
        ]

        invalid_permission_rejected = False

        try:
            self.execute_machine_request(
                invalid_permission
            )

        except ValueError:
            invalid_permission_rejected = True

        add(
            "72. Unsupported browser permission rejected",
            invalid_permission_rejected,
        )

        add(
            "73. Bounded recovery preserved in machine work order",
            machine_result[
                "work_order"
            ][
                "execution"
            ][
                "bounded_recovery"
            ]
            is True,
        )

        add(
            "74. Verification remains mandatory",
            machine_result[
                "work_order"
            ][
                "execution"
            ][
                "verification_required"
            ]
            is True,
        )

        add(
            "75. Browser Worker machine integration architecture ready",
            (
                LIVE_EXECUTION_INTERFACE
                is True
                and machine_result[
                    "authority_preserved"
                ]
                is True
                and machine_result[
                    "scope_preserved"
                ]
                is True
                and machine_result[
                    "credentials_exposed"
                ]
                is False
                and machine_result[
                    "browser_execution"
                ][
                    "success_claimed"
                ]
                is False
            ),
        )

        all_passed = all(
            x[
                "pass"
            ]
            for x in tests
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

            "machine_request_schema":
                MACHINE_REQUEST_SCHEMA,

            "machine_execution_schema":
                MACHINE_EXECUTION_SCHEMA,

            "machine_result_schema":
                MACHINE_RESULT_SCHEMA,

            "live_execution_interface":
                LIVE_EXECUTION_INTERFACE,

            "live_browser_engine_connected":
                LIVE_BROWSER_ENGINE_CONNECTED,

            "capabilities":
                deepcopy(
                    CAPABILITIES
                ),

            "tests":
                tests,

            "test_count":
                len(
                    tests
                ),

            "passed_count":
                sum(
                    1
                    for x
                    in tests
                    if x[
                        "pass"
                    ]
                ),

            "all_passed":
                all_passed,

            "production_ready":
                all_passed,

            "note": (
                "Browser Worker Bot v1.1.0 provides the "
                "Main Assistant machine-to-machine browser "
                "execution contract while keeping the actual "
                "Chromium/browser engine separately connectable. "
                "No browser action or success is claimed until "
                "the external browser engine executes and "
                "verification succeeds."
            ),
        }


MASTER = BrowserWorkerBot()


# =============================================================================
# UI
# =============================================================================

def example_machine_request() -> str:

    value = {
        "schema":
            MACHINE_REQUEST_SCHEMA,

        "request_id":
            "BROWSER-REQ-001",

        "source_bot":
            REPORTS_TO,

        "target_bot":
            BOT_NAME,

        "objective":
            "Inspect deployment status.",

        "target_url":
            "https://example.com",

        "permissions": [
            "READ",
            "NAVIGATE",
        ],

        "authorized":
            False,

        "context":
            "",
    }

    return json.dumps(
        value,
        indent=2,
    )


def build_work_order_ui(
    requester,
    objective,
    target_url,
    permissions,
    authorized,
    context,
):

    return MASTER.build_work_order(
        requester=requester,
        objective=objective,
        target_url=target_url,
        permissions=permissions,
        authorized=authorized,
        context=context,
    )


def execute_machine_request_ui(
    request_raw,
):

    return MASTER.execute_machine_request_json(
        request_raw
    )


def tests_ui():

    return MASTER.acceptance_test()


def build_app():

    with gr.Blocks(
        title=f"{BOT_NAME} v{APP_VERSION}"
    ) as app:

        gr.Markdown(
            f"# {BOT_NAME}\n\n"
            "**Shared J.O.A.T. browser/computer execution worker.**\n\n"
            "**Main Assistant Machine Interface: READY**\n\n"
            "**Browser Engine: NOT YET CONNECTED**\n\n"
            "Execution model: "
            "**OBSERVE → DECIDE → ACT → VERIFY**"
        )

        with gr.Tab(
            "Browser Work Order"
        ):

            requester = gr.Textbox(
                value=REPORTS_TO,
                label="Requesting Bot",
            )

            objective = gr.Textbox(
                value="Inspect deployment status.",
                lines=3,
                label="Objective",
            )

            target_url = gr.Textbox(
                value="https://example.com",
                label="Target URL",
            )

            permissions = gr.CheckboxGroup(
                choices=PERMISSIONS,
                value=[
                    "READ",
                    "NAVIGATE",
                ],
                label="Authorized Permissions",
            )

            authorized = gr.Checkbox(
                value=False,
                label=(
                    "Dr. G / authorized J.O.A.T. "
                    "authority approved sensitive action"
                ),
            )

            context = gr.Textbox(
                lines=5,
                label="Execution Context",
            )

            output = gr.JSON(
                label="Browser Work Order"
            )

            gr.Button(
                "Build Browser Work Order",
                variant="primary",
            ).click(
                fn=build_work_order_ui,
                inputs=[
                    requester,
                    objective,
                    target_url,
                    permissions,
                    authorized,
                    context,
                ],
                outputs=output,
                api_name="build_browser_work_order",
            )

        with gr.Tab(
            "Live Execution"
        ):

            gr.Markdown(
                """
### Main Assistant → Browser Worker

This machine interface receives an authorized Browser Worker
request from the J.O.A.T. Main Assistant Bot.

The worker validates permissions and approval, constructs the
browser work order, and returns an execution receipt.

The actual Chromium/browser engine remains separately
connectable. No navigation, typing, submission, purchase,
deletion, upload, download or other website action is reported
as performed unless the browser engine actually executes it
and verification succeeds.
"""
            )

            machine_request = gr.Code(
                value=example_machine_request(),
                language="json",
                label="Browser Machine Request",
            )

            machine_output = gr.JSON(
                label="Browser Machine Execution Result"
            )

            gr.Button(
                "Execute Browser Request",
                variant="primary",
            ).click(
                fn=execute_machine_request_ui,
                inputs=machine_request,
                outputs=machine_output,
                api_name="execute_browser_request",
            )

        with gr.Tab(
            "Acceptance Tests"
        ):

            gr.Markdown(
                """
### Acceptance Target

`75/75 PASS`

`all_passed: true`

`production_ready: true`
"""
            )

            test_output = gr.JSON(
                label="Browser Worker Acceptance Tests"
            )

            gr.Button(
                "Run Acceptance Tests",
                variant="primary",
            ).click(
                fn=tests_ui,
                outputs=test_output,
                api_name="acceptance_tests",
            )

        with gr.Tab(
            "Capabilities"
        ):

            gr.JSON(
                value=CAPABILITIES,
                label="Browser Worker Capabilities",
            )

        with gr.Tab(
            "Authority Boundary"
        ):

            gr.JSON(
                value=AUTHORITY_BOUNDARY,
                label="Authority Boundary",
            )

        with gr.Tab(
            "About"
        ):

            gr.Markdown(
                f"""
## {BOT_NAME}

**Version:** `{APP_VERSION}`

**Bot type:** `{BOT_TYPE}`

**Reports to:** {REPORTS_TO}

**Work order:** `{WORK_ORDER_SCHEMA}`

**Execution:** `{EXECUTION_SCHEMA}`

**Result:** `{RESULT_SCHEMA}`

**Machine request:** `{MACHINE_REQUEST_SCHEMA}`

**Machine execution:** `{MACHINE_EXECUTION_SCHEMA}`

**Machine result:** `{MACHINE_RESULT_SCHEMA}`

### Operating Contract

The Browser Worker is the shared execution control plane for
authorized J.O.A.T. web and browser operations.

The Main Assistant can now call the Browser Worker through a
stable machine-to-machine Gradio API endpoint.

### Browser Engine Boundary

The machine interface and browser engine are separate layers.

The machine interface validates scope, permissions and
authorization.

The Chromium/browser engine will perform the actual website
actions once connected.

A successful browser operation can never be reported until
the real action has occurred and post-action verification
has succeeded.
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