# Existing architecture and responsibility boundaries

File version: 1.0.0.

Repository naming is temporary. The owner confirmed this private repository will
eventually represent Main Assistant. A future dedicated Studio repository will be
routed through the appropriate agent; no repository rename, creation or migration
is authorized or required for this release.

Main Assistant remains the ecosystem coordinator, with its own operational memory
and interfaces. It sends explicit signed work to Executive/Studio Control. The
Director role owns the approved story, casting, shot dependencies, continuity and
future production UI. The shared deployment does not combine these authorities.

Studio Control hosts the existing twenty roles: browser, Hugging Face Master,
narration, character, environment, director, shot/camera, performance/action,
generation supervisor, generation worker, independent QC, post supervisor,
editorial, sound, music, compositing/VFX, color/finish, titles/graphics,
voice/dialogue and delivery/archive. Their native contracts remain authoritative.
Source manifests verify their installed bytes. A subprocess is not a separate
security tenant; broader autonomy requires a separate credential/isolation review.

Shared production guidance is one versioned library consumed by Main and Control.
Every record is pinned in a reviewed index, with project/style/role scope, expiry,
provenance, version requirements and supersession. Package records and optionally
index-pinned records under the existing `/studio/joat-studio` mount are supported.
No bucket migration or new database service is introduced. Unindexed files and
raw transcripts cannot promote themselves into approved lessons. This initial
release curates existing policies and role guidance; it does not claim automatic
learning or semantic/vector retrieval from all previous films.

Main's system prompt receives general Main guidance only. Explicit owner tools
can retrieve project/style guidance. Control production planning receives Director
advice separately from immutable objectives. Each native role's API description
includes its own guidance without changing callback arguments or signed packets.

The current 90-second Style001 film remains the active approved creative target.
Its existing completed opening and all source approvals remain intact. New footage,
multi-person qualification, audio and final editing/QC are unfinished. Existing
budget/grant/GPU-hold controls remain mandatory.
