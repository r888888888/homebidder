---
allowed-tools: Bash(git log:*), Bash(git tag:*), Bash(git describe:*), Bash(git rev-list:*), Bash(git add:*), Bash(git commit:*), Bash(sed:*), Bash(fly deploy:*), Bash(flyctl deploy:*), Read, Edit, Write
description: Cut a release and deploy HomeBidder to Fly.io
---

## Context

- Last release tag: !`git describe --tags --abbrev=0 2>/dev/null || echo "none (no tags yet)"`
- Current [Unreleased] section of CHANGELOG.md: !`sed -n '/## \[Unreleased\]/,/## \[/{ /## \[Unreleased\]/d; /## \[/d; p }' CHANGELOG.md | head -40`

## Your task

Follow these steps in order. **Confirm with the user before running any `fly deploy` commands.**

1. **Find commits since the last tag.** Run this command (substituting the last release tag shown above):
   ```
   git log <last-tag>..HEAD --oneline
   ```
   Also run `git diff --stat HEAD` to see any uncommitted changes that should be included.

2. **Choose the new version number.** Use the last tag and commit list. Apply semver:
   - `MINOR` bump when new features are included
   - `PATCH` bump when the changes are fixes or small improvements only
   - `MAJOR` bump for breaking changes (auth overhaul, schema migration, etc.)

3. **Update `CHANGELOG.md`.** Move all entries under `## [Unreleased]` into a new section `## [X.Y.Z] - YYYY-MM-DD` (use today's date). Leave `## [Unreleased]` empty above it. If [Unreleased] is empty, synthesize entries from the commits found in step 1.

4. **Update `frontend/src/routes/changelog.tsx`.** Add a matching `Release` object to the **top** of the `RELEASES` array, mirroring the CHANGELOG.md entries exactly (same version, date, and text, categorized as `"Added"`, `"Changed"`, or `"Fixed"`).

5. **Commit and tag.** Stage all modified files (including any uncommitted work), then:
   ```
   git commit -m "chore: release vX.Y.Z"
   git tag vX.Y.Z
   ```

6. **Ask for confirmation**, then deploy both services:
   - Backend: `fly deploy` from the **project root** (uses `fly.toml`, deploys `homebidder-api`)
   - Frontend: `fly deploy` from the **`./frontend` directory** (separate Fly app, uses `frontend/fly.toml`)
