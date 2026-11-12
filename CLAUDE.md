# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in this repository.

## About this repository

This is a Fleet GitOps repository: the git-backed source of truth for configuring computers (macOS, Windows, Linux, iOS, iPadOS, Android, ChromeOS) managed by [Fleet](https://fleetdm.com). There's no app to build here — a commit to the default branch is a deploy. CI runs `fleetctl gitops` to apply the YAML in this repo to the live Fleet instance; pull requests get a dry run only. See `.github/workflows/workflow.yml` (GitHub) or `.gitlab-ci.yml` (GitLab).

## Team rules

This repo is public and shared by the CSE team. Follow `CONVENTIONS.md` for layout, naming, and sanitizing.

- `fleets/<name>.yml` is that person's sandbox; don't edit someone else's unless asked.
- Before changing a shared file in `platforms/` or `labels/`, run `python3 tools/check-conventions.py --who-uses <path>` and say which fleets it touches.
- Never rename a fleet's `name:` (it deletes and recreates the fleet) or create fleets in the UI (they get deleted).
- No customer data: use `example.com` and `$FLEET_SECRET_<NAME>`; regenerate every `PayloadUUID`.
- Don't commit or push. The team commits from GitHub Desktop and merges through PRs.

## Layout

- `default.yml` — org-wide settings: org info, server URL, SSO, Apple Business Manager/VPP, migration and Windows MDM controls, and the `labels:` registration.
- `fleets/*.yml` — one file per fleet (a named group of hosts, e.g. "💻 Workstations"). Each fleet's controls, software, policies, and reports live in its own file.
- `labels/{dynamic,manual,host-vitals}/*.yml` — reusable host groupings, filed by how membership is decided, used to scope profiles, software, and policies to a subset of hosts.
- `tools/` — repo tooling, not deployed: `check-conventions.py`, `update-gitops-skill.sh`, and `mdm-commands/` (sends an MDM command to hosts failing a policy, run by `.github/workflows/mdm-command-on-policy-failure.yml`).
- `docs/` — runbooks and lab write-ups, not deployed.
- `platforms/<macos|windows|linux|ios|ipados|android|all>/` — the actual artifacts, one flat folder per kind (no sub-folders):
  - `policies/` — compliance policies (osquery-based checks with a resolution)
  - `reports/` — data collection reports
  - `software/` — custom package definitions
  - `scripts/` — `.sh`/`.ps1` scripts available for automations and manual runs
  - `configuration-profiles/` — `.mobileconfig` (Apple), `.xml` (Windows), or `.json` (Android) profiles
  - `declaration-profiles/` — Apple DDM declarations (`.json`)
  - `enrollment-profiles/` — DEP/ABM automatic enrollment profiles
  - `commands/` — MDM commands
  - `managed-app-configurations/` — Android per-app managed configurations
  - `icons/` — custom software icons (`platforms/all` only)

A fleet's YAML file pulls files from these platform folders with glob patterns, e.g. `paths: ../platforms/macos/policies/*.yml`. Dropping a new file into the right folder is usually enough — check the fleet's YAML to confirm which globs apply before assuming a file needs to be wired up by hand.

## Making changes

- Add a policy, report, profile, or script by creating a file in the matching `platforms/<platform>/<kind>/` folder. Follow the format of an existing file in that folder.
- For software, prefer a [Fleet-maintained app](https://github.com/fleetdm/fleet/tree/main/ee/maintained-apps) (`fleet_maintained_apps` in a fleet's `software:` section) over a custom package when one exists.
- To scope something to part of the fleet, reference a label from `labels/*.yml` with `labels_include_any` / `labels_include_all` rather than inventing a new query inline.
- Validate keys and values against [Fleet's GitOps YAML reference](https://fleetdm.com/docs/configuration/yaml-files) before inventing one — an unrecognized key fails silently in some sections and loudly in others.
- osquery queries (in policies and reports) must use tables and columns that exist in the [Fleet osquery schema](https://fleetdm.com/tables) for the target platform.

## Validating changes

Run all three, in order:

```bash
python3 tools/check-conventions.py
python3 .claude/skills/fleet-gitops/scripts/validate.py
```

Then dry-run the same way CI does for pull requests (needs `FLEET_URL` and the CSE instance as fleetctl's default context; otherwise the PR's CI dry run is the gate):

```bash
fleetctl gitops -f default.yml $(for f in fleets/*.yml; do echo -f "$f"; done) --dry-run
```

## Terminology

- A "fleet" (this repo's `fleets/*.yml`) was formerly called a "team." The product and this repo use "fleet" now, but Fleet's REST API and some `fleetctl` flags still use `team`/`team_id` — expect that name when working with the API directly.
- A "report" is what was formerly called a "query" in Fleet's product. "Query" now refers only to the SQL itself — one part of a report or policy, not a top-level concept with its own folder.

## Skills

- `/fleet-gitops` — vendored verbatim from [fleetdm/fleet `.claude/skills/fleet-gitops`](https://github.com/fleetdm/fleet/tree/main/.claude/skills/fleet-gitops). Don't edit it here; refresh it from upstream instead. Put repo-specific rules in `CONVENTIONS.md`.
- Apple profile authoring (optional): install [contour](https://github.com/macadmins/contour), a community CLI that generates `.mobileconfig`/DDM JSON from Apple's schema, and run `contour setup-agent` to add its own skill and command index here. Contour isn't part of Fleet and isn't installed by default.

## References

- GitOps YAML reference: https://fleetdm.com/docs/configuration/yaml-files
- Fleet REST API reference: https://fleetdm.com/docs/rest-api/rest-api
- Fleet-maintained app catalog: https://github.com/fleetdm/fleet/tree/main/ee/maintained-apps
- osquery table reference: https://fleetdm.com/tables
