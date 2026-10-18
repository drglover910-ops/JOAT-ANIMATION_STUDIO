"""J.O.A.T. Stage 20 — signed, preview-only Main Assistant → Executive Producer dispatch.
Run inside Main Assistant Space, with existing JOAT_DISPATCH_SIGNING_KEY and
JOAT_SPECIALIST_TOKEN secrets. Never prints either secret.
"""
import hashlib
import hmac
import json
import os
import time
import uuid
from gradio_client import Client

EP_SPACE = "Dezz-9-10/J.O.A.T.-Executive-Producer-Bot"
SCHEMA = "joat.executive_producer_dispatch.v1"

def build_preview(project_id="PROJECT-STAGE20-001"):
    secret = os.environ.get("JOAT_DISPATCH_SIGNING_KEY", "")
    if len(secret) < 32:
        raise RuntimeError("Main Assistant signing key missing or too short")
    packet = {
        "schema": SCHEMA,
        "source_bot": "J.O.A.T. Main Assistant Bot",
        "target_bot": "J.O.A.T. Executive Producer Bot",
        "authorized": True,
        "work_order_id": "WO-STAGE20-" + uuid.uuid4().hex[:12],
        "project_id": project_id,
        "department_role": "character",
        "endpoint": "/packet",
        "arguments": {},
        "nonce": uuid.uuid4().hex,
        "issued_at_epoch": time.time(),
        "execute_live": False,
    }
    unsigned = json.dumps(packet, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    packet["signature"] = hmac.new(secret.encode(), unsigned.encode(), hashlib.sha256).hexdigest()
    return packet

def run_preview():
    token = os.environ.get("JOAT_SPECIALIST_TOKEN", "")
    if not token:
        raise RuntimeError("Main Assistant transport token missing")
    packet = build_preview()
    client = Client(EP_SPACE, token=token, verbose=False)
    result = client.predict(json.dumps(packet, sort_keys=True, ensure_ascii=False, separators=(",", ":")), api_name="/dispatch_department")
    if not isinstance(result, dict) or result.get("status") != "validated_preview_only" or result.get("downstream_execution_performed") is not False:
        raise RuntimeError("Unexpected response: " + repr(result))
    return result

if __name__ == "__main__":
    print(json.dumps(run_preview(), indent=2))
