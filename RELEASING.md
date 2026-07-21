# Releasing pilotfish-grok

1. Bump `VERSION` (semver).
2. Sync the version stamp in `templates/rules.pilotfish-grok.md`
   (`<!-- pilotfish-grok vX.Y.Z -->`).
3. Add a `CHANGELOG.md` entry describing what this release actually ships.
4. Run:

   ```sh
   python3 -m unittest discover -s tests -v
   python3 benchmarks/e2e-dispatch/run.py --skip-live
   # optional live approval-gate + dispatch proof (spend):
   # python3 benchmarks/e2e-dispatch/run.py
   git diff --check
   ```

5. Commit, tag `vX.Y.Z`, push, and create a GitHub release if the remote is public.
6. If agent or role templates changed, keep installed `~/.grok/agents` and
   `~/.grok/roles` in mind for the next upgrade path (idempotent installer).

Do not claim runtime multi-model savings in release notes unless the catalog and
`[subagents.models]` pins actually provide distinct cheaper models.
