# Fleet CSE GitOps

The Fleet CSE team's shared test instance, configured entirely from this repo. Each of us has a
sandbox fleet to try things in, and we share one library of policies, reports, profiles, scripts,
and labels that anyone can pull into their fleet.

> **This repo is public.** Nothing from a customer engagement goes in unless it has been sanitized:
> no customer names, domains, hostnames, people, IPs, SSIDs, tenant IDs, certificates, or secrets.
> See [CONVENTIONS.md § 5](CONVENTIONS.md#5-customer-data-never-in-git).

## How changes deploy

**Never push to `main`.** Work on a branch and open a pull request.

| You do | What happens |
|---|---|
| Open a pull request | GitHub Actions runs `fleetctl gitops --dry-run` against the live instance (the `fleet-gitops` check). [CODEOWNERS](.github/CODEOWNERS) asks the owner of any fleet you touched to review. |
| Merge it | The same workflow **applies it to the live instance** within minutes. |
| Nightly, 06:00 UTC | The workflow re-applies `main`, so changes made in the Fleet UI are reverted to what's in git. |

The apply runs with `--delete-other-fleets`: **a fleet that isn't a file in `fleets/` gets deleted**,
and **changing a fleet's `name:` deletes and recreates it**, which drops its hosts to Unassigned. To
rename one, follow [docs/runbooks/fleet-rename.md](docs/runbooks/fleet-rename.md).

## Fleets

| File | Fleet | Owner |
|---|---|---|
| `fleets/adam.yml` | Adam's Adequate Fleet | Adam |
| `fleets/dale.yml` | Dale's Fleet | Dale |
| `fleets/gray.yml` | Gray's Fleet | Gray |
| `fleets/josh.yml` | Josh's All-Star Fleet | Josh |
| `fleets/mason.yml` | Mason's Mega Fleet | Mason |
| `fleets/matt.yml` | Matt's Fleet | Matt |
| `fleets/noel.yml` | Noel's Fleet | Noel |
| `fleets/ryn.yml` | Ryn's Fleet | Ryn |
| `fleets/workstations.yml` | Workstations | Team: only validated, demo-ready config |

Your fleet file is your sandbox. Don't edit someone else's without asking. `fleets/adam.yml` is the
most complete example of wiring the library together; copy entries from it.

## Layout

```
default.yml            org settings (one team-owned file) + label registration
fleets/                one file per fleet
labels/dynamic/        SQL-based labels
labels/manual/         hand-picked host lists
labels/host-vitals/    IdP group / department labels
platforms/<platform>/  the shared library, one flat folder per kind:
                       policies/ reports/ scripts/ software/ configuration-profiles/
                       declaration-profiles/ enrollment-profiles/ commands/
tools/                 repo tooling (not deployed)
docs/runbooks/         how-tos for risky operations
```

Platforms are `macos`, `windows`, `linux`, `ios`, `ipados`, `android`, and `all` (cross-platform).
Naming rules for every kind of file are in [CONVENTIONS.md](CONVENTIONS.md).

## Making a change

1. **Find or add the artifact** under `platforms/<platform>/<kind>/`. Check the library first: it may
   already exist.
2. **Wire it into your fleet** with a `path:` entry in `fleets/<you>.yml`.
3. **Changing a shared file?** First check who else uses it:
   ```bash
   python3 tools/check-conventions.py --who-uses platforms/macos/policies/rosetta-installed.yml
   ```
4. **Check it locally:**
   ```bash
   python3 tools/check-conventions.py
   python3 .claude/skills/fleet-gitops/scripts/validate.py
   ```
   The first command checks naming and layout and scans for leaks. The second is Fleet's own static
   validator (YAML, paths, labels, osquery tables, Fleet-maintained app slugs, and profile structure).
   Optional extras are [flint](https://github.com/headmin/fleet-editor-extensions) (`flint dry-run`)
   and [contour](https://github.com/macadmins/contour) (`contour profile validate <file>.mobileconfig`).
5. **Branch, commit, and open a pull request from GitHub Desktop.** Use **Branch → New branch**,
   make small commits, read every file's diff first, then **Create Pull Request**.
6. **Merge when the `fleet-gitops` dry run is green.** In its log, look for any `would've deleted`
   line before you merge. If you touched someone else's fleet, wait for their review.

### Customer names: local denylist

You can't commit a list of customer names to a public repo. Instead, put the terms from your own
engagements in `.leakcheck.local` at the repo root, one per line. It's gitignored, and
`check-conventions.py` reads it automatically and fails on any match.

## Tools

| Tool | What it does |
|---|---|
| [`tools/check-conventions.py`](tools/check-conventions.py) | Checks naming, layout, and in-file names, and scans for leaks. Also answers "who uses this file?" |
| [`tools/update-gitops-skill.sh`](tools/update-gitops-skill.sh) | Refreshes `.claude/skills/fleet-gitops` from [fleetdm/fleet](https://github.com/fleetdm/fleet/tree/main/.claude/skills/fleet-gitops). The skill is vendored verbatim; don't edit it here. |
| [`tools/mdm-commands/`](tools/mdm-commands/README.md) | Sends an MDM command to hosts failing a policy, for fixes GitOps can't make. Example: `EnableRemoteDesktop` for the "macOS - Remote Management enabled" policy. Runs from the **MDM command on policy failure** workflow. It does nothing until its API token is set up, and defaults to a dry run. |

## CI setup

| Secret / variable | Used by | Notes |
|---|---|---|
| `FLEET_URL` (secret) | Both workflows | Server root, e.g. `https://fleet.example.com` |
| `FLEET_API_TOKEN` (secret) | GitOps apply | GitOps API-only user |
| `FLEET_MDM_SSO_METADATA` (secret) | GitOps apply | IdP metadata XML for end-user authentication |
| `MDM_COMMANDS_API_TOKEN` (secret in the `mdm-commands` environment) | MDM commands | Separate API-only user, Maintainer on target fleets only. Optional. |
| `MDM_COMMANDS_SCHEDULE` (variable) | MDM commands | `hourly`, `daily`, or `weekly`; unset means manual runs only |

## References

- [GitOps YAML reference](https://fleetdm.com/docs/configuration/yaml-files)
- [Fleet REST API](https://fleetdm.com/docs/rest-api/rest-api)
- [Fleet-maintained app catalog](https://github.com/fleetdm/fleet/tree/main/ee/maintained-apps)
- [osquery tables](https://fleetdm.com/tables)
- [Fleet solutions library](https://github.com/fleetdm/fleet/tree/main/docs/solutions): vetted CIS profiles, policies, and scripts to adapt
