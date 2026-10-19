# Authenticated quota and private Reference Lab storage

File version: 1.0.2. October 18, 2026, Eastern time.

Owner saved the existing JOAT-Main-Assistant token permissions. Native Main
check 22e2c0ec4a01429985c5171eee80d2bf now returns HTTP 200 with billing read
permission true: 2400 remaining of 2400 included GPU seconds, reset null and
zero overquota used. Credit balance remains independently unknown; no spending
authority is inferred. No browser automation or new secret was needed.

The first supplemental scene request stopped at Reference Lab's storage check.
Owner-authenticated logs show require_mount used anonymous HTTP to inspect the
now-private Lab's metadata and raised before creating its reference directory,
source loading, or GPU allocation. Actual bucket metadata confirms the existing
/studio read/write mount is correct. Sources themselves remain available and
pinned; no bucket remount, secret rotation or creative changes are needed.

Reference Lab app 2.18 and joat_job_assets.py 1.0.3 authenticate that exact
metadata request with the calling owner credential already verified by the API,
falling back to the existing service secret for other callers, and retain source/path/access
checks. Project reference API 1.0.5 adds an owner-only CPU storage check. Main
2.1.108 / production tasks 1.0.23 verify that check before reconciling the failed
call. Recovery 1.0.2 requires a terminal upstream failure, exact project/request,
and complete absence of Reference Lab's pre-GPU directory; any reference-side
execution evidence prevents release. It archives the original local reservation
and keeps the failed task receipt. This permits a fresh explicitly submitted task
for the same unexecuted candidate without deleting generation evidence or
retrying unknown GPU work. No retry is scheduled by the recovery operation.

93 CPU tests and shared-source consistency pass, including authenticated private
mount access and denial cases, unknown/executed recovery rejection and immutable
failure/reservation evidence. The intermediate stored-credential preflight was also denied; verified caller
authentication addresses that boundary without copying secrets. The final native storage preflight passed. Recovery preserved both failed-call
archives, and the first exact reference reservation is now confirmed in Reference
Lab. Candidate generation is in progress; no finished-image or film approval
is implied. Immutable scope data keeps version 1.0.0 across code upgrades. See private_reference_storage_v1.0.0.json and the quota receipt.
