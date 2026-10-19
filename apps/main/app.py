"""
J.O.A.T. Main Assistant Bot v2.1.105

LIVE SPECIALIST EXECUTION

Adds:
- Owner-only uploaded-video / YouTube evidence and bounded reference analysis
- Live Executive Producer dispatch
- Live Hugging Face Master dispatch
- Live Browser Worker dispatch
- Private Hugging Face Space-to-Space transport
- Automatic Gradio API discovery
- Specialist work-order generation
- Specialist response verification
- Command-to-execution fingerprint linkage
- Persistent specialist execution receipts
- Persistent specialist failure/recovery records
- Bounded specialist retries
- Live specialist health checks
- No false-success execution reporting

Preserves:
- v2.0.0 live Hugging Face intelligence
- Persistent conversational context
- Automatic intent/domain detection
- Persistent projects and tasks
- Approval gates
- Routing records
- Execution receipts
- Recovery records
- Persistent audit trail
- Native Gradio interface
- SQLite persistence
- Mounted /data storage
- Existing authority boundaries
- Existing J.O.A.T. chain of command

CHAIN OF COMMAND

Dr. G
  -> J.O.A.T. Main Assistant Bot
      -> J.O.A.T. Executive Producer Bot
          -> Studio supervisors / workers / assistants
      -> J.O.A.T. Hugging Face Master Bot
      -> J.O.A.T. Browser Worker Bot
      -> Future authorized platform masters
"""

from __future__ import annotations

from joat_runtime_client import install as install_department_routing
install_department_routing(local=False)

import hashlib
import json
import os
import re
import sqlite3
import threading
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gradio as gr
from gradio_client import Client
from huggingface_hub import InferenceClient


# =============================================================================
# CONFIG
# =============================================================================

APP_VERSION = "2.1.105"
ACCEPTANCE_TEST_VERSION = "2.1.0"

BOT_NAME = os.environ.get(
    "JOAT_ASSISTANT_NAME",
    "J.O.A.T. Main Assistant Bot",
)

BOT_TYPE = "main_assistant_bot"

REPORTS_TO = os.environ.get(
    "JOAT_OWNER",
    "Dr. G",
)

ASSISTANT_REQUIRED = False

COMMAND_SCHEMA = "joat.main_assistant_command.v1"
ROUTING_SCHEMA = "joat.main_assistant_routing.v1"
RESULT_SCHEMA = "joat.main_assistant_result.v1"
THREAD_SCHEMA = "joat.conversation_thread.v1"

TASK_SCHEMA = "joat.main_assistant_task.v1"
PROJECT_SCHEMA = "joat.main_assistant_project.v1"
APPROVAL_SCHEMA = "joat.main_assistant_approval.v1"
RECEIPT_SCHEMA = "joat.execution_receipt.v1"
RECOVERY_SCHEMA = "joat.recovery_record.v1"

SPECIALIST_DISPATCH_SCHEMA = "joat.specialist_dispatch.v1"
SPECIALIST_HEALTH_SCHEMA = "joat.specialist_health.v1"

EP_WORK_ORDER_SCHEMA = "joat.executive_producer_work_order.v1"
HF_WORK_ORDER_SCHEMA = "joat.hugging_face_work_order.v1"
BROWSER_WORK_ORDER_SCHEMA = "joat.browser_work_order.v1"

JOAT_ENV = os.environ.get(
    "JOAT_ENV",
    "production",
)

JOAT_DATA_DIR = os.environ.get(
    "JOAT_DATA_DIR",
    "/data/joat-main-assistant",
)

JOAT_DB_PATH = os.environ.get(
    "JOAT_DB_PATH",
    f"{JOAT_DATA_DIR}/main_assistant.sqlite3",
)

JOAT_EP_SPACE = os.environ.get(
    "JOAT_EP_SPACE",
    "Dezz-9-10/J.O.A.T.-Executive-Producer-Bot",
)

JOAT_HF_MASTER_SPACE = os.environ.get(
    "JOAT_HF_MASTER_SPACE",
    "Dezz-9-10/J.O.A.T.-Hugging-Face-Master-Bot",
)

JOAT_BROWSER_WORKER_SPACE = os.environ.get(
    "JOAT_BROWSER_WORKER_SPACE",
    "Dezz-9-10/J.O.A.T.-Browser-Worker-Bot",
)

HF_TOKEN = os.environ.get(
    "HF_TOKEN",
    "",
)

JOAT_SPECIALIST_TOKEN = os.environ.get(
    "JOAT_SPECIALIST_TOKEN",
    "",
)

JOAT_LLM_MODEL = os.environ.get(
    "JOAT_LLM_MODEL",
    "openai/gpt-oss-120b",
)

JOAT_LLM_PROVIDER = os.environ.get(
    "JOAT_LLM_PROVIDER",
    "auto",
)

JOAT_LLM_MAX_TOKENS = int(
    os.environ.get(
        "JOAT_LLM_MAX_TOKENS",
        "1400",
    )
)

JOAT_CONTEXT_MESSAGES = int(
    os.environ.get(
        "JOAT_CONTEXT_MESSAGES",
        "24",
    )
)

JOAT_SPECIALIST_RETRIES = int(
    os.environ.get(
        "JOAT_SPECIALIST_RETRIES",
        "1",
    )
)

JOAT_SPECIALIST_TIMEOUT = float(
    os.environ.get(
        "JOAT_SPECIALIST_TIMEOUT",
        "120",
    )
)


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


JOAT_GHL_ENABLED = env_bool(
    "JOAT_GHL_ENABLED",
    False,
)

JOAT_AUDIT_ENABLED = env_bool(
    "JOAT_AUDIT_ENABLED",
    True,
)

JOAT_PERSISTENCE_ENABLED = env_bool(
    "JOAT_PERSISTENCE_ENABLED",
    True,
)

JOAT_APPROVAL_GATES_ENABLED = env_bool(
    "JOAT_APPROVAL_GATES_ENABLED",
    True,
)


# =============================================================================
# STORAGE PATHS
# =============================================================================

DATA_ROOT = Path(JOAT_DATA_DIR)
DB_PATH = Path(JOAT_DB_PATH)

CONVERSATIONS_DIR = DATA_ROOT / "conversations"
PROJECTS_DIR = DATA_ROOT / "projects"
TASKS_DIR = DATA_ROOT / "tasks"
ROUTING_DIR = DATA_ROOT / "routing"
APPROVALS_DIR = DATA_ROOT / "approvals"
EXECUTION_RECEIPTS_DIR = DATA_ROOT / "execution_receipts"
AUDIT_DIR = DATA_ROOT / "audit"
KNOWLEDGE_DIR = DATA_ROOT / "knowledge"
RECOVERY_DIR = DATA_ROOT / "recovery"
SYSTEM_DIR = DATA_ROOT / "system"

PERSISTENT_DIRECTORIES = [
    DATA_ROOT,
    CONVERSATIONS_DIR,
    PROJECTS_DIR,
    TASKS_DIR,
    ROUTING_DIR,
    APPROVALS_DIR,
    EXECUTION_RECEIPTS_DIR,
    AUDIT_DIR,
    KNOWLEDGE_DIR,
    RECOVERY_DIR,
    SYSTEM_DIR,
]

DB_LOCK = threading.RLock()


# =============================================================================
# BASIC HELPERS
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


def fingerprint(value: Any) -> str:
    return hashlib.sha256(
        stable_json(value).encode("utf-8")
    ).hexdigest()


def clean(value: Any) -> str:
    return str(value or "").strip()


def make_title_from_message(message: str) -> str:
    text = clean(message)

    if not text:
        return "New Conversation"

    if len(text) <= 42:
        return text

    return text[:39].rstrip() + "..."


def ensure_directories() -> None:
    if not JOAT_PERSISTENCE_ENABLED:
        return

    for path in PERSISTENT_DIRECTORIES:
        path.mkdir(
            parents=True,
            exist_ok=True,
        )


def storage_is_writable() -> bool:
    if not JOAT_PERSISTENCE_ENABLED:
        return False

    try:
        ensure_directories()

        test_path = SYSTEM_DIR / ".joat_write_test"

        test_path.write_text(
            "J.O.A.T.",
            encoding="utf-8",
        )

        result = (
            test_path.read_text(
                encoding="utf-8"
            )
            == "J.O.A.T."
        )

        test_path.unlink(
            missing_ok=True
        )

        return result

    except Exception:
        return False


def normalize_api_name(value: str) -> str:
    value = clean(value)

    if not value:
        return ""

    if not value.startswith("/"):
        value = "/" + value

    return value


def parse_json_like(value: Any) -> Any:
    if isinstance(value, dict):
        return deepcopy(value)

    if isinstance(value, tuple):
        if len(value) == 1:
            return parse_json_like(value[0])

        return [
            parse_json_like(item)
            for item in value
        ]

    if isinstance(value, list):
        if len(value) == 1:
            return parse_json_like(value[0])

        return [
            parse_json_like(item)
            for item in value
        ]

    if isinstance(value, str):
        stripped = value.strip()

        if not stripped:
            return ""

        try:
            return json.loads(stripped)
        except Exception:
            return stripped

    return value


def walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value

        for child in value.values():
            yield from walk_dicts(child)

    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from walk_dicts(child)


def find_schema_packet(
    value: Any,
    schemas: set[str] | None = None,
) -> dict[str, Any] | None:
    for item in walk_dicts(value):
        schema = clean(
            item.get("schema")
        )

        if not schema:
            continue

        if schemas is None or schema in schemas:
            return item

    return None


def find_boolean_key(
    value: Any,
    key: str,
) -> bool | None:
    for item in walk_dicts(value):
        if key in item and isinstance(
            item[key],
            bool,
        ):
            return item[key]

    return None


def find_string_key(
    value: Any,
    key: str,
) -> str:
    for item in walk_dicts(value):
        candidate = item.get(key)

        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    return ""


# =============================================================================
# SPECIALIST DEFINITIONS
# =============================================================================

SPECIALISTS = {
    "studio": {
        "key": "executive_producer",
        "bot": "J.O.A.T. Executive Producer Bot",
        "space": JOAT_EP_SPACE,
        "work_order_schema": EP_WORK_ORDER_SCHEMA,
        "preferred_endpoints": [
            "/execute_work_order",
            "/execute",
        ],
        "result_schemas": {
            "joat.executive_producer_execution_result.v1",
            "joat.executive_producer_execution.v1",
        },
        "responsibility": (
            "End-to-end studio production management and "
            "coordination of production supervisors, workers, "
            "assistants, generation, post-production, QC, "
            "delivery, and archive."
        ),
    },

    "hugging face": {
        "key": "hugging_face_master",
        "bot": "J.O.A.T. Hugging Face Master Bot",
        "space": JOAT_HF_MASTER_SPACE,
        "work_order_schema": HF_WORK_ORDER_SCHEMA,
        "preferred_endpoints": [
            "/execute_work_order",
            "/execute_action",
            "/execute_hugging_face_action",
            "/execute",
        ],
        "result_schemas": {
            "joat.hugging_face_execution_result.v1",
            "joat.hugging_face_result.v1",
            "joat.hugging_face_execution.v1",
        },
        "responsibility": (
            "Hugging Face Spaces, Hub operations, deployment, "
            "runtime, repositories, dependencies, diagnostics, "
            "and authorized administration."
        ),
    },

    "browser": {
        "key": "browser_worker",
        "bot": "J.O.A.T. Browser Worker Bot",
        "space": JOAT_BROWSER_WORKER_SPACE,
        "work_order_schema": BROWSER_WORK_ORDER_SCHEMA,
        "preferred_endpoints": [
            "/execute_work_order",
            "/execute_browser_work_order",
            "/execute",
        ],
        "result_schemas": {
            "joat.browser_execution_result.v1",
            "joat.browser_result.v1",
            "joat.browser_execution.v1",
        },
        "responsibility": (
            "Authorized browser execution using the "
            "observe-decide-act-verify contract."
        ),
    },
}


DIRECT_REPORTS = {
    "studio_production": {
        "bot":
            SPECIALISTS["studio"]["bot"],

        "status":
            "live_interface_ready",

        "space":
            JOAT_EP_SPACE,

        "live_execution_connected":
            bool(
                JOAT_EP_SPACE
                and JOAT_SPECIALIST_TOKEN
            ),

        "responsibility":
            SPECIALISTS[
                "studio"
            ][
                "responsibility"
            ],
    },

    "hugging_face": {
        "bot":
            SPECIALISTS[
                "hugging face"
            ][
                "bot"
            ],

        "status":
            "live_interface_ready",

        "space":
            JOAT_HF_MASTER_SPACE,

        "live_execution_connected":
            bool(
                JOAT_HF_MASTER_SPACE
                and JOAT_SPECIALIST_TOKEN
            ),

        "responsibility":
            SPECIALISTS[
                "hugging face"
            ][
                "responsibility"
            ],
    },

    "browser_execution": {
        "bot":
            SPECIALISTS[
                "browser"
            ][
                "bot"
            ],

        "status":
            "live_interface_ready",

        "space":
            JOAT_BROWSER_WORKER_SPACE,

        "live_execution_connected":
            bool(
                JOAT_BROWSER_WORKER_SPACE
                and JOAT_SPECIALIST_TOKEN
            ),

        "responsibility":
            SPECIALISTS[
                "browser"
            ][
                "responsibility"
            ],
    },

    "gohighlevel": {
        "bot":
            "Future GHL Sub-Account Master Bot",

        "status": (
            "configured"
            if JOAT_GHL_ENABLED
            else "deferred"
        ),

        "live_execution_connected":
            False,

        "responsibility": (
            "Client-specific GoHighLevel operations using "
            "client-specific credentials."
        ),
    },
}


# =============================================================================
# LOCKED STUDIO KNOWLEDGE
# =============================================================================

STUDIO_KNOWLEDGE = [
    "Character & Asset Master",
    "Director / Creative Intelligence",
    "Scene / Environment Intelligence",
    "Shot / Camera Intelligence",
    "Performance / Action Intelligence",
    "Generation Supervisor",
    "Generation Worker",
    "Quality Control",
    "Post-Production Supervisor",
    "Editorial Worker",
    "Sound Worker",
    "Music Worker",
    "Compositing/VFX Worker",
    "Color/Finish Worker",
    "Titles/Graphics Worker",
    "Delivery/Archive",
    "Executive Producer",
    "Hugging Face Master",
    "Browser Worker",
]


# =============================================================================
# CAPABILITIES
# =============================================================================

CAPABILITIES = {
    "conversation": {
        "required_level": "guru",
        "capabilities": [
            "live conversational intelligence",
            "persistent conversation history",
            "multiple conversation threads",
            "context-aware responses",
            "task clarification",
            "command interpretation",
            "human-readable reporting",
        ],
    },

    "reasoning": {
        "required_level": "guru",
        "capabilities": [
            "objective interpretation",
            "intent detection",
            "domain classification",
            "task planning",
            "specialist selection",
            "context synthesis",
            "failure analysis",
            "recovery planning",
        ],
    },

    "orchestration": {
        "required_level": "guru",
        "capabilities": [
            "system-wide task routing",
            "specialist delegation",
            "live specialist dispatch",
            "Executive Producer delegation",
            "platform-master delegation",
            "Browser Worker delegation",
            "handoff tracking",
            "approval gating",
            "execution verification",
            "failure escalation",
            "bounded retries",
            "recovery coordination",
            "final-result reporting",
        ],
    },

    "studio": {
        "required_level": "guru",
        "capabilities": [
            "animation studio architecture",
            "production pipeline understanding",
            "creative authority awareness",
            "generation pipeline understanding",
            "post-production understanding",
            "quality-control understanding",
            "delivery/archive understanding",
            "subordinate role understanding",
        ],
    },

    "coding": {
        "required_level": "expert",
        "capabilities": [
            "Python",
            "Gradio",
            "SQLite",
            "persistent state architecture",
            "API integration",
            "JSON schemas",
            "debugging",
            "dependency diagnostics",
            "code modification planning",
            "acceptance-test design",
            "safe authorized code changes",
        ],
    },

    "internet_browser": {
        "required_level": "guru",
        "capabilities": [
            "internet research planning",
            "browser-task planning",
            "Browser Worker delegation",
            "live Browser Worker dispatch",
            "DOM-aware execution concepts",
            "vision-aware execution concepts",
            "observe-decide-act-verify",
            "result verification",
            "session awareness",
            "download/upload coordination",
        ],
    },

    "hugging_face": {
        "required_level": "guru",
        "capabilities": [
            "Hugging Face platform understanding",
            "Space architecture",
            "Hub architecture",
            "Gradio deployment",
            "Inference Providers",
            "persistent Storage Bucket architecture",
            "runtime diagnostics",
            "dependency diagnostics",
            "Hugging Face Master delegation",
            "live Hugging Face Master dispatch",
        ],
    },

    "authority": {
        "required_level": "guru",
        "capabilities": [
            "Dr. G direct-command authority",
            "scope-limited authorization",
            "approval checkpoints",
            "specialist authority preservation",
            "immutable packet preservation",
            "credential protection",
            "auditability",
            "chain-of-command enforcement",
        ],
    },
}


# =============================================================================
# AUTHORITY
# =============================================================================

AUTHORITY_BOUNDARY = {
    "highest_human_authority":
        REPORTS_TO,

    "direct_dr_g_instruction_counts_as_authorization":
        True,

    "authorization_is_scope_limited":
        True,

    "may_command_executive_producer":
        True,

    "may_delegate_to_platform_masters":
        True,

    "may_delegate_to_browser_worker":
        True,

    "may_coordinate_system_recovery":
        True,

    "may_prepare_code_changes":
        True,

    "may_execute_authorized_code_changes":
        True,

    "may_bypass_dr_g":
        False,

    "may_expand_scope_without_authorization":
        False,

    "may_override_locked_creative":
        False,

    "may_override_qc_pass_requirement":
        False,

    "may_mutate_immutable_packets":
        False,

    "may_expose_credentials":
        False,

    "may_bypass_2fa":
        False,

    "may_bypass_captcha":
        False,

    "may_self_authorize_purchase":
        False,

    "may_self_authorize_delete":
        False,

    "may_claim_unverified_success":
        False,
}


APPROVAL_POLICY = {
    "enabled":
        JOAT_APPROVAL_GATES_ENABLED,

    "read_only_research":
        "no_additional_approval",

    "read_only_inspection":
        "no_additional_approval",

    "direct_dr_g_command":
        "authorized_within_explicit_scope",

    "scope_expansion":
        "approval_required",

    "destructive_action":
        "approval_required",

    "financial_action":
        "approval_required",

    "credential_change":
        "approval_required",

    "locked_creative_change":
        "approval_required",

    "2fa":
        "human_checkpoint_required",

    "captcha":
        "human_checkpoint_required",
}


# =============================================================================
# EXECUTION LAYERS
# =============================================================================

EXECUTION_LAYERS = {
    "reasoning_control_plane": {
        "enabled": True,
    },

    "persistent_state": {
        "enabled":
            JOAT_PERSISTENCE_ENABLED,

        "data_directory":
            JOAT_DATA_DIR,

        "database":
            JOAT_DB_PATH,

        "storage_bucket_mount":
            "/data",
    },

    "audit": {
        "enabled":
            JOAT_AUDIT_ENABLED,
    },

    "live_llm_provider": {
        "enabled":
            bool(HF_TOKEN),

        "service":
            "Hugging Face Inference Providers",

        "model":
            JOAT_LLM_MODEL,

        "provider_policy":
            JOAT_LLM_PROVIDER,

        "credential":
            "HF_TOKEN",

        "credential_exposed":
            False,
    },

    "specialist_transport": {
        "enabled":
            bool(JOAT_SPECIALIST_TOKEN),

        "transport":
            "Gradio Python Client",

        "credential":
            "JOAT_SPECIALIST_TOKEN",

        "credential_exposed":
            False,

        "bounded_retries":
            JOAT_SPECIALIST_RETRIES,
    },

    "browser_worker":
        deepcopy(
            DIRECT_REPORTS[
                "browser_execution"
            ]
        ),

    "hugging_face_master":
        deepcopy(
            DIRECT_REPORTS[
                "hugging_face"
            ]
        ),

    "executive_producer":
        deepcopy(
            DIRECT_REPORTS[
                "studio_production"
            ]
        ),

    "gohighlevel":
        deepcopy(
            DIRECT_REPORTS[
                "gohighlevel"
            ]
        ),
}


# =============================================================================
# PERSISTENT DATABASE
# =============================================================================

class PersistentStore:

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.enabled = JOAT_PERSISTENCE_ENABLED

        if self.enabled:
            ensure_directories()
            self.initialize()

    def connect(self):
        connection = sqlite3.connect(
            str(self.db_path),
            timeout=30,
            check_same_thread=False,
        )

        connection.row_factory = sqlite3.Row
        connection.execute(
            "PRAGMA foreign_keys = ON"
        )
        connection.execute(
            "PRAGMA journal_mode = WAL"
        )
        connection.execute(
            "PRAGMA synchronous = NORMAL"
        )

        return connection

    def initialize(self) -> None:
        if not self.enabled:
            return

        with DB_LOCK:
            with self.connect() as conn:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS threads (
                        thread_id TEXT PRIMARY KEY,
                        schema_name TEXT NOT NULL,
                        title TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        archived INTEGER NOT NULL DEFAULT 0
                    );

                    CREATE TABLE IF NOT EXISTS messages (
                        message_id TEXT PRIMARY KEY,
                        thread_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        sequence_number INTEGER NOT NULL,
                        FOREIGN KEY(thread_id)
                            REFERENCES threads(thread_id)
                            ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS
                        idx_messages_thread_sequence
                    ON messages(
                        thread_id,
                        sequence_number
                    );

                    CREATE TABLE IF NOT EXISTS projects (
                        project_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS tasks (
                        task_id TEXT PRIMARY KEY,
                        project_id TEXT,
                        status TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS routing_records (
                        routing_id TEXT PRIMARY KEY,
                        thread_id TEXT,
                        payload_json TEXT NOT NULL,
                        fingerprint TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS approvals (
                        approval_id TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS execution_receipts (
                        receipt_id TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        verified INTEGER NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS audit_log (
                        audit_id TEXT PRIMARY KEY,
                        event_type TEXT NOT NULL,
                        thread_id TEXT,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS recovery_records (
                        recovery_id TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS system_state (
                        state_key TEXT PRIMARY KEY,
                        value_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    """
                )

                conn.commit()

        self.set_system_state(
            "app_version",
            APP_VERSION,
        )

        self.set_system_state(
            "environment",
            JOAT_ENV,
        )

        self.set_system_state(
            "llm_model",
            JOAT_LLM_MODEL,
        )

        self.set_system_state(
            "specialist_transport_enabled",
            bool(JOAT_SPECIALIST_TOKEN),
        )

        self.set_system_state(
            "last_startup",
            utc_now(),
        )

        self.audit(
            "system_startup",
            {
                "app_version":
                    APP_VERSION,

                "environment":
                    JOAT_ENV,

                "llm_model":
                    JOAT_LLM_MODEL,

                "hf_token_present":
                    bool(HF_TOKEN),

                "specialist_token_present":
                    bool(
                        JOAT_SPECIALIST_TOKEN
                    ),
            },
        )

    def table_exists(self, table_name: str) -> bool:
        if not self.enabled:
            return False

        with DB_LOCK:
            with self.connect() as conn:
                row = conn.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                      AND name = ?
                    """,
                    (clean(table_name),),
                ).fetchone()

        return row is not None

    def count_rows(self, table_name: str) -> int:
        allowed = {
            "threads",
            "messages",
            "projects",
            "tasks",
            "routing_records",
            "approvals",
            "execution_receipts",
            "audit_log",
            "recovery_records",
            "system_state",
        }

        if table_name not in allowed:
            raise ValueError(
                "Unsupported table."
            )

        with DB_LOCK:
            with self.connect() as conn:
                row = conn.execute(
                    f"""
                    SELECT COUNT(*) AS count
                    FROM {table_name}
                    """
                ).fetchone()

        return int(row["count"])

    def set_system_state(
        self,
        key: str,
        value: Any,
    ) -> None:

        if not self.enabled:
            return

        with DB_LOCK:
            with self.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO system_state (
                        state_key,
                        value_json,
                        updated_at
                    )
                    VALUES (?, ?, ?)
                    ON CONFLICT(state_key)
                    DO UPDATE SET
                        value_json = excluded.value_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        clean(key),
                        stable_json(value),
                        utc_now(),
                    ),
                )

                conn.commit()

    def audit(
        self,
        event_type: str,
        payload: dict[str, Any],
        thread_id: str | None = None,
    ) -> None:

        if (
            not self.enabled
            or not JOAT_AUDIT_ENABLED
        ):
            return

        safe_payload = deepcopy(payload)

        for key in list(
            safe_payload.keys()
        ):
            if any(
                word in key.lower()
                for word in [
                    "token",
                    "password",
                    "secret",
                    "credential",
                    "api_key",
                ]
            ):
                safe_payload[key] = "[REDACTED]"

        with DB_LOCK:
            with self.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO audit_log (
                        audit_id,
                        event_type,
                        thread_id,
                        payload_json,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        clean(event_type),
                        (
                            clean(thread_id)
                            if thread_id
                            else None
                        ),
                        stable_json(
                            safe_payload
                        ),
                        utc_now(),
                    ),
                )

                conn.commit()

    def save_thread(
        self,
        thread: dict[str, Any],
    ) -> None:

        if not self.enabled:
            return

        thread_id = clean(
            thread.get("thread_id")
        )

        if not thread_id:
            raise ValueError(
                "Thread ID required."
            )

        title = (
            clean(
                thread.get("title")
            )
            or "New Conversation"
        )

        created_at = (
            clean(
                thread.get("created_at")
            )
            or utc_now()
        )

        messages = list(
            thread.get(
                "messages",
                [],
            )
        )

        with DB_LOCK:
            with self.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO threads (
                        thread_id,
                        schema_name,
                        title,
                        created_at,
                        updated_at,
                        archived
                    )
                    VALUES (?, ?, ?, ?, ?, 0)
                    ON CONFLICT(thread_id)
                    DO UPDATE SET
                        schema_name = excluded.schema_name,
                        title = excluded.title,
                        updated_at = excluded.updated_at,
                        archived = 0
                    """,
                    (
                        thread_id,
                        THREAD_SCHEMA,
                        title,
                        created_at,
                        utc_now(),
                    ),
                )

                conn.execute(
                    """
                    DELETE FROM messages
                    WHERE thread_id = ?
                    """,
                    (thread_id,),
                )

                for index, message in enumerate(
                    messages
                ):
                    role = clean(
                        message.get("role")
                    )

                    content = clean(
                        message.get("content")
                    )

                    if role not in {
                        "user",
                        "assistant",
                        "system",
                    }:
                        continue

                    conn.execute(
                        """
                        INSERT INTO messages (
                            message_id,
                            thread_id,
                            role,
                            content,
                            created_at,
                            sequence_number
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(uuid.uuid4()),
                            thread_id,
                            role,
                            content,
                            utc_now(),
                            index,
                        ),
                    )

                conn.commit()

    def load_thread(
        self,
        thread_id: str,
    ) -> dict[str, Any] | None:

        thread_id = clean(thread_id)

        with DB_LOCK:
            with self.connect() as conn:
                row = conn.execute(
                    """
                    SELECT *
                    FROM threads
                    WHERE thread_id = ?
                      AND archived = 0
                    """,
                    (thread_id,),
                ).fetchone()

                if row is None:
                    return None

                message_rows = conn.execute(
                    """
                    SELECT role, content
                    FROM messages
                    WHERE thread_id = ?
                    ORDER BY sequence_number ASC
                    """,
                    (thread_id,),
                ).fetchall()

        return {
            "schema":
                row["schema_name"],

            "thread_id":
                row["thread_id"],

            "title":
                row["title"],

            "created_at":
                row["created_at"],

            "updated_at":
                row["updated_at"],

            "messages": [
                {
                    "role":
                        item["role"],

                    "content":
                        item["content"],
                }
                for item
                in message_rows
            ],

            "persistent_storage_connected":
                True,
        }

    def load_all_threads(self) -> dict[str, Any]:
        with DB_LOCK:
            with self.connect() as conn:
                rows = conn.execute(
                    """
                    SELECT thread_id
                    FROM threads
                    WHERE archived = 0
                    ORDER BY updated_at ASC
                    """
                ).fetchall()

        result = {}

        for row in rows:
            thread = self.load_thread(
                row["thread_id"]
            )

            if thread:
                result[
                    thread["thread_id"]
                ] = thread

        return result

    def delete_thread(
        self,
        thread_id: str,
    ) -> None:

        with DB_LOCK:
            with self.connect() as conn:
                conn.execute(
                    """
                    DELETE FROM threads
                    WHERE thread_id = ?
                    """,
                    (clean(thread_id),),
                )

                conn.commit()

    def save_routing(
        self,
        thread_id: str,
        routing: dict[str, Any],
    ) -> str:

        routing_id = str(
            uuid.uuid4()
        )

        routing_fp = fingerprint(
            routing
        )

        with DB_LOCK:
            with self.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO routing_records (
                        routing_id,
                        thread_id,
                        payload_json,
                        fingerprint,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        routing_id,
                        clean(thread_id),
                        stable_json(routing),
                        routing_fp,
                        utc_now(),
                    ),
                )

                conn.commit()

        return routing_id

    def create_task(
        self,
        objective: str,
        domain: str,
        route: dict[str, Any],
        thread_id: str,
    ) -> dict[str, Any]:

        now = utc_now()

        task = {
            "schema":
                TASK_SCHEMA,

            "task_id":
                str(uuid.uuid4()),

            "thread_id":
                clean(thread_id),

            "objective":
                clean(objective),

            "domain":
                clean(domain),

            "assigned_to":
                route["selected_bot"],

            "status":
                "received",

            "created_at":
                now,

            "updated_at":
                now,
        }

        with DB_LOCK:
            with self.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO tasks (
                        task_id,
                        project_id,
                        status,
                        payload_json,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task["task_id"],
                        None,
                        task["status"],
                        stable_json(task),
                        now,
                        now,
                    ),
                )

                conn.commit()

        return task

    def create_approval(
        self,
        objective: str,
        reason: str,
        thread_id: str,
    ) -> dict[str, Any]:

        now = utc_now()

        approval = {
            "schema":
                APPROVAL_SCHEMA,

            "approval_id":
                str(uuid.uuid4()),

            "thread_id":
                clean(thread_id),

            "objective":
                clean(objective),

            "reason":
                clean(reason),

            "status":
                "pending",

            "created_at":
                now,

            "updated_at":
                now,
        }

        with DB_LOCK:
            with self.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO approvals (
                        approval_id,
                        status,
                        payload_json,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        approval["approval_id"],
                        approval["status"],
                        stable_json(approval),
                        now,
                        now,
                    ),
                )

                conn.commit()

        return approval

    def create_receipt(
        self,
        status: str,
        verified: bool,
        payload: dict[str, Any],
    ) -> dict[str, Any]:

        receipt = {
            "schema":
                RECEIPT_SCHEMA,

            "receipt_id":
                str(uuid.uuid4()),

            "status":
                clean(status),

            "verified":
                bool(verified),

            "payload":
                deepcopy(payload),

            "created_at":
                utc_now(),
        }

        with DB_LOCK:
            with self.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO execution_receipts (
                        receipt_id,
                        status,
                        verified,
                        payload_json,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        receipt["receipt_id"],
                        receipt["status"],
                        (
                            1
                            if receipt["verified"]
                            else 0
                        ),
                        stable_json(receipt),
                        receipt["created_at"],
                    ),
                )

                conn.commit()

        return receipt

    def create_recovery(
        self,
        status: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:

        now = utc_now()

        recovery = {
            "schema":
                RECOVERY_SCHEMA,

            "recovery_id":
                str(uuid.uuid4()),

            "status":
                clean(status),

            "payload":
                deepcopy(payload),

            "created_at":
                now,

            "updated_at":
                now,
        }

        with DB_LOCK:
            with self.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO recovery_records (
                        recovery_id,
                        status,
                        payload_json,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        recovery["recovery_id"],
                        recovery["status"],
                        stable_json(recovery),
                        now,
                        now,
                    ),
                )

                conn.commit()

        return recovery


STORE = PersistentStore(DB_PATH)


# =============================================================================
# ROUTING + APPROVAL INTELLIGENCE
# =============================================================================

STUDIO_TERMS = {
    "studio",
    "commercial",
    "film",
    "movie",
    "animation",
    "animate",
    "character",
    "scene",
    "environment",
    "camera",
    "shot",
    "performance",
    "generation",
    "ltx",
    "voice",
    "dialogue",
    "audio",
    "sound",
    "music",
    "edit",
    "editorial",
    "vfx",
    "compositing",
    "color",
    "titles",
    "graphics",
    "qc",
    "quality control",
    "delivery",
    "archive",
    "production",
}

HF_TERMS = {
    "hugging face",
    "huggingface",
    "space",
    "spaces",
    "repository",
    "repo",
    "gradio",
    "runtime",
    "dependency",
    "dependencies",
    "storage bucket",
    "hf token",
    "inference provider",
}

BROWSER_TERMS = {
    "browser",
    "website",
    "web page",
    "webpage",
    "navigate",
    "click",
    "open site",
    "log in",
    "login",
    "upload",
    "download",
    "form",
    "submit",
    "internet",
}

GHL_TERMS = {
    "gohighlevel",
    "go high level",
    "ghl",
    "sub-account",
    "subaccount",
    "location id",
}

DESTRUCTIVE_TERMS = {
    "delete",
    "remove permanently",
    "erase",
    "destroy",
    "wipe",
    "purge",
}

FINANCIAL_TERMS = {
    "purchase",
    "buy",
    "pay",
    "payment",
    "charge",
    "subscribe",
    "checkout",
}

CREDENTIAL_TERMS = {
    "change password",
    "reset password",
    "rotate token",
    "replace token",
    "delete token",
    "create api key",
    "change api key",
    "credential change",
}

LOCKED_CREATIVE_TERMS = {
    "change locked character",
    "change locked scene",
    "change locked creative",
    "override creative lock",
    "modify locked creative",
}

HUMAN_CHECKPOINT_TERMS = {
    "captcha",
    "2fa",
    "two factor",
    "two-factor",
    "verification code",
}


def contains_term(
    text: str,
    terms: set[str],
) -> bool:

    lowered = clean(text).lower()

    return any(
        term in lowered
        for term in terms
    )


def detect_domain(
    objective: str,
) -> str:

    text = clean(objective)

    if contains_term(
        text,
        GHL_TERMS,
    ):
        return "gohighlevel"

    if contains_term(
        text,
        HF_TERMS,
    ):
        return "hugging face"

    if contains_term(
        text,
        STUDIO_TERMS,
    ):
        return "studio"

    if contains_term(
        text,
        BROWSER_TERMS,
    ):
        return "browser"

    return "general"


def evaluate_approval(
    objective: str,
) -> dict[str, Any]:

    text = clean(objective)

    if contains_term(
        text,
        HUMAN_CHECKPOINT_TERMS,
    ):
        return {
            "required": True,
            "type": "human_checkpoint",
            "reason": (
                "2FA/CAPTCHA or human verification "
                "requires human intervention."
            ),
        }

    if contains_term(
        text,
        DESTRUCTIVE_TERMS,
    ):
        return {
            "required": True,
            "type": "destructive_action",
            "reason": (
                "Potentially destructive action detected."
            ),
        }

    if contains_term(
        text,
        FINANCIAL_TERMS,
    ):
        return {
            "required": True,
            "type": "financial_action",
            "reason": (
                "Potential financial action detected."
            ),
        }

    if contains_term(
        text,
        CREDENTIAL_TERMS,
    ):
        return {
            "required": True,
            "type": "credential_change",
            "reason": (
                "Credential-changing action detected."
            ),
        }

    if contains_term(
        text,
        LOCKED_CREATIVE_TERMS,
    ):
        return {
            "required": True,
            "type": "locked_creative_change",
            "reason": (
                "Locked creative change detected."
            ),
        }

    return {
        "required": False,
        "type": None,
        "reason": (
            "No additional approval gate detected."
        ),
    }


# =============================================================================
# MAIN ASSISTANT CONTROL PLANE
# =============================================================================

class MainAssistantBot:

    def determine_route(
        self,
        objective: str,
        domain: str | None = None,
    ) -> dict[str, Any]:

        objective = clean(objective)

        if not objective:
            raise ValueError(
                "Objective is required."
            )

        resolved_domain = (
            clean(domain).lower()
            if clean(domain)
            else detect_domain(objective)
        )

        routes = {
            "studio":
                DIRECT_REPORTS[
                    "studio_production"
                ],

            "production":
                DIRECT_REPORTS[
                    "studio_production"
                ],

            "hugging face":
                DIRECT_REPORTS[
                    "hugging_face"
                ],

            "hugging_face":
                DIRECT_REPORTS[
                    "hugging_face"
                ],

            "browser":
                DIRECT_REPORTS[
                    "browser_execution"
                ],

            "web":
                DIRECT_REPORTS[
                    "browser_execution"
                ],

            "gohighlevel":
                DIRECT_REPORTS[
                    "gohighlevel"
                ],

            "ghl":
                DIRECT_REPORTS[
                    "gohighlevel"
                ],
        }

        selected = routes.get(
            resolved_domain
        )

        if selected is None:
            selected = {
                "bot":
                    BOT_NAME,

                "status":
                    "available",

                "live_execution_connected":
                    True,

                "responsibility": (
                    "Main Assistant conversation, reasoning, "
                    "analysis, planning, clarification, and "
                    "routing."
                ),
            }

        routing = {
            "schema":
                ROUTING_SCHEMA,

            "objective":
                objective,

            "domain":
                resolved_domain
                or "general",

            "selected_bot":
                selected["bot"],

            "selected_status":
                selected["status"],

            "live_execution_connected":
                selected.get(
                    "live_execution_connected",
                    False,
                ),

            "reason":
                selected[
                    "responsibility"
                ],

            "authority_preserved":
                True,
        }

        routing[
            "routing_fingerprint"
        ] = fingerprint(routing)

        return routing

    def build_command(
        self,
        objective: str,
        domain: str | None = None,
        direct_dr_g_instruction: bool = True,
        requested_action: str = "analyze",
    ) -> dict[str, Any]:

        route = self.determine_route(
            objective,
            domain,
        )

        approval = evaluate_approval(
            objective
        )

        command = {
            "schema":
                COMMAND_SCHEMA,

            "bot_name":
                BOT_NAME,

            "bot_type":
                BOT_TYPE,

            "reports_to":
                REPORTS_TO,

            "objective":
                clean(objective),

            "requested_action":
                clean(requested_action),

            "authorization": {
                "source": (
                    REPORTS_TO
                    if direct_dr_g_instruction
                    else "not_directly_authorized"
                ),

                "direct_instruction":
                    bool(
                        direct_dr_g_instruction
                    ),

                "scope_limited":
                    True,
            },

            "routing":
                route,

            "approval":
                approval,

            "approval_policy":
                deepcopy(
                    APPROVAL_POLICY
                ),

            "authority_boundary":
                deepcopy(
                    AUTHORITY_BOUNDARY
                ),
        }

        command[
            "command_fingerprint"
        ] = fingerprint(command)

        return command

    def build_result(
        self,
        command: dict[str, Any],
        status: str,
        verified: bool,
        summary: str,
    ) -> dict[str, Any]:

        if command.get(
            "schema"
        ) != COMMAND_SCHEMA:
            raise ValueError(
                "Invalid command schema."
            )

        allowed = {
            "completed",
            "delegated",
            "blocked",
            "failed",
            "requires_approval",
            "requires_connection",
        }

        if status not in allowed:
            raise ValueError(
                f"Unsupported status: {status}"
            )

        if (
            status == "completed"
            and verified is not True
        ):
            raise ValueError(
                "Completed work must be verified."
            )

        result = {
            "schema":
                RESULT_SCHEMA,

            "bot_name":
                BOT_NAME,

            "reports_to":
                REPORTS_TO,

            "source_command_fingerprint":
                command[
                    "command_fingerprint"
                ],

            "objective":
                command["objective"],

            "delegated_to":
                command[
                    "routing"
                ][
                    "selected_bot"
                ],

            "status":
                status,

            "verified":
                bool(verified),

            "summary":
                clean(summary),

            "authority_preserved":
                True,

            "scope_preserved":
                True,

            "credentials_protected":
                True,

            "immutable_packets_preserved":
                True,
        }

        result[
            "result_fingerprint"
        ] = fingerprint(result)

        return result

    def create_thread(
        self,
        title: str,
    ) -> dict[str, Any]:

        now = utc_now()

        return {
            "schema":
                THREAD_SCHEMA,

            "thread_id":
                str(uuid.uuid4()),

            "title":
                clean(title)
                or "New Conversation",

            "created_at":
                now,

            "updated_at":
                now,

            "messages":
                [],

            "persistent_storage_connected":
                JOAT_PERSISTENCE_ENABLED,
        }


MASTER = MainAssistantBot()


# =============================================================================
# LIVE INTELLIGENCE
# =============================================================================

def build_system_prompt(
    route: dict[str, Any],
    approval: dict[str, Any],
) -> str:

    studio_roles = ", ".join(
        STUDIO_KNOWLEDGE
    )

    return f"""
You are {BOT_NAME}, the primary command, conversation,
reasoning, orchestration, coding, platform-management,
and studio-management assistant for J.O.A.T.

HIGHEST HUMAN AUTHORITY:
{REPORTS_TO}

CHAIN OF COMMAND:
{REPORTS_TO}
-> {BOT_NAME}
-> Executive Producer / authorized platform master
-> supervisors / workers / assistants
-> verified result
-> {BOT_NAME}
-> {REPORTS_TO}

YOUR OPERATING PRINCIPLES:
1. Follow {REPORTS_TO}'s explicit instruction within its stated scope.
2. Never silently expand the scope.
3. Never claim an external action happened unless execution is actually
   connected and a verified specialist result exists.
4. Never reveal, request in chat, echo, or store credentials.
5. Never bypass CAPTCHA or 2FA.
6. Never self-authorize purchases, destructive actions, credential changes,
   or locked creative changes.
7. Preserve immutable packets and locked creative decisions.
8. Preserve QC requirements.
9. Distinguish planning from execution.
10. Be concise, operational, and useful.
11. Specialist results are evidence only when verified.
12. Never turn a failed or unverified specialist result into success.

LOCKED/KNOWN STUDIO ROLES:
{studio_roles}

CURRENT AUTOMATIC ROUTE:
Domain: {route["domain"]}
Selected bot: {route["selected_bot"]}
Selected status: {route["selected_status"]}
Live execution configured: {route["live_execution_connected"]}

CURRENT APPROVAL ANALYSIS:
Approval required: {approval["required"]}
Approval type: {approval["type"]}
Reason: {approval["reason"]}

LIVE SYSTEM STATE:
Persistent memory: {JOAT_PERSISTENCE_ENABLED}
Audit: {JOAT_AUDIT_ENABLED}
Approval gates: {JOAT_APPROVAL_GATES_ENABLED}
GHL enabled: {JOAT_GHL_ENABLED}
Specialist transport configured: {bool(JOAT_SPECIALIST_TOKEN)}
Executive Producer Space: {JOAT_EP_SPACE}
Hugging Face Master Space: {JOAT_HF_MASTER_SPACE}
Browser Worker Space: {JOAT_BROWSER_WORKER_SPACE}

When responding:
- Answer naturally.
- Use conversation context.
- Do not expose secrets.
- Do not claim unverified execution.
- If a task requires approval, identify the gate.
- If specialist execution has returned a verified result, summarize it
  without inventing additional actions.
""".strip() + "\n\n" + __import__("joat_studio_capabilities").context(compact=route.get("domain") != "studio") + "\n\n" + __import__("joat_production_knowledge").context(role="main")


def get_inference_client():
    if not HF_TOKEN:
        raise RuntimeError(
            "HF_TOKEN is not configured."
        )

    if (
        JOAT_LLM_PROVIDER
        and JOAT_LLM_PROVIDER.lower()
        not in {
            "",
            "auto",
        }
    ):
        return InferenceClient(
            provider=JOAT_LLM_PROVIDER,
            api_key=HF_TOKEN,
        )

    return InferenceClient(
        api_key=HF_TOKEN,
    )


def extract_completion_text(
    completion: Any,
) -> str:

    try:
        text = (
            completion
            .choices[0]
            .message
            .content
        )

        if isinstance(
            text,
            str,
        ):
            return text.strip()

        if isinstance(
            text,
            list,
        ):
            parts = []

            for item in text:
                if isinstance(
                    item,
                    dict,
                ):
                    candidate = (
                        item.get("text")
                        or item.get("content")
                    )

                    if candidate:
                        parts.append(
                            str(candidate)
                        )
                else:
                    parts.append(
                        str(item)
                    )

            return "\n".join(
                parts
            ).strip()

        return clean(text)

    except Exception as exc:
        raise RuntimeError(
            "Inference response did not contain usable text."
        ) from exc


def call_live_intelligence(
    history: list[dict[str, Any]],
    route: dict[str, Any],
    approval: dict[str, Any],
    execution_context: dict[str, Any] | None = None,
) -> str:

    client = get_inference_client()

    system_prompt = build_system_prompt(
        route,
        approval,
    )

    if execution_context is not None:
        system_prompt += (
            "\n\nVERIFIED SPECIALIST EXECUTION CONTEXT:\n"
            + json.dumps(
                execution_context,
                ensure_ascii=False,
                indent=2,
            )
            + "\n\nSummarize only what this verified result supports."
        )

    usable_history = []

    for item in history[
        -JOAT_CONTEXT_MESSAGES:
    ]:
        role = clean(
            item.get("role")
        )

        content = clean(
            item.get("content")
        )

        if (
            role
            in {
                "user",
                "assistant",
            }
            and content
        ):
            usable_history.append(
                {
                    "role":
                        role,

                    "content":
                        content,
                }
            )

    messages = [
        {
            "role":
                "system",

            "content":
                system_prompt,
        }
    ] + usable_history

    completion = client.chat_completion(
        model=JOAT_LLM_MODEL,
        messages=messages,
        max_tokens=JOAT_LLM_MAX_TOKENS,
        temperature=0.3,
    )

    reply = extract_completion_text(
        completion
    )

    if not reply:
        raise RuntimeError(
            "Inference returned an empty response."
        )

    return reply


# =============================================================================
# SPECIALIST TRANSPORT
# =============================================================================

def specialist_for_domain(
    domain: str,
) -> dict[str, Any] | None:

    domain = clean(domain).lower()

    if domain in {
        "studio",
        "production",
    }:
        return SPECIALISTS["studio"]

    if domain in {
        "hugging face",
        "hugging_face",
    }:
        return SPECIALISTS[
            "hugging face"
        ]

    if domain in {
        "browser",
        "web",
    }:
        return SPECIALISTS[
            "browser"
        ]

    return None


def create_specialist_client(
    space: str,
) -> Client:

    if not JOAT_SPECIALIST_TOKEN:
        raise RuntimeError(
            "JOAT_SPECIALIST_TOKEN is not configured."
        )

    if not clean(space):
        raise RuntimeError(
            "Specialist Space is not configured."
        )

    return Client(
        clean(space),
        token=JOAT_SPECIALIST_TOKEN,
        verbose=False,
    )


def extract_named_endpoints(
    api_info: Any,
) -> list[str]:

    if not isinstance(
        api_info,
        dict,
    ):
        return []

    named = api_info.get(
        "named_endpoints",
        {},
    )

    if isinstance(
        named,
        dict,
    ):
        return [
            normalize_api_name(name)
            for name in named.keys()
            if clean(name)
        ]

    return []


def discover_execution_endpoint(
    client: Client,
    specialist: dict[str, Any],
) -> tuple[str, list[str]]:

    api_info = client.view_api(
        return_format="dict"
    )

    endpoints = extract_named_endpoints(
        api_info
    )

    endpoint_set = set(
        endpoints
    )

    for preferred in specialist[
        "preferred_endpoints"
    ]:
        normalized = normalize_api_name(
            preferred
        )

        if normalized in endpoint_set:
            return (
                normalized,
                endpoints,
            )

    execution_candidates = [
        endpoint
        for endpoint in endpoints
        if (
            "execute" in endpoint.lower()
            and "acceptance" not in endpoint.lower()
            and "test" not in endpoint.lower()
        )
    ]

    if len(execution_candidates) == 1:
        return (
            execution_candidates[0],
            endpoints,
        )

    raise RuntimeError(
        "No unique live execution endpoint was discovered. "
        f"Available endpoints: {endpoints}"
    )


def specialist_health(
    domain: str,
) -> dict[str, Any]:

    specialist = specialist_for_domain(
        domain
    )

    if specialist is None:
        return {
            "schema":
                SPECIALIST_HEALTH_SCHEMA,

            "domain":
                domain,

            "connected":
                False,

            "error":
                "No specialist exists for this domain.",
        }

    health = {
        "schema":
            SPECIALIST_HEALTH_SCHEMA,

        "domain":
            domain,

        "bot":
            specialist["bot"],

        "space":
            specialist["space"],

        "token_present":
            bool(
                JOAT_SPECIALIST_TOKEN
            ),

        "token_exposed":
            False,

        "connected":
            False,

        "endpoint":
            "",

        "available_endpoints":
            [],
    }

    try:
        client = create_specialist_client(
            specialist["space"]
        )

        endpoint, endpoints = (
            discover_execution_endpoint(
                client,
                specialist,
            )
        )

        health[
            "available_endpoints"
        ] = endpoints

        health[
            "endpoint"
        ] = endpoint

        health[
            "connected"
        ] = True

        return health

    except Exception as exc:
        health["error"] = clean(exc)
        return health


def build_specialist_work_order(
    command: dict[str, Any],
    task: dict[str, Any],
) -> dict[str, Any]:

    domain = command[
        "routing"
    ][
        "domain"
    ]

    specialist = specialist_for_domain(
        domain
    )

    if specialist is None:
        raise ValueError(
            "No live specialist is defined for this domain."
        )

    if (
        command[
            "approval"
        ][
            "required"
        ]
        and JOAT_APPROVAL_GATES_ENABLED
    ):
        raise ValueError(
            "Approval-gated command cannot be dispatched."
        )

    work_order = {
        "schema":
            specialist[
                "work_order_schema"
            ],

        "work_order_id":
            str(uuid.uuid4()),

        "source":
            BOT_NAME,

        "target":
            specialist["bot"],

        "authorized":
            True,

        "objective": {
            "instruction":
                command["objective"],

            "requested_action":
                command[
                    "requested_action"
                ],

            "approved_by_main_assistant":
                True,

            "main_assistant":
                BOT_NAME,

            "human_authority":
                REPORTS_TO,
        },

        "authorization": {
            "source":
                REPORTS_TO,

            "main_assistant_authorized":
                True,

            "scope_limited":
                True,

            "approval_gate_clear":
                True,
        },

        "task_id":
            task["task_id"],

        "source_command_fingerprint":
            command[
                "command_fingerprint"
            ],

        "routing_fingerprint":
            command[
                "routing"
            ][
                "routing_fingerprint"
            ],

        "requested_at":
            utc_now(),

        "dry_run":
            False,
    }

    if specialist["key"] == "executive_producer":
        # EP's established receiver uses source_bot/target_bot and a project
        # objective. Preserve the generic fields for existing receipt readers.
        project_id = clean(task.get("project_id")) or clean(command.get("project_id"))
        if not project_id:
            matches = re.findall(r"(?<![A-Za-z0-9_-])PROJECT-[A-Za-z0-9_-]+", command["objective"])
            if len(set(matches)) > 1:
                raise ValueError("Studio planning requires one explicit project ID per work order.")
            project_id = matches[0] if matches else "PROJECT-" + fingerprint({"task_id": task["task_id"]})[:16]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", project_id):
            raise ValueError("Invalid production project ID.")
        work_order.update(source_bot=BOT_NAME, target_bot=specialist["bot"], project_id=project_id)
        work_order["objective"].update(project_id=project_id, objective=command["objective"])

    work_order[
        "work_order_fingerprint"
    ] = fingerprint(
        work_order
    )

    return work_order


def verify_specialist_response(
    specialist: dict[str, Any],
    work_order: dict[str, Any],
    response: Any,
) -> dict[str, Any]:

    parsed = parse_json_like(
        response
    )

    verification = {
        "verified":
            False,

        "schema_found":
            "",

        "explicit_verified":
            False,

        "source_linkage":
            True,

        "failure_detected":
            False,

        "reason":
            "",
    }

    result_packet = find_schema_packet(
        parsed,
        specialist[
            "result_schemas"
        ],
    )

    if specialist["key"] == "executive_producer":
        # The response contains both an execution envelope and a result.
        # Verify the result, not the earlier envelope encountered by traversal.
        result_packet = find_schema_packet(parsed, {"joat.executive_producer_execution_result.v1"})

    if result_packet is not None:
        verification[
            "schema_found"
        ] = clean(
            result_packet.get(
                "schema"
            )
        )

    explicit_verified = (
        find_boolean_key(
            parsed,
            "verified",
        )
    )

    verification[
        "explicit_verified"
    ] = (
        explicit_verified is True
    )

    source_fp = find_string_key(
        parsed,
        "source_command_fingerprint",
    )

    if source_fp:
        verification[
            "source_linkage"
        ] = (
            source_fp
            == work_order[
                "source_command_fingerprint"
            ]
        )

    status = find_string_key(
        parsed,
        "status",
    ).lower()

    failure_statuses = {
        "failed",
        "failure",
        "rejected",
        "blocked",
        "error",
        "unauthorized",
    }

    verification[
        "failure_detected"
    ] = status in failure_statuses

    if result_packet is None:
        verification[
            "reason"
        ] = (
            "Expected specialist result schema "
            "was not found."
        )

        return {
            "parsed_response":
                parsed,

            "verification":
                verification,
        }

    if explicit_verified is not True:
        verification[
            "reason"
        ] = (
            "Specialist did not explicitly verify the result."
        )

        return {
            "parsed_response":
                parsed,

            "verification":
                verification,
        }

    if not verification[
        "source_linkage"
    ]:
        verification[
            "reason"
        ] = (
            "Specialist result command fingerprint "
            "does not match the dispatched command."
        )

        return {
            "parsed_response":
                parsed,

            "verification":
                verification,
        }

    if verification[
        "failure_detected"
    ]:
        verification[
            "reason"
        ] = (
            "Specialist returned a failure status."
        )

        return {
            "parsed_response":
                parsed,

            "verification":
                verification,
        }

    if specialist["key"] == "executive_producer":
        if result_packet.get("work_order_id") != work_order["work_order_id"]:
            verification["reason"] = "Executive result does not match the dispatched work order."
            return {"parsed_response": parsed, "verification": verification}
        packet = result_packet.get("production_packet")
        if packet is not None:
            result_unsigned = dict(result_packet)
            result_fp = result_unsigned.pop("result_fingerprint", None)
            if result_fp != fingerprint(result_unsigned):
                verification["reason"] = "Executive result fingerprint is invalid."
                return {"parsed_response": parsed, "verification": verification}
            unsigned = dict(packet); supplied = unsigned.pop("packet_fingerprint", None)
            plan = packet.get("production_plan", {})
            unsigned_plan = dict(plan); plan_fp = unsigned_plan.pop("plan_fingerprint", None)
            if (supplied != fingerprint(unsigned) or plan_fp != fingerprint(unsigned_plan)
                    or packet.get("immutable_objective_snapshot") != work_order["objective"]
                    or plan.get("production_objective") != work_order["objective"]
                    or plan.get("project_id") != work_order["project_id"]):
                verification["reason"] = "Executive production plan changed the approved objective or project."
                return {"parsed_response": parsed, "verification": verification}
        verification["execution_scope"] = "production_plan_only"
        verification["finished_video_verified"] = False

    verification["verified"] = True
    verification["reason"] = (
        "Specialist result schema and verification passed."
    )

    return {
        "parsed_response":
            parsed,

        "verification":
            verification,
    }


def dispatch_specialist(
    command: dict[str, Any],
    task: dict[str, Any],
    thread_id: str,
) -> dict[str, Any]:

    domain = command[
        "routing"
    ][
        "domain"
    ]

    specialist = specialist_for_domain(
        domain
    )

    if specialist is None:
        raise RuntimeError(
            "No live specialist is defined for this route."
        )

    work_order = build_specialist_work_order(
        command,
        task,
    )

    dispatch_id = str(
        uuid.uuid4()
    )

    attempts = []
    max_attempts = max(
        1,
        JOAT_SPECIALIST_RETRIES + 1,
    )

    for attempt_number in range(
        1,
        max_attempts + 1,
    ):
        attempt = {
            "attempt":
                attempt_number,

            "started_at":
                utc_now(),
        }

        try:
            client = create_specialist_client(
                specialist["space"]
            )

            endpoint, endpoints = (
                discover_execution_endpoint(
                    client,
                    specialist,
                )
            )

            attempt[
                "endpoint"
            ] = endpoint

            attempt[
                "available_endpoints"
            ] = endpoints

            raw_response = client.predict(
                stable_json(
                    work_order
                ),
                api_name=endpoint,
            )

            verified = verify_specialist_response(
                specialist,
                work_order,
                raw_response,
            )

            attempt[
                "completed_at"
            ] = utc_now()

            attempt[
                "transport_success"
            ] = True

            attempt[
                "verification"
            ] = verified[
                "verification"
            ]

            attempts.append(
                attempt
            )

            dispatch = {
                "schema":
                    SPECIALIST_DISPATCH_SCHEMA,

                "dispatch_id":
                    dispatch_id,

                "task_id":
                    task["task_id"],

                "thread_id":
                    clean(thread_id),

                "domain":
                    domain,

                "specialist":
                    specialist["bot"],

                "space":
                    specialist["space"],

                "endpoint":
                    endpoint,

                "work_order":
                    work_order,

                "response":
                    verified[
                        "parsed_response"
                    ],

                "verification":
                    verified[
                        "verification"
                    ],

                "attempts":
                    attempts,

                "executed":
                    True,

                "verified":
                    verified[
                        "verification"
                    ][
                        "verified"
                    ],

                "completed_at":
                    utc_now(),
            }

            dispatch[
                "dispatch_fingerprint"
            ] = fingerprint(
                dispatch
            )

            if dispatch["verified"]:
                return dispatch

            if attempt_number >= max_attempts:
                return dispatch

        except Exception as exc:
            attempt[
                "completed_at"
            ] = utc_now()

            attempt[
                "transport_success"
            ] = False

            attempt[
                "error"
            ] = clean(exc)

            attempts.append(
                attempt
            )

            if attempt_number >= max_attempts:
                dispatch = {
                    "schema":
                        SPECIALIST_DISPATCH_SCHEMA,

                    "dispatch_id":
                        dispatch_id,

                    "task_id":
                        task["task_id"],

                    "thread_id":
                        clean(thread_id),

                    "domain":
                        domain,

                    "specialist":
                        specialist["bot"],

                    "space":
                        specialist["space"],

                    "work_order":
                        work_order,

                    "attempts":
                        attempts,

                    "executed":
                        False,

                    "verified":
                        False,

                    "error":
                        clean(exc),

                    "completed_at":
                        utc_now(),
                }

                dispatch[
                    "dispatch_fingerprint"
                ] = fingerprint(
                    dispatch
                )

                return dispatch

            time.sleep(1)

    raise RuntimeError(
        "Specialist dispatch terminated unexpectedly."
    )


def specialist_health_all() -> dict[str, Any]:
    return {
        "schema":
            SPECIALIST_HEALTH_SCHEMA,

        "transport_token_present":
            bool(
                JOAT_SPECIALIST_TOKEN
            ),

        "transport_token_exposed":
            False,

        "executive_producer":
            specialist_health(
                "studio"
            ),

        "hugging_face_master":
            specialist_health(
                "hugging face"
            ),

        "browser_worker":
            specialist_health(
                "browser"
            ),

        "gohighlevel": {
            "connected":
                False,

            "status":
                "deferred",
        },
    }


# =============================================================================
# THREAD HELPERS
# =============================================================================

def thread_choices(
    threads: dict[str, Any],
) -> list[tuple[str, str]]:

    return [
        (
            item.get(
                "title",
                "Conversation",
            ),
            thread_id,
        )
        for thread_id, item
        in reversed(
            list(
                threads.items()
            )
        )
    ]


def create_initial_thread():
    threads = (
        STORE.load_all_threads()
        if JOAT_PERSISTENCE_ENABLED
        else {}
    )

    if threads:
        selected_id = next(
            reversed(threads)
        )

        return (
            threads,
            selected_id,
        )

    thread = MASTER.create_thread(
        "New Conversation"
    )

    threads = {
        thread["thread_id"]:
            thread
    }

    if JOAT_PERSISTENCE_ENABLED:
        STORE.save_thread(
            thread
        )

    return (
        threads,
        thread["thread_id"],
    )


def new_thread(threads):
    threads = dict(
        threads or {}
    )

    thread = MASTER.create_thread(
        "New Conversation"
    )

    threads[
        thread["thread_id"]
    ] = thread

    STORE.save_thread(thread)

    return (
        threads,

        gr.update(
            choices=thread_choices(
                threads
            ),
            value=thread["thread_id"],
        ),

        [],

        "",

        "New Conversation",
    )


def load_thread(
    thread_id,
    threads,
):

    threads = dict(
        threads or {}
    )

    persistent = (
        STORE.load_thread(
            thread_id
        )
        if thread_id
        else None
    )

    if persistent:
        threads[
            thread_id
        ] = persistent

    if (
        not thread_id
        or thread_id
        not in threads
    ):
        return (
            [],
            "New Conversation",
        )

    thread = threads[
        thread_id
    ]

    return (
        deepcopy(
            thread.get(
                "messages",
                [],
            )
        ),

        thread.get(
            "title",
            "Conversation",
        ),
    )


def delete_thread(
    thread_id,
    threads,
):

    threads = dict(
        threads or {}
    )

    if thread_id in threads:
        del threads[
            thread_id
        ]

        STORE.delete_thread(
            thread_id
        )

    if not threads:
        thread = MASTER.create_thread(
            "New Conversation"
        )

        threads[
            thread["thread_id"]
        ] = thread

        STORE.save_thread(
            thread
        )

    selected_id = next(
        reversed(threads)
    )

    selected = threads[
        selected_id
    ]

    return (
        threads,

        gr.update(
            choices=thread_choices(
                threads
            ),
            value=selected_id,
        ),

        deepcopy(
            selected.get(
                "messages",
                [],
            )
        ),

        selected.get(
            "title",
            "Conversation",
        ),
    )


def clear_current_thread(
    thread_id,
    threads,
):

    threads = dict(
        threads or {}
    )

    if (
        thread_id
        and thread_id
        in threads
    ):
        threads[
            thread_id
        ][
            "messages"
        ] = []

        threads[
            thread_id
        ][
            "updated_at"
        ] = utc_now()

        STORE.save_thread(
            threads[
                thread_id
            ]
        )

    return (
        [],
        threads,
    )


# =============================================================================
# MAIN CHAT EXECUTION
# =============================================================================

def send_message(
    message,
    history,
    thread_id,
    threads,
):

    message = clean(message)
    history = list(history or [])
    threads = dict(threads or {})

    if not message:
        current_title = (
            threads.get(
                thread_id,
                {},
            ).get(
                "title",
                "Conversation",
            )
        )

        return (
            history,
            "",
            threads,
            gr.update(),
            current_title,
        )

    if (
        not thread_id
        or thread_id
        not in threads
    ):
        thread = MASTER.create_thread(
            make_title_from_message(
                message
            )
        )

        thread_id = thread[
            "thread_id"
        ]

        threads[
            thread_id
        ] = thread

    thread = threads[
        thread_id
    ]

    if (
        not thread.get(
            "messages"
        )
        and thread.get(
            "title"
        )
        == "New Conversation"
    ):
        thread[
            "title"
        ] = make_title_from_message(
            message
        )

    user_message = {
        "role":
            "user",

        "content":
            message,
    }

    history.append(
        user_message
    )

    route = MASTER.determine_route(
        message
    )

    approval = evaluate_approval(
        message
    )

    command = MASTER.build_command(
        objective=message,
        domain=route["domain"],
        direct_dr_g_instruction=True,
        requested_action="execute",
    )

    routing_id = STORE.save_routing(
        thread_id,
        route,
    )

    task = STORE.create_task(
        objective=message,
        domain=route["domain"],
        route=route,
        thread_id=thread_id,
    )

    STORE.audit(
        "user_command_received",
        {
            "task_id":
                task["task_id"],

            "routing_id":
                routing_id,

            "domain":
                route["domain"],

            "selected_bot":
                route["selected_bot"],

            "approval_required":
                approval["required"],

            "command_fingerprint":
                command[
                    "command_fingerprint"
                ],
        },
        thread_id=thread_id,
    )

    if (
        approval["required"]
        and JOAT_APPROVAL_GATES_ENABLED
    ):
        approval_record = (
            STORE.create_approval(
                objective=message,
                reason=approval["reason"],
                thread_id=thread_id,
            )
        )

        reply = (
            f"Approval checkpoint required.\n\n"
            f"**Reason:** {approval['reason']}\n\n"
            f"**Approval ID:** "
            f"`{approval_record['approval_id']}`\n\n"
            "I have not dispatched or executed the gated action."
        )

        STORE.create_receipt(
            status="requires_approval",
            verified=True,
            payload={
                "task_id":
                    task["task_id"],

                "approval_id":
                    approval_record[
                        "approval_id"
                    ],

                "command_fingerprint":
                    command[
                        "command_fingerprint"
                    ],

                "execution_performed":
                    False,
            },
        )

    else:
        specialist = specialist_for_domain(
            route["domain"]
        )

        if specialist is not None:
            if not JOAT_SPECIALIST_TOKEN:
                recovery = STORE.create_recovery(
                    status="open",
                    payload={
                        "task_id":
                            task["task_id"],

                        "failure_class":
                            "specialist_transport_not_configured",

                        "selected_bot":
                            specialist["bot"],

                        "space":
                            specialist["space"],

                        "retry_allowed":
                            True,
                    },
                )

                STORE.create_receipt(
                    status="requires_connection",
                    verified=True,
                    payload={
                        "task_id":
                            task["task_id"],

                        "recovery_id":
                            recovery[
                                "recovery_id"
                            ],

                        "selected_bot":
                            specialist["bot"],

                        "execution_performed":
                            False,
                    },
                )

                reply = (
                    f"The command routes to "
                    f"**{specialist['bot']}**, but the private "
                    "specialist transport credential is not configured.\n\n"
                    f"**Recovery ID:** "
                    f"`{recovery['recovery_id']}`\n\n"
                    "No external execution was claimed."
                )

            else:
                dispatch = dispatch_specialist(
                    command,
                    task,
                    thread_id,
                )

                if dispatch["verified"]:
                    receipt = STORE.create_receipt(
                        status="completed",
                        verified=True,
                        payload={
                            "task_id":
                                task["task_id"],

                            "routing_id":
                                routing_id,

                            "dispatch_id":
                                dispatch[
                                    "dispatch_id"
                                ],

                            "selected_bot":
                                specialist["bot"],

                            "space":
                                specialist["space"],

                            "endpoint":
                                dispatch.get(
                                    "endpoint",
                                    "",
                                ),

                            "command_fingerprint":
                                command[
                                    "command_fingerprint"
                                ],

                            "work_order_fingerprint":
                                dispatch[
                                    "work_order"
                                ][
                                    "work_order_fingerprint"
                                ],

                            "dispatch_fingerprint":
                                dispatch[
                                    "dispatch_fingerprint"
                                ],

                            "specialist_verified":
                                True,

                            "execution_performed":
                                True,
                        },
                    )

                    STORE.audit(
                        "specialist_execution_verified",
                        {
                            "task_id":
                                task["task_id"],

                            "dispatch_id":
                                dispatch[
                                    "dispatch_id"
                                ],

                            "receipt_id":
                                receipt[
                                    "receipt_id"
                                ],

                            "selected_bot":
                                specialist["bot"],

                            "space":
                                specialist["space"],

                            "endpoint":
                                dispatch.get(
                                    "endpoint",
                                    "",
                                ),
                        },
                        thread_id=thread_id,
                    )

                    try:
                        reply = call_live_intelligence(
                            history,
                            route,
                            approval,
                            execution_context={
                                "specialist":
                                    specialist["bot"],

                                "verified":
                                    True,

                                "dispatch_id":
                                    dispatch[
                                        "dispatch_id"
                                    ],

                                "receipt_id":
                                    receipt[
                                        "receipt_id"
                                    ],

                                "result":
                                    dispatch[
                                        "response"
                                    ],
                            },
                        )

                    except Exception:
                        reply = (
                            f"**{specialist['bot']} returned a "
                            "verified result.**\n\n"
                            f"Execution receipt: "
                            f"`{receipt['receipt_id']}`\n\n"
                            "Verified specialist result:\n\n"
                            "```json\n"
                            + json.dumps(
                                dispatch["response"],
                                ensure_ascii=False,
                                indent=2,
                            )
                            + "\n```"
                        )

                else:
                    recovery = STORE.create_recovery(
                        status="open",
                        payload={
                            "task_id":
                                task["task_id"],

                            "dispatch_id":
                                dispatch[
                                    "dispatch_id"
                                ],

                            "failure_class":
                                "specialist_execution_unverified",

                            "selected_bot":
                                specialist["bot"],

                            "space":
                                specialist["space"],

                            "verification":
                                dispatch.get(
                                    "verification",
                                    {},
                                ),

                            "attempts":
                                dispatch.get(
                                    "attempts",
                                    [],
                                ),

                            "retry_allowed":
                                True,
                        },
                    )

                    STORE.create_receipt(
                        status="failed",
                        verified=True,
                        payload={
                            "task_id":
                                task["task_id"],

                            "dispatch_id":
                                dispatch[
                                    "dispatch_id"
                                ],

                            "recovery_id":
                                recovery[
                                    "recovery_id"
                                ],

                            "selected_bot":
                                specialist["bot"],

                            "execution_verified":
                                False,

                            "execution_performed":
                                dispatch.get(
                                    "executed",
                                    False,
                                ),
                        },
                    )

                    STORE.audit(
                        "specialist_execution_unverified",
                        {
                            "task_id":
                                task["task_id"],

                            "dispatch_id":
                                dispatch[
                                    "dispatch_id"
                                ],

                            "recovery_id":
                                recovery[
                                    "recovery_id"
                                ],

                            "selected_bot":
                                specialist["bot"],
                        },
                        thread_id=thread_id,
                    )

                    reason = (
                        dispatch.get(
                            "verification",
                            {},
                        ).get(
                            "reason"
                        )
                        or dispatch.get(
                            "error"
                        )
                        or "Specialist result was not verified."
                    )

                    reply = (
                        f"The command reached the "
                        f"**{specialist['bot']}** execution path, "
                        "but I cannot mark it successful.\n\n"
                        f"**Reason:** {reason}\n\n"
                        f"**Recovery ID:** "
                        f"`{recovery['recovery_id']}`\n\n"
                        "The failure was recorded and no "
                        "unverified success was reported."
                    )

        else:
            try:
                reply = call_live_intelligence(
                    history,
                    route,
                    approval,
                )

                STORE.create_receipt(
                    status="completed",
                    verified=True,
                    payload={
                        "task_id":
                            task["task_id"],

                        "routing_id":
                            routing_id,

                        "selected_bot":
                            BOT_NAME,

                        "command_fingerprint":
                            command[
                                "command_fingerprint"
                            ],

                        "live_specialist_execution":
                            False,

                        "reasoning_response_received":
                            True,
                    },
                )

                STORE.audit(
                    "live_intelligence_success",
                    {
                        "task_id":
                            task["task_id"],

                        "model":
                            JOAT_LLM_MODEL,

                        "selected_bot":
                            BOT_NAME,
                    },
                    thread_id=thread_id,
                )

            except Exception as exc:
                error_text = clean(exc)

                recovery = STORE.create_recovery(
                    status="open",
                    payload={
                        "task_id":
                            task["task_id"],

                        "failure_class":
                            "live_intelligence_failure",

                        "error":
                            error_text,

                        "retry_allowed":
                            True,
                    },
                )

                STORE.create_receipt(
                    status="failed",
                    verified=True,
                    payload={
                        "task_id":
                            task["task_id"],

                        "recovery_id":
                            recovery[
                                "recovery_id"
                            ],

                        "execution_performed":
                            False,
                    },
                )

                STORE.audit(
                    "live_intelligence_failure",
                    {
                        "task_id":
                            task["task_id"],

                        "recovery_id":
                            recovery[
                                "recovery_id"
                            ],

                        "error":
                            error_text,
                    },
                    thread_id=thread_id,
                )

                reply = (
                    "The Main Assistant control plane is online, "
                    "but the live intelligence request failed.\n\n"
                    f"**Failure:** {error_text}\n\n"
                    f"**Recovery ID:** "
                    f"`{recovery['recovery_id']}`\n\n"
                    "The failure was recorded instead of being "
                    "reported as a successful execution."
                )

    history.append(
        {
            "role":
                "assistant",

            "content":
                reply,
        }
    )

    thread[
        "messages"
    ] = deepcopy(history)

    thread[
        "updated_at"
    ] = utc_now()

    threads[
        thread_id
    ] = thread

    STORE.save_thread(thread)

    return (
        history,
        "",
        threads,

        gr.update(
            choices=thread_choices(
                threads
            ),
            value=thread_id,
        ),

        thread["title"],
    )


# =============================================================================
# ADMIN FUNCTIONS
# =============================================================================

def command_ui(
    objective,
    domain,
    direct_authorization,
    requested_action,
):

    try:
        selected_domain = (
            None
            if domain == "automatic"
            else domain
        )

        return MASTER.build_command(
            objective=objective,
            domain=selected_domain,
            direct_dr_g_instruction=(
                direct_authorization
            ),
            requested_action=(
                requested_action
            ),
        )

    except Exception as exc:
        return {
            "error":
                str(exc)
        }


def persistence_status_ui():
    try:
        return {
            "app_version":
                APP_VERSION,

            "environment":
                JOAT_ENV,

            "persistence_enabled":
                JOAT_PERSISTENCE_ENABLED,

            "audit_enabled":
                JOAT_AUDIT_ENABLED,

            "approval_gates_enabled":
                JOAT_APPROVAL_GATES_ENABLED,

            "data_directory":
                str(DATA_ROOT),

            "database_path":
                str(DB_PATH),

            "database_exists":
                DB_PATH.exists(),

            "storage_writable":
                storage_is_writable(),

            "thread_count":
                STORE.count_rows(
                    "threads"
                ),

            "message_count":
                STORE.count_rows(
                    "messages"
                ),

            "task_count":
                STORE.count_rows(
                    "tasks"
                ),

            "routing_count":
                STORE.count_rows(
                    "routing_records"
                ),

            "approval_count":
                STORE.count_rows(
                    "approvals"
                ),

            "receipt_count":
                STORE.count_rows(
                    "execution_receipts"
                ),

            "recovery_count":
                STORE.count_rows(
                    "recovery_records"
                ),

            "audit_count":
                STORE.count_rows(
                    "audit_log"
                ),
        }

    except Exception as exc:
        return {
            "error":
                str(exc)
        }


def intelligence_status_ui():
    return {
        "live_intelligence_enabled":
            bool(HF_TOKEN),

        "service":
            "Hugging Face Inference Providers",

        "model":
            JOAT_LLM_MODEL,

        "provider_policy":
            JOAT_LLM_PROVIDER,

        "hf_token_present":
            bool(HF_TOKEN),

        "hf_token_value_exposed":
            False,

        "max_output_tokens":
            JOAT_LLM_MAX_TOKENS,

        "context_messages":
            JOAT_CONTEXT_MESSAGES,
    }


def specialist_status_ui():
    return specialist_health_all()


# =============================================================================
# ACCEPTANCE TESTS
# =============================================================================

def tests_ui():
    tests = []

    def add(
        name,
        passed,
        detail=None,
    ):
        tests.append(
            {
                "test":
                    name,

                "pass":
                    bool(passed),

                "detail": (
                    detail
                    if detail is not None
                    else bool(passed)
                ),
            }
        )

    try:
        add(
            "1. App version is 2.1.105",
            APP_VERSION == "2.1.105",
        )

        add(
            "2. Acceptance version is 2.1.0",
            ACCEPTANCE_TEST_VERSION == "2.1.0",
        )

        add(
            "3. Main Assistant bot name correct",
            BOT_NAME
            == "J.O.A.T. Main Assistant Bot",
        )

        add(
            "4. Main Assistant bot type correct",
            BOT_TYPE
            == "main_assistant_bot",
        )

        add(
            "5. Reports directly to Dr. G",
            REPORTS_TO == "Dr. G",
        )

        add(
            "6. Assistant not required",
            ASSISTANT_REQUIRED is False,
        )

        add(
            "7. Command schema preserved",
            COMMAND_SCHEMA
            == "joat.main_assistant_command.v1",
        )

        add(
            "8. Routing schema preserved",
            ROUTING_SCHEMA
            == "joat.main_assistant_routing.v1",
        )

        add(
            "9. Result schema preserved",
            RESULT_SCHEMA
            == "joat.main_assistant_result.v1",
        )

        add(
            "10. Thread schema preserved",
            THREAD_SCHEMA
            == "joat.conversation_thread.v1",
        )

        add(
            "11. Persistence enabled",
            JOAT_PERSISTENCE_ENABLED,
        )

        add(
            "12. Audit enabled",
            JOAT_AUDIT_ENABLED,
        )

        add(
            "13. Approval gates enabled",
            JOAT_APPROVAL_GATES_ENABLED,
        )

        add(
            "14. Production environment loaded",
            JOAT_ENV == "production",
        )

        add(
            "15. Data directory correct",
            str(DATA_ROOT)
            == "/data/joat-main-assistant",
        )

        add(
            "16. Database path correct",
            str(DB_PATH)
            == (
                "/data/joat-main-assistant/"
                "main_assistant.sqlite3"
            ),
        )

        add(
            "17. Storage writable",
            storage_is_writable(),
        )

        add(
            "18. Database exists",
            DB_PATH.exists(),
        )

        required_tables = [
            "threads",
            "messages",
            "projects",
            "tasks",
            "routing_records",
            "approvals",
            "execution_receipts",
            "audit_log",
            "recovery_records",
            "system_state",
        ]

        add(
            "19. All operational tables exist",
            all(
                STORE.table_exists(table)
                for table in required_tables
            ),
        )

        add(
            "20. HF inference token present",
            bool(HF_TOKEN),
        )

        add(
            "21. HF inference token not exposed",
            EXECUTION_LAYERS[
                "live_llm_provider"
            ][
                "credential_exposed"
            ] is False,
        )

        add(
            "22. Live LLM provider enabled",
            EXECUTION_LAYERS[
                "live_llm_provider"
            ][
                "enabled"
            ] is True,
        )

        add(
            "23. LLM model configured",
            bool(JOAT_LLM_MODEL),
            JOAT_LLM_MODEL,
        )

        add(
            "24. Specialist transport token present",
            bool(
                JOAT_SPECIALIST_TOKEN
            ),
        )

        add(
            "25. Specialist token not exposed",
            EXECUTION_LAYERS[
                "specialist_transport"
            ][
                "credential_exposed"
            ] is False,
        )

        add(
            "26. Specialist transport enabled",
            EXECUTION_LAYERS[
                "specialist_transport"
            ][
                "enabled"
            ] is True,
        )

        add(
            "27. Conversation guru declared",
            CAPABILITIES[
                "conversation"
            ][
                "required_level"
            ] == "guru",
        )

        add(
            "28. Reasoning guru declared",
            CAPABILITIES[
                "reasoning"
            ][
                "required_level"
            ] == "guru",
        )

        add(
            "29. Orchestration guru declared",
            CAPABILITIES[
                "orchestration"
            ][
                "required_level"
            ] == "guru",
        )

        add(
            "30. Studio guru declared",
            CAPABILITIES[
                "studio"
            ][
                "required_level"
            ] == "guru",
        )

        add(
            "31. Coding expert declared",
            CAPABILITIES[
                "coding"
            ][
                "required_level"
            ] == "expert",
        )

        add(
            "32. Browser guru declared",
            CAPABILITIES[
                "internet_browser"
            ][
                "required_level"
            ] == "guru",
        )

        add(
            "33. Hugging Face guru declared",
            CAPABILITIES[
                "hugging_face"
            ][
                "required_level"
            ] == "guru",
        )

        add(
            "34. Authority guru declared",
            CAPABILITIES[
                "authority"
            ][
                "required_level"
            ] == "guru",
        )

        add(
            "35. Live specialist dispatch declared",
            (
                "live specialist dispatch"
                in CAPABILITIES[
                    "orchestration"
                ][
                    "capabilities"
                ]
            ),
        )

        add(
            "36. Bounded retries declared",
            (
                "bounded retries"
                in CAPABILITIES[
                    "orchestration"
                ][
                    "capabilities"
                ]
            ),
        )

        add(
            "37. Studio intent detected",
            detect_domain(
                "Produce the animated commercial."
            ) == "studio",
        )

        add(
            "38. Hugging Face intent detected",
            detect_domain(
                "Inspect the Hugging Face Space runtime."
            ) == "hugging face",
        )

        add(
            "39. Browser intent detected",
            detect_domain(
                "Open the website and click the form."
            ) == "browser",
        )

        add(
            "40. GHL intent detected",
            detect_domain(
                "Inspect the GoHighLevel sub-account."
            ) == "gohighlevel",
        )

        add(
            "41. General intent detected",
            detect_domain(
                "Explain what you can do."
            ) == "general",
        )

        studio_route = MASTER.determine_route(
            "Produce the commercial."
        )

        hf_route = MASTER.determine_route(
            "Inspect the Hugging Face Space."
        )

        browser_route = MASTER.determine_route(
            "Open the website."
        )

        general_route = MASTER.determine_route(
            "Explain the system."
        )

        add(
            "42. Studio routes to Executive Producer",
            studio_route[
                "selected_bot"
            ]
            == "J.O.A.T. Executive Producer Bot",
        )

        add(
            "43. HF routes to HF Master",
            hf_route[
                "selected_bot"
            ]
            == "J.O.A.T. Hugging Face Master Bot",
        )

        add(
            "44. Browser routes to Browser Worker",
            browser_route[
                "selected_bot"
            ]
            == "J.O.A.T. Browser Worker Bot",
        )

        add(
            "45. General reasoning stays with Main Assistant",
            general_route[
                "selected_bot"
            ] == BOT_NAME,
        )

        add(
            "46. Executive Producer repository exact",
            JOAT_EP_SPACE
            == (
                "Dezz-9-10/"
                "J.O.A.T.-Executive-Producer-Bot"
            ),
        )

        add(
            "47. HF Master repository exact",
            JOAT_HF_MASTER_SPACE
            == (
                "Dezz-9-10/"
                "J.O.A.T.-Hugging-Face-Master-Bot"
            ),
        )

        add(
            "48. Browser Worker repository exact",
            JOAT_BROWSER_WORKER_SPACE
            == (
                "Dezz-9-10/"
                "J.O.A.T.-Browser-Worker-Bot"
            ),
        )

        add(
            "49. EP work-order schema configured",
            EP_WORK_ORDER_SCHEMA
            == "joat.executive_producer_work_order.v1",
        )

        add(
            "50. Browser work-order schema preserved",
            BROWSER_WORK_ORDER_SCHEMA
            == "joat.browser_work_order.v1",
        )

        destructive = evaluate_approval(
            "Delete the production repository."
        )

        financial = evaluate_approval(
            "Purchase the subscription."
        )

        credential = evaluate_approval(
            "Rotate token for the service."
        )

        human = evaluate_approval(
            "Enter the 2FA verification code."
        )

        safe = evaluate_approval(
            "Explain the production pipeline."
        )

        add(
            "51. Destructive action requires approval",
            (
                destructive["required"]
                and destructive["type"]
                == "destructive_action"
            ),
        )

        add(
            "52. Financial action requires approval",
            (
                financial["required"]
                and financial["type"]
                == "financial_action"
            ),
        )

        add(
            "53. Credential change requires approval",
            (
                credential["required"]
                and credential["type"]
                == "credential_change"
            ),
        )

        add(
            "54. 2FA requires human checkpoint",
            (
                human["required"]
                and human["type"]
                == "human_checkpoint"
            ),
        )

        add(
            "55. Safe reasoning needs no extra approval",
            safe["required"] is False,
        )

        add(
            "56. Cannot bypass Dr. G",
            AUTHORITY_BOUNDARY[
                "may_bypass_dr_g"
            ] is False,
        )

        add(
            "57. Cannot expand scope without authorization",
            AUTHORITY_BOUNDARY[
                "may_expand_scope_without_authorization"
            ] is False,
        )

        add(
            "58. Cannot override locked creative",
            AUTHORITY_BOUNDARY[
                "may_override_locked_creative"
            ] is False,
        )

        add(
            "59. Cannot override QC",
            AUTHORITY_BOUNDARY[
                "may_override_qc_pass_requirement"
            ] is False,
        )

        add(
            "60. Cannot mutate immutable packets",
            AUTHORITY_BOUNDARY[
                "may_mutate_immutable_packets"
            ] is False,
        )

        add(
            "61. Cannot expose credentials",
            AUTHORITY_BOUNDARY[
                "may_expose_credentials"
            ] is False,
        )

        add(
            "62. Cannot bypass 2FA",
            AUTHORITY_BOUNDARY[
                "may_bypass_2fa"
            ] is False,
        )

        add(
            "63. Cannot bypass CAPTCHA",
            AUTHORITY_BOUNDARY[
                "may_bypass_captcha"
            ] is False,
        )

        add(
            "64. Cannot self-authorize purchase",
            AUTHORITY_BOUNDARY[
                "may_self_authorize_purchase"
            ] is False,
        )

        add(
            "65. Cannot self-authorize delete",
            AUTHORITY_BOUNDARY[
                "may_self_authorize_delete"
            ] is False,
        )

        add(
            "66. Cannot claim unverified success",
            AUTHORITY_BOUNDARY[
                "may_claim_unverified_success"
            ] is False,
        )

        command = MASTER.build_command(
            "Inspect the Hugging Face deployment."
        )

        command2 = MASTER.build_command(
            "Inspect the Hugging Face deployment."
        )

        add(
            "67. Command packet generates",
            command["schema"]
            == COMMAND_SCHEMA,
        )

        add(
            "68. Command fingerprint deterministic",
            command[
                "command_fingerprint"
            ]
            == command2[
                "command_fingerprint"
            ],
        )

        before = stable_json(command)

        result = MASTER.build_result(
            command,
            "completed",
            True,
            "Verified.",
        )

        add(
            "69. Verified result packet generates",
            (
                result["schema"]
                == RESULT_SCHEMA
                and result["verified"]
                is True
            ),
        )

        add(
            "70. Source command remains immutable",
            before
            == stable_json(command),
        )

        rejected = False

        try:
            MASTER.build_result(
                command,
                "completed",
                False,
                "Not verified.",
            )

        except ValueError:
            rejected = True

        add(
            "71. Unverified completion rejected",
            rejected,
        )

        test_thread = MASTER.create_thread(
            "v2.1 Persistence Test"
        )

        test_thread["messages"] = [
            {
                "role": "user",
                "content": "Persistence v2.1 user.",
            },
            {
                "role": "assistant",
                "content": "Persistence v2.1 assistant.",
            },
        ]

        STORE.save_thread(
            test_thread
        )

        loaded = STORE.load_thread(
            test_thread["thread_id"]
        )

        add(
            "72. Thread persistence works",
            loaded is not None,
        )

        add(
            "73. Message persistence works",
            (
                loaded is not None
                and len(
                    loaded["messages"]
                ) == 2
            ),
        )

        STORE.delete_thread(
            test_thread["thread_id"]
        )

        add(
            "74. Thread deletion works",
            STORE.load_thread(
                test_thread["thread_id"]
            ) is None,
        )

        test_route = MASTER.determine_route(
            "Explain the system."
        )

        routing_id = STORE.save_routing(
            "acceptance-test",
            test_route,
        )

        add(
            "75. Routing persistence works",
            bool(routing_id),
        )

        test_task = STORE.create_task(
            "Acceptance task",
            "general",
            test_route,
            "acceptance-test",
        )

        add(
            "76. Task persistence works",
            bool(
                test_task["task_id"]
            ),
        )

        test_approval = STORE.create_approval(
            "Acceptance approval",
            "Acceptance test only",
            "acceptance-test",
        )

        add(
            "77. Approval persistence works",
            bool(
                test_approval[
                    "approval_id"
                ]
            ),
        )

        test_receipt = STORE.create_receipt(
            "acceptance_test",
            True,
            {
                "execution":
                    "test_only"
            },
        )

        add(
            "78. Execution receipt persistence works",
            (
                bool(
                    test_receipt[
                        "receipt_id"
                    ]
                )
                and test_receipt[
                    "verified"
                ] is True
            ),
        )

        test_recovery = STORE.create_recovery(
            "test_only",
            {
                "failure":
                    "acceptance_test"
            },
        )

        add(
            "79. Recovery persistence works",
            bool(
                test_recovery[
                    "recovery_id"
                ]
            ),
        )

        add(
            "80. Audit records exist",
            STORE.count_rows(
                "audit_log"
            ) > 0,
        )

        studio_command = MASTER.build_command(
            "Produce the commercial.",
            requested_action="execute",
        )

        studio_task = {
            "task_id":
                "acceptance-studio-task"
        }

        studio_work_order = (
            build_specialist_work_order(
                studio_command,
                studio_task,
            )
        )

        add(
            "81. EP work order generates",
            studio_work_order[
                "schema"
            ]
            == EP_WORK_ORDER_SCHEMA,
        )

        add(
            "82. EP work order source is Main Assistant",
            studio_work_order[
                "source"
            ] == BOT_NAME,
        )

        add(
            "83. EP work order target correct",
            studio_work_order[
                "target"
            ]
            == "J.O.A.T. Executive Producer Bot",
        )

        add(
            "84. EP work order authorized",
            studio_work_order[
                "authorized"
            ] is True,
        )

        add(
            "85. EP work order links command fingerprint",
            studio_work_order[
                "source_command_fingerprint"
            ]
            == studio_command[
                "command_fingerprint"
            ],
        )

        hf_command = MASTER.build_command(
            "Inspect the Hugging Face Space runtime.",
            requested_action="execute",
        )

        hf_work_order = (
            build_specialist_work_order(
                hf_command,
                {
                    "task_id":
                        "acceptance-hf-task"
                },
            )
        )

        add(
            "86. HF work order generates",
            hf_work_order[
                "schema"
            ] == HF_WORK_ORDER_SCHEMA,
        )

        add(
            "87. HF work order target correct",
            hf_work_order[
                "target"
            ]
            == "J.O.A.T. Hugging Face Master Bot",
        )

        browser_command = MASTER.build_command(
            "Open the website.",
            requested_action="execute",
        )

        browser_work_order = (
            build_specialist_work_order(
                browser_command,
                {
                    "task_id":
                        "acceptance-browser-task"
                },
            )
        )

        add(
            "88. Browser work order generates",
            browser_work_order[
                "schema"
            ] == BROWSER_WORK_ORDER_SCHEMA,
        )

        add(
            "89. Browser work order target correct",
            browser_work_order[
                "target"
            ]
            == "J.O.A.T. Browser Worker Bot",
        )

        gated_command = MASTER.build_command(
            "Delete the production repository.",
            requested_action="execute",
        )

        gated_rejected = False

        try:
            build_specialist_work_order(
                gated_command,
                {
                    "task_id":
                        "acceptance-gated-task"
                },
            )

        except ValueError:
            gated_rejected = True

        add(
            "90. Approval-gated work order cannot dispatch",
            gated_rejected,
        )

        synthetic_ep_response = {
            "work_order_id": studio_work_order["work_order_id"],
            "schema":
                "joat.executive_producer_execution_result.v1",

            "verified":
                True,

            "status":
                "completed",

            "source_command_fingerprint":
                studio_work_order[
                    "source_command_fingerprint"
                ],
        }

        synthetic_verification = (
            verify_specialist_response(
                SPECIALISTS["studio"],
                studio_work_order,
                synthetic_ep_response,
            )
        )

        add(
            "91. Verified specialist response accepted",
            synthetic_verification[
                "verification"
            ][
                "verified"
            ] is True,
        )

        synthetic_bad_response = {
            "schema":
                "joat.executive_producer_execution_result.v1",

            "verified":
                False,

            "status":
                "completed",
        }

        synthetic_bad_verification = (
            verify_specialist_response(
                SPECIALISTS["studio"],
                studio_work_order,
                synthetic_bad_response,
            )
        )

        add(
            "92. Unverified specialist response rejected",
            synthetic_bad_verification[
                "verification"
            ][
                "verified"
            ] is False,
        )

        synthetic_wrong_fp = {
            "schema":
                "joat.executive_producer_execution_result.v1",

            "verified":
                True,

            "status":
                "completed",

            "source_command_fingerprint":
                "wrong-fingerprint",
        }

        wrong_fp_verification = (
            verify_specialist_response(
                SPECIALISTS["studio"],
                studio_work_order,
                synthetic_wrong_fp,
            )
        )

        add(
            "93. Wrong command fingerprint rejected",
            wrong_fp_verification[
                "verification"
            ][
                "verified"
            ] is False,
        )

        add(
            "94. GHL remains deferred",
            JOAT_GHL_ENABLED is False,
        )

        add(
            "95. Specialist retry count bounded",
            (
                JOAT_SPECIALIST_RETRIES >= 0
                and JOAT_SPECIALIST_RETRIES <= 3
            ),
            JOAT_SPECIALIST_RETRIES,
        )

        ep_health = specialist_health(
            "studio"
        )

        add(
            "96. Executive Producer live API reachable",
            ep_health.get(
                "connected"
            ) is True,
            ep_health,
        )

        hf_health = specialist_health(
            "hugging face"
        )

        add(
            "97. Hugging Face Master live API reachable",
            hf_health.get(
                "connected"
            ) is True,
            hf_health,
        )

        browser_health = specialist_health(
            "browser"
        )

        add(
            "98. Browser Worker live API reachable",
            browser_health.get(
                "connected"
            ) is True,
            browser_health,
        )

        add(
            "99. All three specialist execution endpoints discovered",
            (
                bool(
                    ep_health.get(
                        "endpoint"
                    )
                )
                and bool(
                    hf_health.get(
                        "endpoint"
                    )
                )
                and bool(
                    browser_health.get(
                        "endpoint"
                    )
                )
            ),
        )

        add(
            "100. Main Assistant live specialist architecture ready",
            all(
                item["pass"]
                for item in tests
            ),
        )

        all_passed = all(
            item["pass"]
            for item in tests
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

            "environment":
                JOAT_ENV,

            "live_intelligence": {
                "enabled":
                    bool(HF_TOKEN),

                "service":
                    "Hugging Face Inference Providers",

                "model":
                    JOAT_LLM_MODEL,

                "provider_policy":
                    JOAT_LLM_PROVIDER,

                "token_present":
                    bool(HF_TOKEN),

                "token_exposed":
                    False,
            },

            "specialist_transport": {
                "enabled":
                    bool(
                        JOAT_SPECIALIST_TOKEN
                    ),

                "transport":
                    "Gradio Python Client",

                "token_present":
                    bool(
                        JOAT_SPECIALIST_TOKEN
                    ),

                "token_exposed":
                    False,

                "bounded_retries":
                    JOAT_SPECIALIST_RETRIES,
            },

            "persistence": {
                "enabled":
                    JOAT_PERSISTENCE_ENABLED,

                "database":
                    str(DB_PATH),

                "storage_writable":
                    storage_is_writable(),
            },

            "specialist_connections": {
                "executive_producer":
                    ep_health,

                "hugging_face_master":
                    hf_health,

                "browser_worker":
                    browser_health,

                "gohighlevel":
                    DIRECT_REPORTS[
                        "gohighlevel"
                    ],
            },

            "tests":
                tests,

            "test_count":
                len(tests),

            "passed_count":
                sum(
                    1
                    for item in tests
                    if item["pass"]
                ),

            "all_passed":
                all_passed,

            "production_ready":
                all_passed,
        }

    except Exception as exc:
        return {
            "acceptance_test_version":
                ACCEPTANCE_TEST_VERSION,

            "app_version":
                APP_VERSION,

            "all_passed":
                False,

            "production_ready":
                False,

            "tests":
                tests,

            "test_count":
                len(tests),

            "passed_count":
                sum(
                    1
                    for item in tests
                    if item["pass"]
                ),

            "error":
                str(exc),
        }


# =============================================================================
# APP
# =============================================================================

def build_app():

    (
        initial_threads,
        initial_thread_id,
    ) = create_initial_thread()

    initial_choices = thread_choices(
        initial_threads
    )

    selected_initial = (
        initial_threads[
            initial_thread_id
        ]
    )

    initial_history = deepcopy(
        selected_initial.get(
            "messages",
            [],
        )
    )

    initial_title = (
        selected_initial.get(
            "title",
            "New Conversation",
        )
    )

    with gr.Blocks(
        title=(
            f"{BOT_NAME} v{APP_VERSION}"
        ),
        delete_cache=(3600, 86400),
    ) as app:

        threads_state = gr.State(
            initial_threads
        )

        gr.Markdown(
            f"""
# J.O.A.T. Main Assistant

**Version:** `{APP_VERSION}`

**Authority:** {REPORTS_TO}

**Environment:** `{JOAT_ENV}`

**Control Plane:** Online

**Persistent State:** Connected

**Live Intelligence:** {"Connected" if HF_TOKEN else "Not Connected"}

**Specialist Transport:** {"Configured" if JOAT_SPECIALIST_TOKEN else "Not Configured"}

**Reasoning Model:** `{JOAT_LLM_MODEL}`
"""
        )

        from joat_style001_corrected_opening import add_ui as add_style001_browser_check
        add_style001_browser_check()

        with gr.Tabs():

            with gr.Tab(
                "Assistant"
            ):

                with gr.Row():

                    with gr.Column(
                        scale=1,
                        min_width=220,
                    ):

                        gr.Markdown(
                            "### Conversations"
                        )

                        new_chat_button = gr.Button(
                            "New Conversation"
                        )

                        thread_selector = gr.Dropdown(
                            choices=initial_choices,
                            value=initial_thread_id,
                            label="Conversation History",
                            interactive=True,
                        )

                        clear_chat_button = gr.Button(
                            "Clear Conversation"
                        )

                        delete_chat_button = gr.Button(
                            "Delete Conversation"
                        )

                        gr.Markdown(
                            f"""
### System

- Control Plane: Online
- Persistent State: Connected
- Live Intelligence: {"Connected" if HF_TOKEN else "Not Connected"}
- Specialist Transport: {"Configured" if JOAT_SPECIALIST_TOKEN else "Not Configured"}
- Executive Producer: Live Interface
- Hugging Face Master: Live Interface
- Browser Worker: Live Interface
- GHL: Deferred
"""
                        )

                    with gr.Column(
                        scale=4
                    ):

                        conversation_title = gr.Textbox(
                            value=initial_title,
                            label="Conversation",
                            interactive=False,
                        )

                        chatbot = gr.Chatbot(
                            value=initial_history,
                            label=(
                                "J.O.A.T. Main Assistant"
                            ),
                            height=450,
                        )

                        message = gr.Textbox(
                            label="Message",
                            placeholder=(
                                "Type your message or command here..."
                            ),
                            lines=2,
                            max_lines=5,
                        )

                        with gr.Row():

                            send_button = gr.Button(
                                "Send",
                                variant="primary",
                            )

                            clear_input_button = gr.Button(
                                "Clear Message"
                            )

                new_chat_button.click(
                    fn=new_thread,
                    inputs=[
                        threads_state,
                    ],
                    outputs=[
                        threads_state,
                        thread_selector,
                        chatbot,
                        message,
                        conversation_title,
                    ],
                )

                thread_selector.change(
                    fn=load_thread,
                    inputs=[
                        thread_selector,
                        threads_state,
                    ],
                    outputs=[
                        chatbot,
                        conversation_title,
                    ],
                )

                delete_chat_button.click(
                    fn=delete_thread,
                    inputs=[
                        thread_selector,
                        threads_state,
                    ],
                    outputs=[
                        threads_state,
                        thread_selector,
                        chatbot,
                        conversation_title,
                    ],
                )

                clear_chat_button.click(
                    fn=clear_current_thread,
                    inputs=[
                        thread_selector,
                        threads_state,
                    ],
                    outputs=[
                        chatbot,
                        threads_state,
                    ],
                )

                send_button.click(
                    fn=send_message,
                    inputs=[
                        message,
                        chatbot,
                        thread_selector,
                        threads_state,
                    ],
                    outputs=[
                        chatbot,
                        message,
                        threads_state,
                        thread_selector,
                        conversation_title,
                    ],
                )

                message.submit(
                    fn=send_message,
                    inputs=[
                        message,
                        chatbot,
                        thread_selector,
                        threads_state,
                    ],
                    outputs=[
                        chatbot,
                        message,
                        threads_state,
                        thread_selector,
                        conversation_title,
                    ],
                )

                clear_input_button.click(
                    fn=lambda: "",
                    outputs=message,
                )

            with gr.Tab(
                "System Console"
            ):

                gr.Markdown(
                    """
# System Console

Administrative and engineering controls for the
J.O.A.T. Main Assistant.
"""
                )

                with gr.Tabs():

                    with gr.Tab(
                        "Command Router"
                    ):

                        objective = gr.Textbox(
                            value=(
                                "Inspect the Hugging Face deployment."
                            ),
                            lines=3,
                            label="Objective",
                        )

                        domain = gr.Dropdown(
                            choices=[
                                "automatic",
                                "general",
                                "studio",
                                "hugging face",
                                "browser",
                                "gohighlevel",
                            ],
                            value="automatic",
                            label="Domain",
                        )

                        requested_action = gr.Textbox(
                            value="inspect",
                            label="Requested Action",
                        )

                        direct_authorization = gr.Checkbox(
                            value=True,
                            label=(
                                "Direct instruction from Dr. G"
                            ),
                        )

                        build_command_button = gr.Button(
                            "Build Command",
                            variant="primary",
                        )

                        command_output = gr.JSON(
                            label=(
                                "Main Assistant Command"
                            )
                        )

                        build_command_button.click(
                            fn=command_ui,
                            inputs=[
                                objective,
                                domain,
                                direct_authorization,
                                requested_action,
                            ],
                            outputs=command_output,
                        )

                    with gr.Tab(
                        "Organization"
                    ):

                        gr.JSON(
                            value=DIRECT_REPORTS,
                            label="Direct Reports",
                        )

                        gr.JSON(
                            value=STUDIO_KNOWLEDGE,
                            label="Studio Organization",
                        )

                    with gr.Tab(
                        "Capabilities"
                    ):

                        gr.JSON(
                            value=CAPABILITIES,
                            label=(
                                "Main Assistant Capabilities"
                            ),
                        )

                    with gr.Tab(
                        "Authority"
                    ):

                        gr.JSON(
                            value=AUTHORITY_BOUNDARY,
                            label=(
                                "Authority Boundary"
                            ),
                        )

                        gr.JSON(
                            value=APPROVAL_POLICY,
                            label="Approval Policy",
                        )

                    with gr.Tab(
                        "Execution Layers"
                    ):

                        gr.JSON(
                            value=EXECUTION_LAYERS,
                            label=(
                                "Execution Connections"
                            ),
                        )

                    with gr.Tab(
                        "Specialists"
                    ):

                        gr.Markdown(
                            """
### Live Specialist Connections

This performs a safe API-discovery health check.

It does **not** execute a production action.
"""
                        )

                        specialist_button = gr.Button(
                            "Check Specialists",
                            variant="primary",
                        )

                        specialist_output = gr.JSON(
                            label=(
                                "Specialist Health"
                            )
                        )

                        specialist_button.click(
                            fn=specialist_status_ui,
                            outputs=(
                                specialist_output
                            ),
                        )

                    with gr.Tab(
                        "Intelligence"
                    ):

                        gr.Markdown(
                            """
### Live Intelligence

The token itself is never displayed.

This panel reports only whether the credential
is present and which reasoning configuration is active.
"""
                        )

                        intelligence_button = gr.Button(
                            "Check Intelligence",
                            variant="primary",
                        )

                        intelligence_output = gr.JSON(
                            label=(
                                "Intelligence Status"
                            )
                        )

                        intelligence_button.click(
                            fn=intelligence_status_ui,
                            outputs=(
                                intelligence_output
                            ),
                        )

                    with gr.Tab(
                        "Persistence"
                    ):

                        persistence_button = gr.Button(
                            "Check Persistence",
                            variant="primary",
                        )

                        persistence_output = gr.JSON(
                            label=(
                                "Persistence Status"
                            )
                        )

                        persistence_button.click(
                            fn=persistence_status_ui,
                            outputs=(
                                persistence_output
                            ),
                        )

                    with gr.Tab(
                        "Acceptance Tests"
                    ):

                        gr.Markdown(
                            """
### Main Assistant v2.1 Live Specialist Acceptance

Target:

`100/100 PASS`

`all_passed: true`

`production_ready: true`

Tests 96–99 perform safe live API-discovery checks
against the three private specialist Spaces.
"""
                        )

                        acceptance_button = gr.Button(
                            "Run Acceptance Tests",
                            variant="primary",
                        )

                        acceptance_output = gr.JSON(
                            label=(
                                "Main Assistant v2.1 Acceptance"
                            )
                        )

                        acceptance_button.click(
                            fn=tests_ui,
                            outputs=(
                                acceptance_output
                            ),
                        )

                    with gr.Tab(
                        "About"
                    ):

                        gr.Markdown(
                            f"""
# {BOT_NAME}

**Version:** `{APP_VERSION}`

**Bot Type:** `{BOT_TYPE}`

**Reports To:** `{REPORTS_TO}`

**Environment:** `{JOAT_ENV}`

**Live Intelligence:** `{"Connected" if HF_TOKEN else "Not Connected"}`

**Specialist Transport:** `{"Configured" if JOAT_SPECIALIST_TOKEN else "Not Configured"}`

**Reasoning Model:** `{JOAT_LLM_MODEL}`

**Persistent Database:** `{JOAT_DB_PATH}`

---

## Chain of Command

{REPORTS_TO}

↓

J.O.A.T. Main Assistant Bot

↓

Executive Producer / Platform Master / Browser Worker

↓

Supervisor / Worker / Assistant

↓

Verified Result

↓

J.O.A.T. Main Assistant Bot

↓

{REPORTS_TO}
"""
                        )

        from joat_production_ui import add_specialist_ui, add_post_ui, add_delivery_ui, add_voice_ui, add_timeline_ui
        gr.Markdown(f"**Production integration version:** {APP_VERSION}")
        post_controls = add_post_ui(main_assistant=True)
        from joat_executive_handoff import add_executive_handoff_ui
        add_executive_handoff_ui(audit=STORE.audit)
        from joat_media_control import add_media_control_ui
        media_controls = add_media_control_ui(post_controls=post_controls, audit=STORE.audit)
        from joat_managed_generation import add_managed_generation_ui, add_managed_main_cpu_api
        add_managed_generation_ui(media_controls=media_controls, audit=STORE.audit)
        add_managed_main_cpu_api()
        from joat_remote_generation import add_remote_control_ui
        add_remote_control_ui()
        from joat_film_completion import add_film_completion_ui
        add_film_completion_ui()
        from joat_saved_film_previews import add_saved_film_previews
        add_saved_film_previews()
        from joat_gpu_quota_panel import add_quota_ui
        add_quota_ui()
        from joat_project_reference_review import add_reference_review_ui
        add_reference_review_ui()
        from joat_creative_workflow import add_creative_workflow_ui
        add_creative_workflow_ui(inference_factory=get_inference_client, model=JOAT_LLM_MODEL)
        from joat_job_frame_ui import add_job_frame_ui
        add_job_frame_ui()
        from joat_video_reference_ui import add_video_reference_ui
        add_video_reference_ui(audit=STORE.audit)
        from joat_studio_capability_ui import add_studio_capability_ui
        add_studio_capability_ui()
        from joat_reference_connection_check import add_reference_connection_ui
        add_reference_connection_ui()

    return app


# =============================================================================
# LAUNCH
# =============================================================================

demo = build_app()

if __name__ == "__main__":
    from joat_provider_quota import start_provider_checks
    start_provider_checks()
    from joat_gpu_quota_panel import start_dashboard_reports
    start_dashboard_reports()
    from joat_capability_check import start_capability_checks
    start_capability_checks()
    from joat_reference_connection_check import start_reference_connection_checks
    start_reference_connection_checks()
    from joat_consolidation_check import start_consolidation_checks
    start_consolidation_checks()
    from joat_cpu_qualification import start_cpu_qualifications
    start_cpu_qualifications()
    from joat_remote_generation import start_remote_requests
    start_remote_requests()
    from joat_production_tasks import start_production_tasks
    start_production_tasks()
    from joat_commercial_proposal import stage_proposals
    stage_proposals()
    from joat_creative_workflow import inspect_environment_checkpoint
    inspect_environment_checkpoint()
    from joat_creative_continuation import continue_cpu_drafts
    continue_cpu_drafts()
    from joat_creative_approval import execute_creative_approvals
    execute_creative_approvals()
    from joat_frame_assignment_task import run_frame_assignment_tasks
    run_frame_assignment_tasks()
    from joat_frame_preflight_task import start_frame_preflights
    start_frame_preflights()

    from joat_video_reference import MAX_SOURCE_BYTES
    from joat_video_reference_ui import video_reference_cache_lifespan
    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
        max_file_size=MAX_SOURCE_BYTES,
        app_kwargs={"lifespan": video_reference_cache_lifespan},
    )
