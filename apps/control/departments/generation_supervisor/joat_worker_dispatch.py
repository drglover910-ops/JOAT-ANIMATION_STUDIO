"""J.O.A.T. Stage 21: authenticated Supervisor -> Generation Worker packet handoff.

This module prepares execution packets only. It does not render media.
"""
import hashlib
import json
import os
from typing import Any

WORKER_SPACE = "Dezz-9-10/J.O.A.T.-Generation-Worker-Bot"
VERIFIED_WORKER_API = "/execution_ui"


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def validate_worker_response(result: Any, job: dict) -> dict:
    """Accept only an intact execution contract for the exact submitted job."""
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            raise ValueError("Worker returned invalid JSON") from None
    if not isinstance(result, dict) or result.get("schema") != "joat.generation_execution.v1":
        raise ValueError("Worker returned an unexpected execution schema")
    if result.get("source_job_fingerprint") != job["job_fingerprint"]:
        raise ValueError("Worker returned an execution for a different job")
    core = dict(result)
    claimed = core.pop("execution_fingerprint", None)
    if claimed != hashlib.sha256(_stable(core).encode("utf-8")).hexdigest():
        raise ValueError("Worker execution fingerprint mismatch")
    for field in ("job_type", "engine", "project_context"):
        if result.get(field) != job.get(field):
            raise ValueError("Worker changed the submitted job context")
    contract = result.get("engine_contract")
    if not isinstance(contract, dict) or contract.get("engine") != job.get("engine"):
        raise ValueError("Worker changed the approved engine")
    inputs = contract.get("input_contract")
    if not isinstance(inputs, dict):
        raise ValueError("Worker execution input contract missing")
    for field in ("prompt_contract", "generation_specification", "project_context", "source_packet_fingerprints"):
        if inputs.get(field) != job.get(field, {}):
            raise ValueError("Worker changed a locked execution input")
    policy = result.get("immutability_policy", {})
    if not isinstance(policy, dict) or any(
        policy.get(field) is not False for field in (
            "source_job_mutation_allowed", "locked_upstream_mutation_allowed",
            "creative_instruction_mutation_allowed",
        )
    ):
        raise ValueError("Worker execution permits prohibited mutation")
    if result.get("media_rendered", False) is not False:
        raise ValueError("Execution-packet endpoint cannot prove rendered media")
    return result


def handoff_generation_packet(supervisor_packet: dict) -> dict:
    """Send an already-built supervisor packet to the worker's execution-packet API.

    Fail closed if the worker's API is not unambiguously identifiable.
    """
    if os.getenv("JOAT_DISPATCH_ENABLED", "false").lower() != "true":
        raise RuntimeError("Dispatch disabled: JOAT_DISPATCH_ENABLED must be true")
    token = os.getenv("JOAT_SPECIALIST_TOKEN", "")
    signing_key = os.getenv("JOAT_DISPATCH_SIGNING_KEY", "")
    if not token or not signing_key:
        raise RuntimeError("Missing existing JOAT_SPECIALIST_TOKEN or JOAT_DISPATCH_SIGNING_KEY")
    if not isinstance(supervisor_packet, dict):
        raise ValueError("Build a Supervisor packet before sending it")
    if supervisor_packet.get("schema") != "joat.generation_supervisor_packet.v1":
        raise ValueError("Unexpected Supervisor packet schema")
    if supervisor_packet.get("production_ready") is not True:
        raise ValueError("Supervisor packet is not approved")
    packet_copy = dict(supervisor_packet)
    claimed_packet_fp = packet_copy.pop("packet_fingerprint", None)
    actual_packet_fp = hashlib.sha256(_stable(packet_copy).encode()).hexdigest()
    if claimed_packet_fp != actual_packet_fp:
        raise ValueError("Supervisor packet fingerprint mismatch")
    job = supervisor_packet.get("generation_job", {})
    if not isinstance(job, dict) or job.get("schema") != "joat.generation_job.v1":
        raise ValueError("Invalid generation job")
    job_copy = dict(job)
    claimed_job_fp = job_copy.pop("job_fingerprint", None)
    actual_job_fp = hashlib.sha256(_stable(job_copy).encode()).hexdigest()
    if claimed_job_fp != actual_job_fp:
        raise ValueError("Generation job fingerprint mismatch")
    if job.get("downstream_handoff", {}).get("ready_for_generation_worker") is not True:
        raise ValueError("Worker handoff not approved")

    try:
        from gradio_client import Client
    except ImportError as exc:
        raise RuntimeError("Install gradio_client in requirements.txt") from exc

    # The Worker API name must be verified, not inferred from a UI label.
    # /execution_ui was verified from the Worker's published metadata at
    # d8353c9b77c8a0bfd51fbe33abda42408f05f967. An incompatible override fails closed.
    endpoint = os.getenv("JOAT_GENERATION_WORKER_API_NAME", "").strip() or VERIFIED_WORKER_API
    if endpoint != VERIFIED_WORKER_API:
        raise RuntimeError("Worker API setting differs from the verified /execution_ui route")
    # Existing Worker contract consumes the supervisor packet. Exact argument shape
    # must match its published API; do not silently retry different payload shapes.
    payload = json.dumps(supervisor_packet, ensure_ascii=False)
    client = None
    try:
        client = Client(WORKER_SPACE, token=token, verbose=False)
        result = client.submit(payload, api_name=endpoint).result(timeout=90)
    except Exception:
        # Remote exception messages can include request details. Do not expose
        # them through a public UI or retry a possibly completed request.
        raise RuntimeError("Worker API request failed or timed out; no automatic retry was made") from None
    finally:
        if client is not None:
            client.close()
    result = validate_worker_response(result, job)
    return {
        "status": "worker_api_returned",
        "worker_space": WORKER_SPACE,
        "worker_api": endpoint,
        "job_fingerprint": claimed_job_fp,
        "worker_response": result,
        "execution_fingerprint": result["execution_fingerprint"],
        "response_validated": True,
        "media_rendered": False,
    }
