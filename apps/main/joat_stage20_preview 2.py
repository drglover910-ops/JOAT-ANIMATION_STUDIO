"""J.O.A.T. Stage 20 signed Main Assistant -> Executive Producer dispatch tester.

Runs a single approved department route per invocation. Default is validation-only.
No secrets are printed or stored. Does not modify any existing bot.
"""
import argparse
import hashlib
import hmac
import json
import os
import time
import uuid
from gradio_client import Client

EP_SPACE = "Dezz-9-10/J.O.A.T.-Executive-Producer-Bot"
SCHEMA = "joat.executive_producer_dispatch.v1"
ROUTES = {
    "character": {
        "endpoint": "/packet",
        "arguments": {"cid": "CHAR-001", "task": "identity"},
    },
    "environment": {
        "endpoint": "/build_packet_ui",
        "arguments": {
            "environment_id": "ENV-001",
            "task": "scene",
            "time_of_day": "director_defined",
            "lighting": "director_defined",
            "weather": "director_defined",
            "scene_id": "SCENE-001",
            "shot_id": "SHOT-001",
        },
    },
}


def build_request(department, execute_live=False):
    secret = os.environ.get("JOAT_DISPATCH_SIGNING_KEY", "")
    if len(secret) < 32:
        raise RuntimeError("JOAT_DISPATCH_SIGNING_KEY missing or too short")
    route = ROUTES[department]
    packet = {
        "schema": SCHEMA,
        "source_bot": "J.O.A.T. Main Assistant Bot",
        "target_bot": "J.O.A.T. Executive Producer Bot",
        "authorized": True,
        "work_order_id": "WO-STAGE20-" + uuid.uuid4().hex[:12],
        "project_id": "PROJECT-STAGE20-001",
        "department_role": department,
        "endpoint": route["endpoint"],
        "arguments": route["arguments"],
        "nonce": uuid.uuid4().hex,
        "issued_at_epoch": time.time(),
        "execute_live": execute_live,
    }
    canonical = json.dumps(packet, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    packet["signature"] = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    return packet


def main():
    parser = argparse.ArgumentParser(description="J.O.A.T. Stage 20 department dispatch tester")
    parser.add_argument("--department", choices=sorted(ROUTES), default="environment")
    parser.add_argument("--live", action="store_true", help="Explicitly request a live department call")
    args = parser.parse_args()
    token = os.environ.get("JOAT_SPECIALIST_TOKEN", "")
    if not token:
        raise RuntimeError("JOAT_SPECIALIST_TOKEN missing")
    if args.live and os.environ.get("JOAT_DISPATCH_ENABLED", "").lower() != "true":
        raise RuntimeError("Live dispatch requested but JOAT_DISPATCH_ENABLED is not true")
    packet = build_request(args.department, execute_live=args.live)
    client = Client(EP_SPACE, token=token, verbose=False)
    response = client.predict(
        json.dumps(packet, sort_keys=True, ensure_ascii=False, separators=(",", ":")),
        api_name="/dispatch_department",
    )
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except json.JSONDecodeError:
            pass
    print(json.dumps({
        "department": args.department,
        "requested_live": args.live,
        "work_order_id": packet["work_order_id"],
        "response": response,
    }, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
