# Releasing Vibe HUD

This describes how Vibe HUD ships installable builds for macOS, Windows,
and Ubuntu via GitHub Actions. It's the practical "how do I cut a release"
reference — for the reasoning behind these choices (why Briefcase, why one
shared version number, etc.), see
`docs/superpowers/specs/2026-09-16-github-release-pipeline-design.md`.

Packaging is done with [Briefcase](https://briefcase.readthedocs.io/),
which builds a macOS `.dmg`, a Windows `.msi`, and an Ubuntu `.deb` from
the same `pyproject.toml`.

> **Ubuntu is temporarily disabled** in the Build & Release workflow (see
> the note in `.github/workflows/build-release.yml`'s `FULL_MATRIX`). The
> `create`/`build`/`package` cycle was fully verified working in a local
> `ubuntu:24.04` container, but the resulting `.deb`'s runtime dependency
> closure (does it actually pull in GTK/WebKit/PyGObject on a machine that
> doesn't already have the build-time packages installed?) hasn't been
> confirmed yet. Only macOS and Windows currently build via CI.

---

## Cutting a normal release

1. Go to **Actions → Prepare Release → Run workflow**.
2. Choose a bump type (`patch` / `minor` / `major`) or type an explicit
   version (e.g. `0.3.0`).
3. This workflow:
   - Creates (or reuses) a `release/X.Y` branch off `main`.
   - Runs `poetry version` to bump `[project].version` in `pyproject.toml`,
     then syncs `[tool.briefcase].version` to match — Briefcase reads its
     own version from `[tool.briefcase]`, not `[project]`, so the two
     fields have to be kept in lockstep.
   - Commits that bump (`chore: bump version to X.Y.Z`).
   - Tags the commit `vX.Y.Z` and pushes the branch + tag.
4. The tag push automatically triggers **Build & Release**, which:
   - Builds the macOS `.dmg`, Windows `.msi`, and Ubuntu `.deb` in
     parallel (one GitHub-hosted runner per OS — Briefcase can't
     cross-compile, so each platform's artifact is only ever built on
     that platform's own runner).
   - If **all three** succeed, publishes a GitHub Release for `vX.Y.Z`
     with all three files attached and auto-generated release notes.
   - If **any** platform fails, no release is published at all — check
     the failed job's log, fix, and either re-run the workflow or push a
     new patch version.

No local `git`/`poetry` commands are required for a normal release — the
whole thing runs from the GitHub Actions UI, so anyone with write access to
the repo can cut one.

---

## Hotfixing an old release

Release branches (`release/X.Y`) are permanent, so you can always go back:

```bash
git checkout release/0.2
# make the fix, commit it
poetry version 0.2.1
git commit -am "chore: bump version to 0.2.1"
git tag v0.2.1
git push origin release/0.2 --tags
```

`main` doesn't need to be touched or be in any particular state — the fix
only needs to exist on the release branch itself. Pushing the tag triggers
**Build & Release** exactly as above.

---

## Patching a single platform without a full re-release

If a change only affects one platform (say, a Windows-only bug in
`vibe_hud/platform/windows.py`), you don't need to force a meaningless
rebuild of the untouched macOS/Ubuntu artifacts:

1. Go to **Actions → Build & Release → Run workflow**.
2. Set `tag` to the existing release tag (e.g. `v0.3.0`).
3. Set `platforms` to just the one you need (e.g. `windows`).
4. This rebuilds only that platform's artifact and replaces it in the
   already-published `v0.3.0` release — the mac/ubuntu files already
   attached to that release are left as-is.

---

## Known limitations

- **No code signing yet.** Nobody's stopping you from opening
  `Actions → Prepare Release`, but there's no Apple Developer account or
  Windows code-signing certificate configured. That means:
  - **macOS:** the `.dmg`/`.app` is ad-hoc signed (required just to run at
    all on modern macOS) but not signed with a real Developer ID, so
    Gatekeeper will still warn "Apple could not verify..." on first open.
    Users need to right-click → Open (or clear the quarantine flag) once.
  - **Windows:** the `.msi` is unsigned, so Windows SmartScreen will warn
    "Windows protected your PC." Users need to click "More info" → "Run
    anyway."
  - Signing can be added later once certificates exist — not solved here.
- **The Ubuntu `.deb` targets whatever Ubuntu LTS version the GitHub
  `ubuntu-latest` runner currently is** (it's built against that runner's
  own system libraries, e.g. `libwebkit2gtk`). Users on a different
  Ubuntu version (or another distro entirely) may hit a library version
  mismatch and need to install from source instead.
- **One shared version number across all three platforms.** Even a
  Windows-only change bumps the version everyone sees. This is
  intentional — see the spec's Non-goals section for why per-platform
  independent versioning was rejected.

---

## File layout

```
.github/workflows/
  prepare-release.yml   # cuts a release: branch + version bump + tag
  build-release.yml     # builds all 3 platforms and publishes the GitHub Release
pyproject.toml          # [tool.briefcase] packaging config lives here
assets/icon/
  generate_icon.py      # Pillow script that draws the icon and renders every
                         # file below from it — there's no source .svg
  vibe-hud-1024.png      # rendered artwork, largest size
  vibe-hud-512.png       # rendered artwork, smaller size
  vibe-hud.icns          # macOS app icon (built via iconutil, macOS-only)
  vibe-hud.ico           # Windows app icon
vibe_hud/assets/
  tray-icon-32.png       # packaged with the app; used at runtime for the
  tray-icon-64.png       # macOS/Windows/Linux menu bar tray icon
```
