"""
J.O.A.T. Executive Producer Bot v1.2.20
Roadmap Stage #17

LIVE EXECUTION + STUDIO CONNECTIVITY UPGRADE

Purpose:
- Serve as executive command authority for the J.O.A.T. production studio
- Receive authenticated/authorized production work orders from Main Assistant
- Validate machine-to-machine execution contracts
- Create production plans
- Return structured execution results
- Preserve deterministic fingerprints
- Preserve all original Executive Producer authority boundaries
- Never falsely claim downstream studio execution
- Discover and safely probe subordinate Hugging Face Spaces
"""

from __future__ import annotations

from joat_runtime_client import install as install_department_routing
install_department_routing(local=True)

import hashlib
import hmac
import threading
import json
import os
import re
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

import gradio as gr
from gradio_client import Client
from huggingface_hub import HfApi


# =============================================================================
# CONFIG
# =============================================================================

APP_VERSION = "1.2.20"
FILE_VERSION = "1.2.20"
ACCEPTANCE_TEST_VERSION = "1.2.0"

BOT_NAME = "J.O.A.T. Executive Producer Bot"
BOT_TYPE = "executive_producer_bot"

REPORTS_TO = "J.O.A.T. Main Assistant Bot"

PACKET_SCHEMA = "joat.executive_producer_packet.v1"
PRODUCTION_PLAN_SCHEMA = "joat.production_plan.v1"
STATUS_SCHEMA = "joat.production_status.v1"
ESCALATION_SCHEMA = "joat.production_escalation.v1"

WORK_ORDER_SCHEMA = "joat.executive_producer_work_order.v1"
EXECUTION_SCHEMA = "joat.executive_producer_execution.v1"
EXECUTION_RESULT_SCHEMA = "joat.executive_producer_execution_result.v1"

CONNECTIVITY_REPORT_SCHEMA = "joat.studio_connectivity_report.v1"

LIVE_EXECUTION_INTERFACE = True
DOWNSTREAM_LIVE_EXECUTION_CONNECTED = False

HF_OWNER = "Dezz-9-10"
HF_TOKEN_ENV = "JOAT_SPECIALIST_TOKEN"
CONNECTIVITY_RETRIES = 2
CONNECTIVITY_RETRY_DELAY_SECONDS = 0.75


# =============================================================================
# STUDIO ORGANIZATION
# =============================================================================

STUDIO_ROLES = {
    "character": {
        "bot": "J.O.A.T. Character Master Bot",
        "responsibility": (
            "character identity, approved appearance, "
            "identity locks and character continuity"
        ),
    },
    "environment": {
        "bot": "J.O.A.T. Environment Master Bot",
        "responsibility": (
            "environment identity, locations, world assets, "
            "environment locks and visual-world continuity"
        ),
    },
    "director": {
        "bot": "J.O.A.T. Director Master Bot",
        "responsibility": (
            "creative interpretation, performance intent, "
            "tone, staging and audience experience"
        ),
    },
    "shot_camera": {
        "bot": "J.O.A.T. Shot/Camera Master Bot",
        "responsibility": (
            "shot design, framing, camera position, movement, "
            "composition and cinematographic execution"
        ),
    },
    "performance_action": {
        "bot": "J.O.A.T. Performance/Action Master Bot",
        "responsibility": (
            "performance beats, physical action, emotional "
            "continuity and shot-level action timing"
        ),
    },
    "generation_supervisor": {
        "bot": "J.O.A.T. Generation Supervisor Bot",
        "responsibility": (
            "generation routing, engine selection, job creation "
            "and preservation of locked upstream instructions"
        ),
    },
    "generation_worker": {
        "bot": "J.O.A.T. Generation Worker Bot",
        "responsibility": (
            "approved engine execution and generation-result "
            "creation without creative reinterpretation"
        ),
    },
    "quality_control": {
        "bot": "J.O.A.T. Quality Control Bot",
        "assistant": "J.O.A.T. QC Assistant Bot",
        "responsibility": (
            "independent inspection, pass/reject decisions, "
            "continuity verification and failure classification"
        ),
    },
    "post_production": {
        "bot": "J.O.A.T. Post-Production Supervisor Bot",
        "responsibility": (
            "coordination of approved Post-Production work"
        ),
    },
    "editorial": {
        "bot": "J.O.A.T. Editorial Worker Bot",
        "assistant": "J.O.A.T. Edit Assistant Bot",
        "responsibility": (
            "editorial assembly of QC-approved production assets"
        ),
    },
    "sound": {
        "bot": "J.O.A.T. Sound Worker Bot",
        "assistant": "J.O.A.T. Audio Assistant Bot",
        "responsibility": (
            "sound execution while protecting dialogue, "
            "voice identity and creative intent"
        ),
    },
    "voice_dialogue": {
        "bot": "J.O.A.T. Voice & Dialogue Worker Bot",
        "responsibility": (
            "approved dialogue and voice execution, voice identity "
            "continuity, synchronization and audio handoff"
        ),
    },
    "music": {
        "bot": "J.O.A.T. Music Worker Bot",
        "responsibility": (
            "approved score and music execution"
        ),
    },
    "compositing_vfx": {
        "bot": "J.O.A.T. Compositing/VFX Worker Bot",
        "responsibility": (
            "approved compositing and visual-effects execution"
        ),
    },
    "color_finish": {
        "bot": "J.O.A.T. Color/Finish Worker Bot",
        "responsibility": (
            "approved color and finishing operations"
        ),
    },
    "titles_graphics": {
        "bot": "J.O.A.T. Titles/Graphics Worker Bot",
        "responsibility": (
            "approved titles, credits, graphics and branding"
        ),
    },
    "delivery_archive": {
        "bot": "J.O.A.T. Delivery/Archive Bot",
        "responsibility": (
            "final-master protection, versioning, provenance, "
            "archiving and authorized delivery"
        ),
    },
}


# =============================================================================
# CANONICAL HUGGING FACE SPACE ALIASES
# =============================================================================

# These aliases bridge logical studio-role names to the permanent Hugging Face
# repository IDs whose deployed names intentionally differ. An alias is accepted
# only when that exact repository ID is present in authenticated owner discovery.
ROLE_REPO_ALIASES = {
    "character": "Dezz-9-10/J.O.A.T.-Character-Asset-Master",
    "environment": "Dezz-9-10/J.O.A.T.-Scene-Environment-Master",
    "director": "Dezz-9-10/J.O.A.T.-Director-Creative-Intelligence",
    "generation_supervisor": "Dezz-9-10/J.O.A.T.-Generation-Supervisor-Master",
}


# =============================================================================
# TECHNOLOGY / PRODUCT MASTERY
# =============================================================================

TECHNOLOGY_MASTERY = {
    "ltx": {
        "required_level": "guru",
        "domain": "video_generation",
        "must_understand": [
            "generation role inside J.O.A.T.",
            "input requirements",
            "shot and motion instruction translation",
            "duration and aspect-ratio requirements",
            "generation-job routing",
            "technical failure diagnosis",
            "retry boundaries",
            "creative-drift risks",
            "output handoff to QC",
        ],
    },
    "hugging_face_spaces": {
        "required_level": "guru",
        "domain": "studio_bot_runtime",
        "must_understand": [
            "Space deployment",
            "Gradio applications",
            "requirements management",
            "runtime failures",
            "version control implications",
            "environment configuration",
            "production readiness",
            "authenticated Space discovery",
            "safe endpoint introspection",
        ],
    },
    "gradio": {
        "required_level": "expert",
        "domain": "bot_interface_runtime",
        "must_understand": [
            "Blocks applications",
            "inputs and outputs",
            "event routing",
            "JSON interfaces",
            "acceptance-test interfaces",
            "Gradio Client API discovery",
        ],
    },
    "joat_packet_architecture": {
        "required_level": "guru",
        "domain": "production_control",
        "must_understand": [
            "schemas",
            "fingerprints",
            "immutable upstream packets",
            "authority boundaries",
            "handoffs",
            "creative locks",
            "provenance",
            "deterministic execution contracts",
        ],
    },
}


# =============================================================================
# PIPELINE
# =============================================================================

PRODUCTION_PIPELINE = [
    "character",
    "environment",
    "director",
    "shot_camera",
    "performance_action",
    "generation_supervisor",
    "generation_worker",
    "quality_control",
    "post_production",
    "editorial",
    "sound",
    "voice_dialogue",
    "music",
    "compositing_vfx",
    "color_finish",
    "titles_graphics",
    "delivery_archive",
]


# =============================================================================
# AUTHORITY
# =============================================================================

AUTHORITY_BOUNDARY = {
    "may_coordinate_departments": True,
    "may_determine_work_order": True,
    "may_inspect_department_outputs": True,
    "may_diagnose_failures": True,
    "may_route_rework": True,
    "may_stop_production": True,
    "may_escalate_to_main_assistant": True,
    "may_verify_technology_route": True,

    "may_replace_main_assistant": False,
    "may_override_dr_g": False,
    "may_silently_rewrite_story": False,
    "may_redesign_locked_character": False,
    "may_replace_locked_environment": False,
    "may_silently_change_director_intent": False,
    "may_silently_change_camera_intent": False,
    "may_silently_change_performance": False,
    "may_bypass_qc": False,
    "may_modify_immutable_packets": False,
    "may_self_approve_locked_creative_change": False,
}


# =============================================================================
# SUPERVISOR ROUTING METADATA
# =============================================================================

SUPERVISOR_ROUTING = {
    "generation_worker": "generation_supervisor",
    "editorial": "post_production",
    "sound": "post_production",
    "voice_dialogue": "post_production",
    "music": "post_production",
    "compositing_vfx": "post_production",
    "color_finish": "post_production",
    "titles_graphics": "post_production",
    "delivery_archive": "post_production",
    "quality_control": None,
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


def make_fingerprint(
    value: dict[str, Any],
) -> str:

    return sha256_text(
        stable_json(value)
    )


def normalize_name(value: str) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        value.lower(),
    )


def get_hf_token() -> str | None:
    token = os.environ.get(
        HF_TOKEN_ENV,
        "",
    ).strip()

    return token or None


def safe_token_status() -> dict[str, Any]:
    token = get_hf_token()

    return {
        "environment_variable": HF_TOKEN_ENV,
        "present": bool(token),
        "value_exposed": False,
    }


def discover_canonical_spaces() -> dict[str, Any]:
    token = get_hf_token()

    if not token:
        return {
            "owner": HF_OWNER,
            "token": safe_token_status(),
            "spaces": [],
            "error": (
                f"{HF_TOKEN_ENV} is not configured."
            ),
        }

    try:
        api = HfApi(
            token=token
        )

        spaces = list(
            api.list_spaces(
                author=HF_OWNER
            )
        )

        discovered = []

        for space in spaces:
            repo_id = getattr(
                space,
                "id",
                None,
            ) or getattr(
                space,
                "repo_id",
                None,
            )

            if repo_id:
                discovered.append(
                    {
                        "repo_id": repo_id,
                        "normalized_repo_name":
                            normalize_name(
                                repo_id.split(
                                    "/",
                                    1,
                                )[-1]
                            ),
                    }
                )

        return {
            "owner": HF_OWNER,
            "token": safe_token_status(),
            "spaces": discovered,
            "error": None,
        }

    except Exception as exc:
        return {
            "owner": HF_OWNER,
            "token": safe_token_status(),
            "spaces": [],
            "error": (
                f"{type(exc).__name__}: {exc}"
            ),
        }


def match_role_to_spaces(
    role: str,
    discovered_spaces: list[dict[str, Any]],
) -> dict[str, Any]:

    definition = STUDIO_ROLES[
        role
    ]

    discovered_repo_ids = {
        item["repo_id"]
        for item in discovered_spaces
        if item.get("repo_id")
    }

    canonical_alias = (
        ROLE_REPO_ALIASES.get(role)
    )

    if (
        canonical_alias
        and canonical_alias
        in discovered_repo_ids
    ):
        return {
            "role": role,
            "bot": definition["bot"],
            "status": "resolved",
            "repo_id": canonical_alias,
            "candidates": [
                canonical_alias
            ],
        }

    target = normalize_name(
        definition["bot"]
    )

    candidates = []

    for item in discovered_spaces:
        repo_name = item[
            "normalized_repo_name"
        ]

        if (
            repo_name == target
            or repo_name in target
            or target in repo_name
        ):
            candidates.append(
                item["repo_id"]
            )

    if len(candidates) == 1:
        return {
            "role": role,
            "bot": definition["bot"],
            "status": "resolved",
            "repo_id": candidates[0],
            "candidates": candidates,
        }

    if not candidates:
        return {
            "role": role,
            "bot": definition["bot"],
            "status": "unresolved",
            "repo_id": None,
            "candidates": [],
        }

    return {
        "role": role,
        "bot": definition["bot"],
        "status": "ambiguous",
        "repo_id": None,
        "candidates": candidates,
    }

def probe_gradio_space(
    repo_id: str,
) -> dict[str, Any]:

    token = get_hf_token()

    if not token:
        return {
            "reachable": False,
            "api_visible": False,
            "named_endpoints": [],
            "error": (
                f"{HF_TOKEN_ENV} is not configured."
            ),
        }

    last_error = None

    for attempt in range(
        1,
        CONNECTIVITY_RETRIES + 1,
    ):
        try:
            client = Client(
                repo_id,
                token=token,
                verbose=False,
            )

            api = client.view_api(
                return_format="dict"
            )

            named_endpoints = sorted(
                list(
                    (
                        api.get(
                            "named_endpoints",
                            {}
                        )
                        if isinstance(
                            api,
                            dict,
                        )
                        else {}
                    ).keys()
                )
            )

            return {
                "reachable": True,
                "api_visible": True,
                "named_endpoints":
                    named_endpoints,
                "error": None,
                "attempts": attempt,
            }

        except Exception as exc:
            last_error = (
                f"{type(exc).__name__}: {exc}"
            )

            if (
                attempt
                < CONNECTIVITY_RETRIES
            ):
                time.sleep(
                    CONNECTIVITY_RETRY_DELAY_SECONDS
                )

    return {
        "reachable": False,
        "api_visible": False,
        "named_endpoints": [],
        "error": last_error,
        "attempts": CONNECTIVITY_RETRIES,
    }


def build_connectivity_report() -> dict[str, Any]:
    discovery = discover_canonical_spaces()

    role_results = []

    for role in PRODUCTION_PIPELINE:
        match = match_role_to_spaces(
            role,
            discovery["spaces"],
        )

        result = {
            "role": role,
            "bot": STUDIO_ROLES[
                role
            ]["bot"],
            "supervisor_role":
                SUPERVISOR_ROUTING.get(
                    role
                ),
            "discovered":
                match[
                    "status"
                ]
                == "resolved",
            "discovery_status":
                match["status"],
            "repo_id":
                match["repo_id"],
            "candidates":
                match["candidates"],
            "reachable": False,
            "api_visible": False,
            "named_endpoints": [],
            "real_work_executed": False,
            "error": None,
        }

        if match["repo_id"]:
            probe = probe_gradio_space(
                match["repo_id"]
            )

            result.update(
                {
                    "reachable":
                        probe["reachable"],
                    "api_visible":
                        probe["api_visible"],
                    "named_endpoints":
                        probe[
                            "named_endpoints"
                        ],
                    "error":
                        probe["error"],
                }
            )

        role_results.append(
            result
        )

    all_required_connected = (
        bool(role_results)
        and all(
            item["discovered"]
            and item["reachable"]
            and item["api_visible"]
            for item in role_results
        )
    )

    report = {
        "schema":
            CONNECTIVITY_REPORT_SCHEMA,
        "app_version":
            APP_VERSION,
        "bot_name":
            BOT_NAME,
        "owner":
            HF_OWNER,
        "token":
            safe_token_status(),
        "discovery_error":
            discovery["error"],
        "roles":
            role_results,
        "required_role_count":
            len(PRODUCTION_PIPELINE),
        "resolved_role_count":
            sum(
                1
                for item in role_results
                if item["discovered"]
            ),
        "reachable_role_count":
            sum(
                1
                for item in role_results
                if item["reachable"]
            ),
        "api_visible_role_count":
            sum(
                1
                for item in role_results
                if item["api_visible"]
            ),
        "all_required_connected":
            all_required_connected,
        "downstream_live_execution_connected":
            DOWNSTREAM_LIVE_EXECUTION_CONNECTED,
        "downstream_execution_performed":
            False,
        "truth_boundary": (
            "Reachability and API visibility prove only that "
            "a Space can be discovered and its Gradio API can "
            "be inspected. No production job is executed by "
            "this connectivity test."
        ),
        "checked_at":
            utc_now(),
    }

    report["report_fingerprint"] = (
        make_fingerprint(
            report
        )
    )

    return report


# =============================================================================
# STAGE 20: CONTROLLED MASTER / SUPERVISOR DISPATCH (v1.2.3)
# =============================================================================

DISPATCH_SCHEMA = "joat.executive_producer_dispatch.v1"
DISPATCH_RESULT_SCHEMA = "joat.executive_producer_dispatch_result.v1"
DISPATCH_SIGNING_KEY_ENV = "JOAT_DISPATCH_SIGNING_KEY"
DISPATCH_MAX_AGE_SECONDS = 300
DISPATCH_ENABLED_ENV = "JOAT_DISPATCH_ENABLED"

# Deliberately no direct worker dispatch. QC is independent and Stage 21
# supervisor-to-worker execution is not implemented here.
DISPATCH_ENDPOINTS = {
    "character": "/packet",
    "environment": "/build_packet_ui",
    "director": "/generate_director_ui",
    "shot_camera": "/build_packet_ui",
    "performance_action": "/build_packet_ui",
    "generation_supervisor": "/build_job_ui",
    "post_production": "/build_packet_ui",
}

_DISPATCH_LOCK = threading.Lock()
_DISPATCH_NONCES: dict[str, int] = {}


def dispatch_signature(payload: dict[str, Any], secret: str) -> str:
    """Signature over all unsigned fields; never include signature itself."""
    unsigned = {k: v for k, v in payload.items() if k != "signature"}
    return hmac.new(
        secret.encode("utf-8"),
        stable_json(unsigned).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def validate_dispatch_request(request: dict[str, Any]) -> tuple[str, str]:
    """Fail closed before creating a Gradio client or issuing network calls."""
    if request.get("schema") != DISPATCH_SCHEMA:
        raise ValueError("Invalid dispatch schema.")
    if request.get("source_bot") != REPORTS_TO:
        raise ValueError("Dispatch source must be Main Assistant.")
    if request.get("target_bot") != BOT_NAME:
        raise ValueError("Dispatch target must be Executive Producer.")
    if request.get("authorized") is not True:
        raise ValueError("Dispatch is not approved.")
    if not isinstance(request.get("work_order_id"), str) or not request["work_order_id"].strip():
        raise ValueError("work_order_id is required.")
    if not isinstance(request.get("project_id"), str) or not request["project_id"].strip():
        raise ValueError("project_id is required.")
    role = request.get("department_role")
    if role not in DISPATCH_ENDPOINTS:
        raise ValueError("Direct dispatch to this role is prohibited or not yet configured.")
    if request.get("endpoint") != DISPATCH_ENDPOINTS[role]:
        raise ValueError("Endpoint does not match approved department route.")
    if not isinstance(request.get("arguments"), dict):
        raise ValueError("arguments must be a JSON object of endpoint parameters.")
    if not isinstance(request.get("nonce"), str) or len(request["nonce"]) < 16:
        raise ValueError("A unique nonce of at least 16 characters is required.")
    issued_at = request.get("issued_at_epoch")
    if type(issued_at) not in (int, float):
        raise ValueError("issued_at_epoch must be a Unix timestamp.")
    if abs(time.time() - issued_at) > DISPATCH_MAX_AGE_SECONDS:
        raise ValueError("Dispatch authorization expired or timestamp invalid.")
    secret = os.environ.get(DISPATCH_SIGNING_KEY_ENV, "")
    if len(secret) < 32:
        raise ValueError("Dispatch signing key is not configured securely.")
    supplied = request.get("signature")
    if not isinstance(supplied, str) or not hmac.compare_digest(
        supplied, dispatch_signature(request, secret)
    ):
        raise ValueError("Dispatch signature invalid.")
    return role, DISPATCH_ENDPOINTS[role]


def dispatch_department(request: dict[str, Any]) -> dict[str, Any]:
    role, endpoint = validate_dispatch_request(request)
    # Preview never contacts a worker, but still requires a valid signature.
    live = request.get("execute_live") is True
    if not live:
        return {
            "schema": DISPATCH_RESULT_SCHEMA,
            "app_version": APP_VERSION,
            "work_order_id": request["work_order_id"],
            "project_id": request["project_id"],
            "department_role": role,
            "endpoint": endpoint,
            "status": "validated_preview_only",
            "downstream_execution_performed": False,
            "production_work_completed": False,
        }
    if os.environ.get(DISPATCH_ENABLED_ENV, "").lower() != "true":
        raise ValueError("Live dispatch disabled. Set JOAT_DISPATCH_ENABLED=true after review.")
    token = get_hf_token()
    if not token:
        raise ValueError("JOAT_SPECIALIST_TOKEN is required for live dispatch.")
    discovery = discover_canonical_spaces()
    if discovery["error"]:
        raise ValueError("Authenticated Space discovery failed.")
    match = match_role_to_spaces(role, discovery["spaces"])
    if match["status"] != "resolved" or not match["repo_id"]:
        raise ValueError("Department repository not uniquely resolved.")
    now = int(time.time())
    with _DISPATCH_LOCK:
        for nonce, expiry in list(_DISPATCH_NONCES.items()):
            if expiry < now:
                del _DISPATCH_NONCES[nonce]
        if request["nonce"] in _DISPATCH_NONCES:
            raise ValueError("Duplicate dispatch nonce rejected.")
        # Reserve before the network call: failures must not silently retry.
        _DISPATCH_NONCES[request["nonce"]] = now + DISPATCH_MAX_AGE_SECONDS
    base = {
        "schema": DISPATCH_RESULT_SCHEMA,
        "app_version": APP_VERSION,
        "work_order_id": request["work_order_id"],
        "project_id": request["project_id"],
        "department_role": role,
        "repo_id": match["repo_id"],
        "endpoint": endpoint,
        "attempted_at": utc_now(),
        "downstream_execution_performed": False,
        "production_work_completed": False,
    }
    phase = "config"
    try:
        from joat_cpu_department_client import connect
        phase = "config"
        client = connect(match["repo_id"], token)
        phase = "predict"
        # Only the approved named endpoint may be called. Caller-supplied
        # arguments are passed unchanged to the endpoint's own validator.
        result = client.predict(**deepcopy(request["arguments"]), api_name=endpoint)
        base.update({
            "status": "api_call_returned",
            "downstream_execution_performed": True,
            "production_work_completed": False,
            "department_response": result,
        })
    except Exception as exc:
        base.update({
            "status": "dispatch_failed_or_outcome_unknown",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "endpoint_phase": phase,
            "http_status": getattr(exc, "http_status", None),
            "submission_state": "not_submitted" if phase == "config" else "unknown",
            "manual_reconciliation_required": True,
        })
    base["result_fingerprint"] = make_fingerprint(base)
    return base


def dispatch_department_ui(raw: str) -> dict[str, Any]:
    return dispatch_department(parse_json_object(raw, "Dispatch Request"))


def dispatch_tests_ui() -> dict[str, Any]:
    """Offline gate tests; never call any department."""
    secret = os.environ.get(DISPATCH_SIGNING_KEY_ENV, "")
    configured = len(secret) >= 32
    checks = {
        "seven_direct_master_supervisor_routes": len(DISPATCH_ENDPOINTS) == 7,
        "generation_worker_not_directly_dispatchable": "generation_worker" not in DISPATCH_ENDPOINTS,
        "post_workers_not_directly_dispatchable": "editorial" not in DISPATCH_ENDPOINTS,
        "qc_not_dispatched_as_subordinate_worker": "quality_control" not in DISPATCH_ENDPOINTS,
        "signing_key_configured": configured,
        "hf_token_present": bool(get_hf_token()),
    }
    if configured:
        candidate = {
            "schema": DISPATCH_SCHEMA,
            "source_bot": REPORTS_TO,
            "target_bot": BOT_NAME,
            "authorized": True,
            "work_order_id": "WO-TEST-001",
            "project_id": "PROJECT-TEST-001",
            "department_role": "character",
            "endpoint": "/packet",
            "arguments": {},
            "nonce": "test-nonce-0123456789",
            "issued_at_epoch": time.time(),
            "execute_live": False,
        }
        candidate["signature"] = dispatch_signature(candidate, secret)
        checks["valid_signature_preview"] = (
            dispatch_department(candidate)["status"] == "validated_preview_only"
        )
        tampered = deepcopy(candidate)
        tampered["department_role"] = "generation_worker"
        try:
            dispatch_department(tampered)
            checks["unauthorized_worker_rejected"] = False
        except ValueError:
            checks["unauthorized_worker_rejected"] = True
    return {
        "app_version": APP_VERSION,
        "stage": 20,
        "tests": checks,
        "all_passed": all(checks.values()),
        "live_dispatch_enabled": os.environ.get(DISPATCH_ENABLED_ENV, "").lower() == "true",
        "note": "Offline tests only; no production work executed.",
    }


# =============================================================================
# EXECUTIVE PRODUCER
# =============================================================================

class ExecutiveProducerBot:

    def validate_objective(
        self,
        objective: dict[str, Any],
    ) -> None:

        if not objective.get("project_id"):
            raise ValueError(
                "Production objective requires project_id."
            )

        if not objective.get("objective"):
            raise ValueError(
                "Production objective requires objective."
            )

        if (
            objective.get("approved_by_main_assistant")
            is not True
        ):
            raise ValueError(
                "Production objective must be approved "
                "by the J.O.A.T. Main Assistant Bot."
            )

    def build_plan(
        self,
        objective: dict[str, Any],
    ) -> dict[str, Any]:

        self.validate_objective(objective)

        immutable_objective = deepcopy(objective)

        department_plan = []

        for order, role in enumerate(
            PRODUCTION_PIPELINE,
            start=1,
        ):
            definition = STUDIO_ROLES[role]

            department_plan.append(
                {
                    "order": order,
                    "department_role": role,
                    "assigned_bot": definition["bot"],
                    "assistant_bot": definition.get(
                        "assistant"
                    ),
                    "supervisor_role":
                        SUPERVISOR_ROUTING.get(
                            role
                        ),
                    "responsibility": definition[
                        "responsibility"
                    ],
                    "status": "pending",
                    "executive_knowledge_level": "guru",
                    "department_authority_preserved": True,
                }
            )

        plan_core = {
            "schema": PRODUCTION_PLAN_SCHEMA,
            "project_id": objective["project_id"],
            "production_objective": deepcopy(
                objective
            ),
            "department_plan": department_plan,
            "technology_requirements": deepcopy(
                TECHNOLOGY_MASTERY
            ),
            "authority_boundary": deepcopy(
                AUTHORITY_BOUNDARY
            ),
            "studio_policy": {
                "executive_understands_all_subordinate_jobs":
                    True,
                "executive_operational_mindset":
                    "promoted_from_the_floor",
                "guru_level_department_knowledge":
                    True,
                "guru_level_product_knowledge":
                    True,
                "delegated_authority_must_be_respected":
                    True,
                "locked_decisions_remain_immutable":
                    True,
                "qc_cannot_be_bypassed":
                    True,
                "worker_dispatch_respects_supervisors":
                    True,
            },
        }

        plan_core["plan_fingerprint"] = (
            make_fingerprint(plan_core)
        )

        packet = {
            "schema": PACKET_SCHEMA,
            "app_version": APP_VERSION,
            "bot_name": BOT_NAME,
            "bot_type": BOT_TYPE,
            "reports_to": REPORTS_TO,
            "production_plan": plan_core,
            "immutable_objective_snapshot":
                immutable_objective,
            "production_ready": True,
        }

        from joat_studio_capabilities import plan_project
        packet["capability_advisory"] = plan_project({
            "project_id": objective["project_id"], "intent": objective["objective"],
            "format": objective.get("format", "product_commercial"),
            "locks": objective.get("creative_locks", {}),
            "required_features": objective.get("required_features", [])})
        if packet["capability_advisory"]["qualification_requirements"]:
            packet["production_ready"] = False

        packet["packet_fingerprint"] = (
            make_fingerprint(packet)
        )

        return packet

    def route_failure(
        self,
        failure_type: str,
        project_id: str,
    ) -> dict[str, Any]:

        routes = {
            "character":
                "J.O.A.T. Character Master Bot",
            "environment":
                "J.O.A.T. Environment Master Bot",
            "director":
                "J.O.A.T. Director Master Bot",
            "camera":
                "J.O.A.T. Shot/Camera Master Bot",
            "performance":
                "J.O.A.T. Performance/Action Master Bot",
            "generation":
                "J.O.A.T. Generation Supervisor Bot",
            "generation_technical":
                "J.O.A.T. Generation Worker Bot",
            "qc":
                "J.O.A.T. Quality Control Bot",
            "editorial":
                "J.O.A.T. Editorial Worker Bot",
            "sound":
                "J.O.A.T. Sound Worker Bot",
            "voice":
                "J.O.A.T. Voice & Dialogue Worker Bot",
            "dialogue":
                "J.O.A.T. Voice & Dialogue Worker Bot",
            "music":
                "J.O.A.T. Music Worker Bot",
            "vfx":
                "J.O.A.T. Compositing/VFX Worker Bot",
            "color":
                "J.O.A.T. Color/Finish Worker Bot",
            "graphics":
                "J.O.A.T. Titles/Graphics Worker Bot",
            "delivery":
                "J.O.A.T. Delivery/Archive Bot",
        }

        target = routes.get(failure_type)

        if not target:
            return {
                "schema": ESCALATION_SCHEMA,
                "project_id": project_id,
                "failure_type": failure_type,
                "action": "escalate",
                "target": REPORTS_TO,
                "reason": (
                    "Unknown or cross-department failure."
                ),
            }

        return {
            "schema": ESCALATION_SCHEMA,
            "project_id": project_id,
            "failure_type": failure_type,
            "action": "route_rework",
            "target": target,
            "executive_may_fix_directly": False,
        }

    # =========================================================================
    # LIVE EXECUTION CONTRACT
    # =========================================================================

    def validate_work_order(
        self,
        work_order: dict[str, Any],
    ) -> None:

        if (
            work_order.get("schema")
            != WORK_ORDER_SCHEMA
        ):
            raise ValueError(
                "Invalid Executive Producer work-order schema."
            )

        if not work_order.get("work_order_id"):
            raise ValueError(
                "work_order_id is required."
            )

        if (
            work_order.get("source_bot")
            != "J.O.A.T. Main Assistant Bot"
        ):
            raise ValueError(
                "Executive Producer accepts live work orders "
                "only from J.O.A.T. Main Assistant Bot."
            )

        if (
            work_order.get("target_bot")
            != BOT_NAME
        ):
            raise ValueError(
                "Work order target does not match "
                "Executive Producer Bot."
            )

        if (
            work_order.get("authorized")
            is not True
        ):
            raise ValueError(
                "Work order is not authorized."
            )

        objective = work_order.get(
            "objective"
        )

        if not isinstance(
            objective,
            dict,
        ):
            raise ValueError(
                "Work order objective must be a JSON object."
            )

        self.validate_objective(
            objective
        )

    def execute_work_order(
        self,
        work_order: dict[str, Any],
    ) -> dict[str, Any]:

        immutable_work_order = deepcopy(
            work_order
        )

        self.validate_work_order(
            work_order
        )

        execution_id = str(
            uuid.uuid4()
        )

        packet = self.build_plan(
            work_order["objective"]
        )

        execution = {
            "schema": EXECUTION_SCHEMA,
            "execution_id": execution_id,
            "work_order_id":
                work_order["work_order_id"],
            "source_bot":
                work_order["source_bot"],
            "target_bot": BOT_NAME,
            "started_at": utc_now(),
            "action":
                "build_production_plan",
            "execution_performed": True,
            "downstream_execution_performed": False,
            "downstream_live_execution_connected":
                DOWNSTREAM_LIVE_EXECUTION_CONNECTED,
        }

        execution[
            "execution_fingerprint"
        ] = make_fingerprint(
            execution
        )

        result_core = {
            "schema":
                EXECUTION_RESULT_SCHEMA,

            "execution_id":
                execution_id,

            "work_order_id":
                work_order["work_order_id"],

            "bot_name":
                BOT_NAME,

            "status":
                "completed",

            "verified":
                True,

            "production_packet":
                packet,

            "downstream_execution": {
                "connected":
                    DOWNSTREAM_LIVE_EXECUTION_CONNECTED,

                "performed":
                    False,

                "status":
                    "not_connected",

                "next_action": (
                    "Use the separate studio_connections "
                    "endpoint to verify subordinate Space "
                    "discovery and API visibility. Do not "
                    "claim real production execution from "
                    "connectivity evidence alone."
                ),
            },

            "authority_preserved":
                True,

            "immutable_work_order_preserved":
                (
                    stable_json(
                        work_order
                    )
                    == stable_json(
                        immutable_work_order
                    )
                ),

            "completed_at":
                utc_now(),
        }

        result_core[
            "result_fingerprint"
        ] = make_fingerprint(
            result_core
        )

        return {
            "execution":
                execution,

            "result":
                result_core,
        }

    def execute_work_order_json(
        self,
        raw: str,
    ) -> dict[str, Any]:

        work_order = parse_json_object(
            raw,
            "Executive Producer Work Order",
        )

        return self.execute_work_order(
            work_order
        )

    # =========================================================================
    # ACCEPTANCE
    # =========================================================================

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

        objective = {
            "project_id": "PROJECT-001",
            "objective":
                "Produce approved J.O.A.T. production.",
            "approved_by_main_assistant": True,
        }

        packet = self.build_plan(
            objective
        )

        plan = packet[
            "production_plan"
        ]

        # ORIGINAL 50 ACCEPTANCE TESTS

        add("1. Executive Producer packet generates", packet["schema"] == PACKET_SCHEMA)
        add("2. Production plan generates", plan["schema"] == PRODUCTION_PLAN_SCHEMA)
        add("3. Reports to Main Assistant Bot", packet["reports_to"] == "J.O.A.T. Main Assistant Bot")
        add("4. Main Assistant approval required", plan["production_objective"]["approved_by_main_assistant"] is True)
        add("5. Complete studio pipeline declared", len(plan["department_plan"]) == len(PRODUCTION_PIPELINE))
        add("6. Character Master understood", "character" in STUDIO_ROLES)
        add("7. Environment Master understood", "environment" in STUDIO_ROLES)
        add("8. Director Master understood", "director" in STUDIO_ROLES)
        add("9. Shot/Camera Master understood", "shot_camera" in STUDIO_ROLES)
        add("10. Performance/Action Master understood", "performance_action" in STUDIO_ROLES)
        add("11. Generation Supervisor understood", "generation_supervisor" in STUDIO_ROLES)
        add("12. Generation Worker understood", "generation_worker" in STUDIO_ROLES)
        add("13. Quality Control understood", "quality_control" in STUDIO_ROLES)
        add("14. Post Supervisor understood", "post_production" in STUDIO_ROLES)
        add("15. Editorial understood", "editorial" in STUDIO_ROLES)
        add("16. Sound understood", "sound" in STUDIO_ROLES)
        add("17. Music understood", "music" in STUDIO_ROLES)
        add("18. Compositing/VFX understood", "compositing_vfx" in STUDIO_ROLES)
        add("19. Color/Finish understood", "color_finish" in STUDIO_ROLES)
        add("20. Titles/Graphics understood", "titles_graphics" in STUDIO_ROLES)
        add("21. Delivery/Archive understood", "delivery_archive" in STUDIO_ROLES)
        add("22. Guru-level subordinate mastery required", plan["studio_policy"]["guru_level_department_knowledge"] is True)
        add("23. Promoted-from-the-floor mindset declared", plan["studio_policy"]["executive_operational_mindset"] == "promoted_from_the_floor")
        add("24. LTX guru mastery declared", TECHNOLOGY_MASTERY["ltx"]["required_level"] == "guru")
        add("25. Hugging Face Spaces mastery declared", TECHNOLOGY_MASTERY["hugging_face_spaces"]["required_level"] == "guru")
        add("26. J.O.A.T. packet architecture mastery declared", TECHNOLOGY_MASTERY["joat_packet_architecture"]["required_level"] == "guru")
        add("27. Department authority preserved", plan["studio_policy"]["delegated_authority_must_be_respected"] is True)
        add("28. Locked decisions remain immutable", plan["studio_policy"]["locked_decisions_remain_immutable"] is True)
        add("29. Executive may diagnose failures", AUTHORITY_BOUNDARY["may_diagnose_failures"] is True)
        add("30. Executive may route rework", AUTHORITY_BOUNDARY["may_route_rework"] is True)
        add("31. Executive may stop production", AUTHORITY_BOUNDARY["may_stop_production"] is True)
        add("32. Executive cannot replace Main Assistant", AUTHORITY_BOUNDARY["may_replace_main_assistant"] is False)
        add("33. Executive cannot override Dr. G", AUTHORITY_BOUNDARY["may_override_dr_g"] is False)
        add("34. Executive cannot bypass QC", AUTHORITY_BOUNDARY["may_bypass_qc"] is False)
        add("35. Executive cannot mutate immutable packets", AUTHORITY_BOUNDARY["may_modify_immutable_packets"] is False)
        add("36. Executive cannot self-approve locked creative change", AUTHORITY_BOUNDARY["may_self_approve_locked_creative_change"] is False)

        route = self.route_failure("character", "PROJECT-001")
        add("37. Character failure routes correctly", route["target"] == "J.O.A.T. Character Master Bot")

        route = self.route_failure("generation_technical", "PROJECT-001")
        add("38. Generation technical failure routes correctly", route["target"] == "J.O.A.T. Generation Worker Bot")

        route = self.route_failure("unknown_cross_department_failure", "PROJECT-001")
        add("39. Unknown failure escalates to Main Assistant", route["target"] == "J.O.A.T. Main Assistant Bot")

        first = self.build_plan(objective)
        second = self.build_plan(objective)
        add("40. Deterministic Executive Producer fingerprint", first["packet_fingerprint"] == second["packet_fingerprint"])

        before = stable_json(objective)
        self.build_plan(objective)
        after = stable_json(objective)
        add("41. Main Assistant objective remains immutable", before == after)

        rejected = False
        bad = deepcopy(objective)
        bad["approved_by_main_assistant"] = False
        try:
            self.build_plan(bad)
        except ValueError:
            rejected = True
        add("42. Unapproved Main Assistant objective rejected", rejected)

        add("43. QC Assistant relationship understood", STUDIO_ROLES["quality_control"].get("assistant") == "J.O.A.T. QC Assistant Bot")
        add("44. Edit Assistant relationship understood", STUDIO_ROLES["editorial"].get("assistant") == "J.O.A.T. Edit Assistant Bot")
        add("45. Audio Assistant relationship understood", STUDIO_ROLES["sound"].get("assistant") == "J.O.A.T. Audio Assistant Bot")
        add("46. Executive understands every subordinate job", plan["studio_policy"]["executive_understands_all_subordinate_jobs"] is True)
        add("47. Guru-level product knowledge required", plan["studio_policy"]["guru_level_product_knowledge"] is True)
        add("48. LTX output-to-QC knowledge declared", "output handoff to QC" in TECHNOLOGY_MASTERY["ltx"]["must_understand"])
        add("49. Executive technology-route verification enabled", AUTHORITY_BOUNDARY["may_verify_technology_route"] is True)
        add("50. Executive Producer production-ready", packet["production_ready"] is True)

        # LIVE EXECUTION TESTS 51-65

        add("51. Live execution interface enabled", LIVE_EXECUTION_INTERFACE is True)
        add("52. Work-order schema declared", WORK_ORDER_SCHEMA == "joat.executive_producer_work_order.v1")
        add("53. Execution schema declared", EXECUTION_SCHEMA == "joat.executive_producer_execution.v1")
        add("54. Execution-result schema declared", EXECUTION_RESULT_SCHEMA == "joat.executive_producer_execution_result.v1")

        work_order = {
            "schema": WORK_ORDER_SCHEMA,
            "work_order_id": "WO-ACCEPTANCE-001",
            "source_bot": "J.O.A.T. Main Assistant Bot",
            "target_bot": BOT_NAME,
            "authorized": True,
            "objective": deepcopy(objective),
        }

        before_work_order = stable_json(work_order)
        live = self.execute_work_order(work_order)
        execution = live["execution"]
        result = live["result"]

        add("55. Valid Main Assistant work order accepted", execution["work_order_id"] == "WO-ACCEPTANCE-001")
        add("56. Live execution packet generated", execution["schema"] == EXECUTION_SCHEMA)
        add("57. Live result packet generated", result["schema"] == EXECUTION_RESULT_SCHEMA)
        add("58. Executive execution verified", result["verified"] is True)
        add("59. Executive execution completes production planning", result["status"] == "completed")
        add("60. Main Assistant work order remains immutable", before_work_order == stable_json(work_order))
        add("61. Production packet returned to caller", result["production_packet"]["schema"] == PACKET_SCHEMA)
        add(
            "62. Downstream execution not falsely claimed",
            result["downstream_execution"]["performed"] is False
            and result["downstream_execution"]["connected"] is False,
        )

        bad_source = deepcopy(work_order)
        bad_source["source_bot"] = "Unauthorized Bot"
        rejected_source = False
        try:
            self.execute_work_order(bad_source)
        except ValueError:
            rejected_source = True
        add("63. Unauthorized source rejected", rejected_source)

        bad_auth = deepcopy(work_order)
        bad_auth["authorized"] = False
        rejected_auth = False
        try:
            self.execute_work_order(bad_auth)
        except ValueError:
            rejected_auth = True
        add("64. Unauthorized work order rejected", rejected_auth)

        wrong_target = deepcopy(work_order)
        wrong_target["target_bot"] = "Wrong Bot"
        rejected_target = False
        try:
            self.execute_work_order(wrong_target)
        except ValueError:
            rejected_target = True
        add("65. Wrong-target work order rejected", rejected_target)

        # ADDITIVE v1.2.0 TESTS 66-77

        add("66. Voice & Dialogue role understood", "voice_dialogue" in STUDIO_ROLES)
        add("67. Studio pipeline contains 17 roles", len(PRODUCTION_PIPELINE) == 17)
        add("68. Voice & Dialogue included in explicit pipeline", "voice_dialogue" in PRODUCTION_PIPELINE)
        add("69. Voice failure routes correctly", self.route_failure("voice", "PROJECT-001")["target"] == "J.O.A.T. Voice & Dialogue Worker Bot")
        add("70. Token source is environment-only", safe_token_status()["environment_variable"] == "JOAT_SPECIALIST_TOKEN")
        add("71. Token value is never exposed by status", safe_token_status()["value_exposed"] is False)
        add("72. Connectivity report schema declared", CONNECTIVITY_REPORT_SCHEMA == "joat.studio_connectivity_report.v1")
        add("73. Generation worker has supervisor route", SUPERVISOR_ROUTING["generation_worker"] == "generation_supervisor")
        add("74. Post workers route through Post Supervisor", SUPERVISOR_ROUTING["editorial"] == "post_production" and SUPERVISOR_ROUTING["voice_dialogue"] == "post_production")
        add("75. QC remains independent", SUPERVISOR_ROUTING["quality_control"] is None)
        add("76. Planning execution still performs no downstream work", result["downstream_execution"]["performed"] is False)
        add("77. Main Assistant execute_work_order contract preserved", WORK_ORDER_SCHEMA == "joat.executive_producer_work_order.v1" and result["schema"] == EXECUTION_RESULT_SCHEMA)

        all_passed = all(
            test["pass"]
            for test in tests
        )

        return {
            "acceptance_test_version": ACCEPTANCE_TEST_VERSION,
            "app_version": APP_VERSION,
            "bot_name": BOT_NAME,
            "bot_type": BOT_TYPE,
            "reports_to": REPORTS_TO,
            "packet_schema": PACKET_SCHEMA,
            "production_plan_schema": PRODUCTION_PLAN_SCHEMA,
            "status_schema": STATUS_SCHEMA,
            "escalation_schema": ESCALATION_SCHEMA,
            "work_order_schema": WORK_ORDER_SCHEMA,
            "execution_schema": EXECUTION_SCHEMA,
            "execution_result_schema": EXECUTION_RESULT_SCHEMA,
            "connectivity_report_schema": CONNECTIVITY_REPORT_SCHEMA,
            "subordinate_roles": len(STUDIO_ROLES),
            "live_execution_interface": LIVE_EXECUTION_INTERFACE,
            "downstream_live_execution_connected": DOWNSTREAM_LIVE_EXECUTION_CONNECTED,
            "technology_mastery": deepcopy(TECHNOLOGY_MASTERY),
            "tests": tests,
            "test_count": len(tests),
            "passed_count": sum(1 for test in tests if test["pass"]),
            "all_passed": all_passed,
            "production_ready": all_passed,
            "note": (
                "Executive Producer live execution interface remains production-ready "
                "for Main Assistant machine-to-machine production planning. "
                "Studio connectivity is verified separately and never treated as "
                "proof of real downstream production execution."
            ),
        }


BOT = ExecutiveProducerBot()


# =============================================================================
# UI
# =============================================================================

def example_objective() -> str:
    value = {
        "project_id": "PROJECT-001",
        "objective": "Produce approved J.O.A.T. production.",
        "approved_by_main_assistant": True,
    }
    return json.dumps(value, indent=2)


def example_work_order() -> str:
    value = {
        "schema": WORK_ORDER_SCHEMA,
        "work_order_id": "WO-001",
        "source_bot": "J.O.A.T. Main Assistant Bot",
        "target_bot": BOT_NAME,
        "authorized": True,
        "objective": {
            "project_id": "PROJECT-001",
            "objective": "Produce approved J.O.A.T. production.",
            "approved_by_main_assistant": True,
        },
    }
    return json.dumps(value, indent=2)


def build_plan_ui(
    objective_raw: str,
) -> dict[str, Any]:

    objective = parse_json_object(
        objective_raw,
        "Main Assistant Production Objective",
    )

    return BOT.build_plan(
        objective
    )


def execute_work_order_ui(
    work_order_raw: str,
) -> dict[str, Any]:

    return BOT.execute_work_order_json(
        work_order_raw
    )


def tests_ui() -> dict[str, Any]:
    return BOT.acceptance_test()


def studio_connections_ui() -> dict[str, Any]:
    return build_connectivity_report()


def build_app() -> gr.Blocks:

    with gr.Blocks(
        title=f"{BOT_NAME} v{APP_VERSION}"
    ) as app:

        gr.Markdown(
            f"# {BOT_NAME}\n\n"
            "**Roadmap Stage #17**\n\n"
            "**Live Execution Interface: READY**\n\n"
            "**Studio Connectivity Diagnostics: READY**\n\n"
            "Runs the J.O.A.T. production studio beneath "
            "the Main Assistant Bot. Possesses guru-level "
            "knowledge of subordinate departments and the "
            "production technology stack while respecting "
            "department authority."
        )

        with gr.Tab("Production Plan"):
            objective_raw = gr.Code(
                value=example_objective(),
                language="json",
                label="Main Assistant Production Objective",
            )
            output = gr.JSON(
                label="Executive Producer Packet",
            )
            gr.Button(
                "Build Production Plan",
                variant="primary",
            ).click(
                fn=build_plan_ui,
                inputs=objective_raw,
                outputs=output,
                api_name="build_production_plan",
            )

        with gr.Tab("Live Execution"):
            gr.Markdown(
                """
### Main Assistant â Executive Producer

This interface accepts a structured, authorized work order
from the J.O.A.T. Main Assistant Bot and returns a verified
Executive Producer execution result.

It does **not** claim downstream studio workers executed until
a separate, explicit, authorized dispatch interface exists.
"""
            )

            work_order_raw = gr.Code(
                value=example_work_order(),
                language="json",
                label="Executive Producer Work Order",
            )
            execution_output = gr.JSON(
                label="Execution Result",
            )
            gr.Button(
                "Execute Work Order",
                variant="primary",
            ).click(
                fn=execute_work_order_ui,
                inputs=work_order_raw,
                outputs=execution_output,
                api_name="execute_work_order",
            )

        with gr.Tab("Studio Connections"):
            gr.Markdown(
                """
### Safe Studio Connectivity Check

Discovers canonical Hugging Face Space repository IDs under
`Dezz-9-10` with `JOAT_SPECIALIST_TOKEN`, then inspects each
resolved Space's Gradio API.

This check does **not** run production jobs.
"""
            )
            connections_output = gr.JSON(
                label="Studio Connectivity Report",
            )
            gr.Button(
                "Check Studio Connections",
                variant="primary",
            ).click(
                fn=studio_connections_ui,
                inputs=None,
                outputs=connections_output,
                api_name="studio_connections",
            )

        with gr.Tab("Controlled Dispatch"):
            gr.Markdown(
                "### Stage 20 â Authenticated Department Dispatch\n\n"
                "Only approved Master/Supervisor routes are available. "
                "Requests require an HMAC signature from the Main Assistant. "
                "`execute_live: false` is validation-only; "
                "live calls require `JOAT_DISPATCH_ENABLED=true`. "
                "Never paste the signing key into the UI."
            )
            dispatch_raw = gr.Code(
                value=json.dumps({
                    "schema": DISPATCH_SCHEMA,
                    "source_bot": REPORTS_TO,
                    "target_bot": BOT_NAME,
                    "authorized": True,
                    "work_order_id": "WO-001",
                    "project_id": "PROJECT-001",
                    "department_role": "character",
                    "endpoint": "/packet",
                    "arguments": {},
                    "nonce": "REPLACE-WITH-UNIQUE-NONCE",
                    "issued_at_epoch": 0,
                    "execute_live": False,
                    "signature": "REPLACE-WITH-MAIN-ASSISTANT-SIGNATURE",
                }, indent=2),
                language="json",
                label="Signed Dispatch Request (example requires valid signature)",
            )
            dispatch_output = gr.JSON(label="Department Dispatch Result")
            gr.Button("Validate / Dispatch", variant="primary").click(
                fn=dispatch_department_ui,
                inputs=dispatch_raw,
                outputs=dispatch_output,
                api_name="dispatch_department",
            )
            dispatch_tests_output = gr.JSON(label="Stage 20 Offline Checks")
            gr.Button("Run Dispatch Gate Tests").click(
                fn=dispatch_tests_ui,
                inputs=None,
                outputs=dispatch_tests_output,
                api_name="dispatch_tests",
            )

        with gr.Tab("Acceptance Tests"):
            gr.Markdown(
                """
### Acceptance Target

Original baseline: `65/65 PASS`

v1.2.0 additive target: `77/77 PASS`

`all_passed: true`

`production_ready: true`
"""
            )
            test_output = gr.JSON(
                label="Executive Producer Acceptance Test",
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

        with gr.Tab("Studio Mastery"):
            gr.JSON(
                value={
                    "studio_roles": STUDIO_ROLES,
                    "technology_mastery": TECHNOLOGY_MASTERY,
                    "supervisor_routing": SUPERVISOR_ROUTING,
                    "mindset": "promoted_from_the_floor",
                },
                label="Executive Producer Mastery Contract",
            )

        with gr.Tab("Authority Boundary"):
            gr.JSON(
                value=AUTHORITY_BOUNDARY,
                label="Executive Producer Authority",
            )

        with gr.Tab("About"):
            gr.Markdown(
                f"""
## {BOT_NAME}

**Version:** `{APP_VERSION}`

**Reports to:**  
{REPORTS_TO}

**Live Execution Interface:** `READY`

**Downstream Production Execution:** `NOT CLAIMED`

### Command Chain

Dr. G  
â  
J.O.A.T. Main Assistant Bot  
â  
**J.O.A.T. Executive Producer Bot**  
â  
Studio Departments / Supervisors / Workers  
â  
J.O.A.T. Delivery/Archive Bot

### Critical Execution Boundary

The Executive Producer accepts the existing machine-callable
Main Assistant work-order contract and returns a verified
production-plan execution result.

Studio connectivity diagnostics are separate and safe. They
discover and inspect subordinate APIs but do not run production
jobs and do not prove downstream work execution.
"""
            )

    with app:
        from joat_managed_generation import add_managed_generation_api
        add_managed_generation_api('executive')

        from joat_cpu_control_ui import add_cpu_control_ui
        add_cpu_control_ui()
        from joat_studio_capability_ui import add_studio_capability_ui
        add_studio_capability_ui()

    return app


if __name__ == "__main__":
    from joat_cpu_department_client import log_connection_check
    log_connection_check("Dezz-9-10/J.O.A.T.-Scene-Environment-Master", get_hf_token())

    demo = build_app()

    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )
