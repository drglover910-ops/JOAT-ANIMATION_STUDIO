---
title: J.O.A.T. Character Asset Master
emoji: 🎭
colorFrom: purple
colorTo: indigo
sdk: gradio
sdk_version: 5.49.1
app_file: app.py
pinned: false
---

# J.O.A.T. Character & Asset Master v1.0

Authoritative worker #1 for the J.O.A.T. studio architecture.

## Boundary
- Owns character registry, approved references, hashes, selection policy, identity/continuity rules.
- Produces machine-readable character packets for Director / Studio Operations / LTX.
- Does **not** modify LTX core.
- Does **not** silently mutate approved character identity.

## Baseline
CHAR-001 Founder is loaded with the 11 approved supplied references and SHA-256 integrity records.

## Acceptance
Run `python test_character_master.py` or use the Acceptance Test tab.
