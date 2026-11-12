# Conventions

How we keep this repo clean while everyone on the CSE team works in it at once.
Short version: **`platforms/` and `labels/` are a shared library; your `fleets/<you>.yml`
is your sandbox; nothing customer-identifiable ever lands in git.**

Run `python3 tools/check-conventions.py` before you commit. It enforces most of what's below.

---

## 1. How the repo is shared

| Path | Who owns it | Rule |
|---|---|---|
| `fleets/<firstname>.yml` | That person | Your sandbox. Wire in whatever you want from the library. Don't edit someone else's file without telling them. |
| `fleets/workstations.yml` | Team | The "golden" fleet: only things that are validated and that you'd show a customer. |
| `platforms/**`, `labels/**` | Team | Shared library. Anything here can be referenced by any fleet. |
| `default.yml` | Team | Org-wide. Change it in its own commit, and say so in the team channel. |
| `tools/`, `CONVENTIONS.md`, `CLAUDE.md`, `.claude/` | Team | Repo tooling. |

**Before you change a shared file, find out who uses it**:

```bash
python3 tools/check-conventions.py --who-uses platforms/macos/configuration-profiles/chrome-settings.mobileconfig
```

When other fleets reference it, either tell those people or copy the file to a new
name for your experiment. Editing a profile that five fleets use re-pushes it to five
sets of test machines.

### Things that will bite you

- **CI runs `fleetctl gitops --delete-other-fleets`.** A fleet created in the Fleet UI is
  deleted on the next run. Every fleet must be a file in `fleets/`.
- **Never change a fleet's `name:` on its own.** GitOps treats a rename as delete plus create:
  the old fleet's hosts fall back to "Unassigned" and lose their profiles. To rename safely,
  follow [docs/runbooks/fleet-rename.md](docs/runbooks/fleet-rename.md).
- **Omitting a top-level key wipes that section.** Leave `policies: []` and similar keys
  in place; don't delete a key to "skip" it.
- **A label rename is delete plus recreate.** Its membership is empty until hosts check in again.
- **Never push to `main`; open a pull request.** Merging applies to the live instance. The PR's
  `fleet-gitops` dry run is the only server-side check, and [CODEOWNERS](.github/CODEOWNERS) asks
  the owner of any fleet you touch to review.
- **Commit small.** One concern per commit: "add Zoom PPPC profile", "wire Zoom into adam.yml".
  GitHub Desktop makes this easy. Review the diff file by file before you commit.

---

## 2. Layout

```
default.yml                      org settings + label registration
fleets/<name>.yml                one per fleet
labels/
  dynamic/<label>.yml            SQL query, recomputed on check-in
  manual/<label>.yml             hand-picked host list (label_membership_type: manual)
  host-vitals/<label>.yml        IdP group / department criteria
platforms/<platform>/<kind>/     platform = macos | windows | linux | ios | ipados | android | all
  policies/  reports/  scripts/  software/
  configuration-profiles/  declaration-profiles/  enrollment-profiles/  commands/
  managed-app-configurations/    (android)
platforms/all/icons/             software icons, <app>.png
tools/                           repo tooling (not deployed)
docs/runbooks/                   how-tos for risky operations (not deployed)
```

- Put a file under the **one** platform it runs on. Use `platforms/all/` only for
  things that genuinely span platforms (a cross-platform policy or report).
- Flat folders, no exceptions. No sub-folders inside a `<kind>/` folder. Group by name
  prefix instead (see below), so files sort together.

---

## 3. File names

All file names: **lowercase, kebab-case, ASCII, no spaces**. Name subject-first so related
files sort together.

| Kind | Pattern | Examples |
|---|---|---|
| Apple profile | `<subject>-<category>[-<detail>].mobileconfig` | `chrome-settings.mobileconfig`, `zoom-pppc.mobileconfig`, `firewall-stealth-mode.mobileconfig` |
| DDM declaration | `<subject>-<category>[-<detail>].json` | `softwareupdate-settings-defer-major.json`, `passcode-settings.json` |
| Windows profile | `<subject>-<detail>.xml` | `defender-realtime-protection.xml`, `bitlocker-settings.xml` |
| Android profile | `<subject>-<detail>.json` | `passcode-policy.json` |
| Enrollment profile | `<purpose>.dep.json` | `automatic-enrollment.dep.json` |
| Policy | `<subject>-<expected-state>.yml` | `filevault-enabled.yml`, `crowdstrike-falcon-running.yml`, `chrome-up-to-date.yml` |
| Report | `<subject>.yml` | `listening-ports.yml`, `chrome-extensions.yml` |
| Script | `<verb>-<object>.sh` / `.ps1` | `flush-dns-cache.sh`, `reset-onedrive.sh`, `install-rosetta.sh` |
| Software (custom package) | `<app>.yml`; its install/uninstall scripts go in the platform's `scripts/` as `install-<app>.sh` / `uninstall-<app>.sh` | `munki.yml` + `scripts/install-munki.sh` |
| Label | `<label-name-in-kebab>.yml` | `macos-hosts-with-zoom-installed.yml` |
| Icon | `<app>.png` in `platforms/all/icons/` | `globalprotect.png` |

**Profile category suffixes** (pick from the actual `PayloadType`, don't guess):
`settings` (managed preferences), `notifications`, `pppc` (TCC / Privacy Preferences),
`system-extension`, `content-filter`, `login-items`, `service-management`, `restrictions`,
`certificate`, `wifi`, `vpn`, `acme`, `scep`, `passcode`.

**Script verbs**: `install`, `uninstall`, `enable`, `disable`, `set`, `reset`, `fix`,
`remove`, `rename`, `collect`, `diagnose`, `flush`, `show`, `hide`.

---

## 4. Names inside files

These are what people see in the Fleet UI, so they matter more than file names.

### Policies

```yaml
- name: macOS - FileVault enabled              # <Platform> - <Subject> <expected state>
  platform: darwin
  description: Why this matters, in one or two sentences.
  resolution: What the end user (or admin) does to fix it. Plain language.
  query: SELECT 1 FROM ... ;                   # returns a row when the host PASSES
  critical: false
```

- Platform prefix: `macOS`, `Windows`, `Linux`, `iOS`, `iPadOS`, `Android`, or none
  when the policy spans platforms.
- State the **passing** condition: "FileVault enabled", not "FileVault disabled check".
- Always include `description` and `resolution`.
- One policy per file, unless it's a tightly related set (e.g. a patch policy per app is
  one per file; a CIS benchmark bundle may be one file).
- Any `run_script` / `install_software` automation must be safe to run repeatedly. How automations are
  wired and re-run is in the fleet-gitops skill's [policy reference](.claude/skills/fleet-gitops/references/queries.md).

### Reports

`name: <Platform> - <What is collected>`, for example `macOS - Listening ports`.
Always include `description`, `interval`, and `platform`. Set `observer_can_run: true`
unless the query returns sensitive data.

### Labels

- `name`: plain English for the host set, ASCII only: `macOS hosts with Zoom installed`,
  `Apple Silicon macOS hosts`, `Windows hosts on ARM`.
- Always include `description` and, for dynamic labels, `platform`.
- Labels are global (registered in `default.yml`), so names must be unique across the team.

### Apple configuration profiles

| Field | Value |
|---|---|
| Top-level `PayloadDisplayName` | `<Subject> - <Category>[ - <Detail>]`, e.g. `Google Chrome - Settings`, `Zoom - Privacy Preferences`, `Firewall - Stealth Mode` |
| Top-level `PayloadIdentifier` | `com.fleetdm.cse.<file-basename>` |
| Inner `PayloadIdentifier` | `com.fleetdm.cse.<file-basename>.<payload-short-name>` |
| `PayloadOrganization` | `Fleet CSE` |
| `PayloadUUID` | fresh `uuidgen` value; never copy a UUID from another org's profile |
| Inner `PayloadDisplayName` | name what it configures (`Chrome Managed Preferences`), never `Custom Settings` |

Fleet identifies a profile by its `PayloadDisplayName`, so it must be unique within a fleet.

Vendor-supplied profiles (an EDR vendor's official PPPC/system-extension profile) keep
the vendor's payload content. We change only the identity fields above.

### DDM declarations

`Identifier: com.fleetdm.cse.<file-basename>`. Fleet uses the file name as the
declaration's name, so the file name is the display name.

### Fleets

- Personal: file `fleets/<firstname>.yml`, `name: "<Firstname>'s ... Fleet"` (emoji allowed in fleet names).
- Shared: file `fleets/<purpose>.yml`, `name: "<Emoji> <Purpose>"`.
- Every fleet file keeps every top-level section (`agent_options`, `settings`, `controls`,
  `reports`, `policies`, `software`), even when empty.

---

## 5. Customer data: never in git

Everything here is visible to the whole team, and some of it reaches demos and screen-shares.
When you bring something over from a customer engagement, **sanitize it before the first
commit**. Git history is forever; a later "remove customer name" commit doesn't help.

Remove or replace:

| Remove | Replace with |
|---|---|
| Customer, subsidiary, product, or project names (including internal app nicknames and abbreviations) | A generic description (`internal-portal`, `Example Corp`), or drop the file |
| Domains, URLs, hostnames, server names, portal addresses, proxy/PAC URLs | `example.com`, `vpn.example.com`, `$FLEET_SECRET_<NAME>` |
| Email addresses and people's names | `it-support@example.com` (or nothing) |
| IP addresses and subnets | RFC 5737 docs ranges (`192.0.2.0/24`) or a variable |
| Wi-Fi SSIDs, VPN gateways, NAC/SCEP/ACME endpoints | `ExampleCorp-WiFi`, `$FLEET_SECRET_…` |
| Certificates, private keys, enroll secrets, API tokens | Don't commit. Use `$FLEET_SECRET_<NAME>` (stored in Fleet) or a CI variable |
| Apple Team IDs / code requirements of the **customer's own** apps | Drop the payload (vendor Team IDs like Zoom, Palo Alto, Microsoft are public and fine) |
| Serial numbers, UUIDs, hardware IDs, usernames from real hosts | Drop them |
| Ticket numbers, Jira keys, Slack links, internal wiki links | Drop them |
| Copied `PayloadUUID`s | Regenerate |
| Customer branding in end-user text (`resolution:`, script output, dialogs) | Neutral wording ("your IT team") |

If it only makes sense for that one customer, don't bring it over at all.

`tools/check-conventions.py` flags generic leak patterns: non-example emails and domains,
public IPs, private keys, and so on. Customer names are by definition not something we can
list in a public file, so put your own denylist (one term per line) in `.leakcheck.local`
at the repo root. It's gitignored, and the checker reads it automatically.

---

## 6. Before you commit

1. `python3 tools/check-conventions.py`: naming, structure, and leak patterns.
2. `python3 .claude/skills/fleet-gitops/scripts/validate.py`: Fleet's own static checks (YAML, paths, labels, osquery tables, FMA slugs, profile structure).
3. `fleetctl gitops -f default.yml $(for f in fleets/*.yml; do echo -f "$f"; done) --dry-run`: the same gate CI runs.
4. Review every file in GitHub Desktop's diff before you commit, keep commits small, and open a pull request.
   Merge once the `fleet-gitops` check is green.

Nothing runs these for you in CI except the server dry run on pull requests, so run them
yourself. [flint](https://github.com/headmin/fleet-editor-extensions) (`flint dry-run`) and
[contour](https://github.com/macadmins/contour) (`contour profile validate <file>`) are worth
installing locally too.

## 7. Fixes only an MDM command can make

GitOps can't send MDM commands. When a policy detects drift that only a command can fix
(for example, Remote Management turned off), pair them in `tools/mdm-commands/jobs.yml` and
store the command template in `platforms/<platform>/commands/`. See
[tools/mdm-commands/README.md](tools/mdm-commands/README.md).

The `/fleet-gitops` skill in `.claude/skills/` runs steps 2 and 3 for you.
