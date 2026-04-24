---
allowed-tools: Bash(git log:*), Bash(git tag:*), Bash(git describe:*), Bash(git rev-list:*), Bash(git add:*), Bash(git commit:*), Bash(sed:*), Bash(fly deploy:*), Bash(flyctl deploy:*), Read, Edit, Write
description: Cut a release and deploy HomeBidder to Fly.io
---

## Context

- Last release tag: !`git describe --tags --abbrev=0 2>/dev/null || echo "none (no tags yet)"`
- Recent commits since last tag: !`git log $(git describe --tags --abbrev=0 2>/dev/null || git rev-list --max-parents=0 HEAD)..HEAD --oneline 2>/dev/null`
- Current [Unreleased] section of CHANGELOG.md: !`sed -n '/## \[Unreleased\]/,/## \[/{ /## \[Unreleased\]/d; /## \[/d; p }' CHANGELOG.md | head -40`

## Your task

Follow these steps in order. **Confirm with the user before running any `fly deploy` commands.**

1. **Choose the new version number.** Use the last tag and commit list above. Apply semver:
   - `MINOR` bump when new features are included
   - `PATCH` bump when the changes are fixes or small improvements only
   - `MAJOR` bump for breaking changes (auth overhaul, schema migration, etc.)

2. **Update `CHANGELOG.md`.** Move all entries under `## [Unreleased]` into a new section `## [X.Y.Z] - YYYY-MM-DD` (use today's date). Leave `## [Unreleased]` empty above it.

3. **Update `frontend/src/routes/changelog.tsx`.** Add a matching `Release` object to the **top** of the `RELEASES` array, mirroring the CHANGELOG.md entries exactly (same version, date, and text, categorized as `"Added"`, `"Changed"`, or `"Fixed"`).

4. **Commit and tag.**
   ```
   git add CHANGELOG.md frontend/src/routes/changelog.tsx
   git commit -m "chore: release vX.Y.Z"
   git tag -a vX.Y.Z -m "vX.Y.Z"
   ```

5. **Ask for confirmation**, then deploy:
   - Backend: `fly deploy` from the project root (deploys `homebidder-api` per fly.toml)
   - Frontend: `fly deploy` from the `./frontend` directory (separate Fly app)
