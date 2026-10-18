# Release and rollback

File version: 1.0.0.

1. Preserve exact current HF revisions and unchanged secret/mount/hardware bindings.
2. Run shared-source checks, knowledge integrity/scope tests, Gradio construction,
   and existing approval/idempotency regressions without GPU inference.
3. Update Control's source manifest hashes and version before deployment. Preserve
   canonical-resource entries, native contracts and all independent QC gates.
4. Upload only changed reviewed files using a parent-revision guard. Do not delete
   media, overwrite project state, alter canonical assets or reset secrets.
5. Verify the deployed bytes, CPU hardware, private visibility and retained GPU hold.
6. Refresh Main's exact Control source pin only after comparing the named endpoint
   contracts. Existing pinned metadata may be retained only when all referenced
   existing endpoints remain byte-compatible in schema and function index.
7. If recovery is needed, restore the changed source files from the captured prior
   HF revision and deploy a newly incremented release. Restore Main's Control pin
   to the actual restored revision; do not blindly pin an old revision identifier
   after creating a new commit. Review in-flight generation state before any restart.

The source backup excludes canonical images and runtime databases. Restore their
existing pinned HF resources when rebuilding a local full Control bundle. SQLite
backup requires the supported online backup API or a consistent stopped-writer
snapshot, not copying a live database without its WAL. A database restore drill
has not been performed by this source/knowledge release.
