# Quota and credit visibility

File version: 1.0.0. October 18, 2026.

Main Assistant 2.1.101 records the owner's dashboard observation in the existing
private shared studio store. The reported ZeroGPU counter is 0 of 40 minutes
used, interpreted as 40 included minutes remaining. Credits are separately
reported as $3.68. The inference usage label is preserved exactly as "0.05%";
it is not converted into a dollar charge or GPU minutes. Paid-spending authority
remains zero. These values are owner-reported, not independently verified billing.

The existing GPU Quota panel now shows credits separately, identifies source and
timestamp, removes the old prefilled 24.1-minute value, and marks records older
than fifteen minutes stale. Refresh reads saved data without renewing its age.
The existing reference-reservation estimate is explicitly labeled incomplete:
untracked video requests and other account Spaces can consume quota. It must
not be represented as an account-wide automatic spending stop or live provider
balance. Existing single-report confirmations remain byte-compatible.

Read-only research found no quota/billing methods in the installed Hub SDK or
documented balance endpoint in the inspected Hub API documentation. An authenticated
token request to the billing page returned HTTP 302 to login. The published
spaces 0.51.3 SDK reports quota through scheduling responses; scheduling is a
resource-allocation operation, so it was not invoked as a passive balance check.
No authenticated browser connector is available in this session. A working,
persistent owner-authenticated browser connection would need to be established
and verified before advertising automatic screen reading. No passwords or
browser cookies were collected, copied or stored.

One shared account observation should serve Main and the Director's future
studio UI. Main remains the account-wide coordinator; Director receives scoped
production budgets. No separate per-department balance or additional GPU service
is required. Automatic provider observations should preserve source, time,
account identity and raw display labels, and must never silently reclassify an
estimate as live or authorize credit spending.

74 CPU tests passed, including used-versus-remaining conversion, stale data,
unchanged refresh timestamps, integrity failures, invalid inputs, legacy records
and compatibility with existing zero-credit reference reservations. The Main
interface builds, deployed source bytes match, and the saved report was read
back from private shared storage. No GPU or inference call was made.

Sources inspected: https://huggingface.co/docs/hub/spaces-zerogpu,
https://huggingface.co/docs/hub/billing, https://huggingface.co/docs/hub/api.
Official ZeroGPU documentation says included PRO quota is 40 minutes, resets
24 hours after first GPU use, and additional use can automatically consume
prepaid credits. A saved credit balance is not permission to consume it.
