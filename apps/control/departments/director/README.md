---
title: J.O.A.T. Director Creative Intelligence
emoji: 👁
colorFrom: indigo
colorTo: purple
sdk: gradio
sdk_version: 4.44.1
app_file: app.py
pinned: false
python_version: "3.10"
hf_oauth: true
hf_oauth_scopes:
  - read-repos
---

# J.O.A.T. Director Creative Intelligence

**Director Worker v1.0.2** — Consumes locked character packets (joat.character_packet.v1) and produces deterministic director packets (joat.director_packet.v1) for production planning.

## Overview

The J.O.A.T. Director Creative Intelligence is a production-ready Director worker in the J.O.A.T. (Joint Operations Architecture for Theatre) virtual studio pipeline. It operates as a **read-only consumer** of the J.O.A.T. Character Asset Master — it never reads the file system for characters.json at runtime during director packet generation (it builds character packets from the embedded data), and it **never mutates** the Character Asset Master registry.

### Key Capabilities

- **Character Packet Validation**: Validates identity lock and approval fields from character packets
- **Deterministic IDs**: project_id is derived from a hash of the creative brief
- **Constraint Preservation**: All character constraints (appearance rules, continuity rules, negative rules, source asset hashes) are carried into director packets
- **No Registry Mutation**: The Character Asset Master is never modified
- **Full Shot-Level Detail**: Per-shot fields for camera framing/angle/movement, performance/action, dialogue/narration, audio/music/SFX, caption/on-screen-text

## Director Packet Schema (joat.director_packet.v1)

The director packet contains:

| Field | Description |
|-------|-------------|
| `schema` | `joat.director_packet.v1` |
| `version` | `1.0.2` |
| `project_id` | Deterministic ID derived from creative brief hash |
| `created_at` | ISO 8601 timestamp |
| `creative_brief` | Free-text creative brief/idea |
| `production_intent` | e.g. animation, live_action, mixed |
| `scene_plan` | Array of scenes with shot_id, scene_id |
| `per_shot` | Per-shot detail including: |
| | - `shot_id`, `scene_id`, `character_ids` |
| | - `character_packet_references` / `character_constraints` |
| | - `environment_requirements` |
| | - `camera_framing` (framing, angle, movement) |
| | - `performance_action` |
| | - `dialogue_narration` |
| | - `audio_music_sfx` |
| | - `caption_on_screen_text` |
| | - `duration` |
| `continuity_constraints` | Continuity constraint descriptions |
| `generation_instructions` | Generation instructions |
| `qc_gates` | Quality control gate list |
| `downstream_handoff` | Downstream handoff metadata |

## Usage

### API
```python
from director import generate_director_packet, build_character_packet

# Build character packet from registry
char_packet = build_character_packet("ae150e40-1123-450a-ac71-6c119e3d5d62")
packet_json = json.dumps(char_packet)

# Generate director packet
director = generate_director_packet(
 creative_brief="A young hero journeys through a dark forest",
 character_packet_json=packet_json,
 production_intent="animation",
)
```

### Gradio UI
Open the Space to use the interactive Gradio UI with three tabs:
1. **Director Generation** — Input creative brief, select character, set shot parameters, generate director packet
2. **Acceptance Tests** — Run the full test suite
3. **About** — Schema documentation

## Acceptance Tests

The test suite covers:
1. **Schema generation** with valid input — produces correct director packet
2. **Reject unlocked character packets** — identity_locked must be True
3. **Reject malformed character packets** — invalid JSON or missing required fields
4. **Preservation of character constraints** — appearance_rules, continuity_rules, negative_rules, source_asset_hashes
5. **Required per-shot fields present** — shot_id, scene_id, character_ids, camera_framing, etc.
6. **Deterministic project IDs** — same creative brief + character = same project_id
7. **No registry file mutation** — characters.json is never modified

## Files

- `app.py` — Main application (Gradio UI + core logic + acceptance tests)
- `characters.json` — Character registry (read-only copy from Character Asset Master)
- `requirements.txt` — Dependencies (gradio)
- `README.md` — This file

## Dependencies

- `gradio` — For the interactive web UI

## Related Spaces

- [J.O.A.T. Character Asset Master](https://huggingface.co/spaces/Dezz-9-10/J.O.A.T.-Character-Asset-Master) — Read-only reference
- [J.O.A.T. Animation Studio](https://huggingface.co/spaces/Dezz-9-10/J.O.A.T.-Animation-Studio) — Downstream consumer

## License

MIT

## Production connection v1.0.2

Use **Production Character Master Connection** to fetch the real locked CHAR-001–CHAR-007 packet, build a draft, and explicitly approve it while signed in as Dezz-9-10. Changing the inputs clears the draft and exports. Approval preserves creative fields and adds the approval lock and packet fingerprint required by Generation Supervisor. Existing registry, functions, and API endpoints remain intact. No media is rendered by this Space.
