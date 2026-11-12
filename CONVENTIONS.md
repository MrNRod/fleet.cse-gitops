# Conventions

## 1. Sharing

- `fleets/<you>.yml` is your sandbox. Don't edit someone else's without asking.
- `platforms/` and `labels/` are shared. Before changing a shared file, run
  `python3 tools/check-conventions.py --who-uses <path>`.
- `default.yml` affects every fleet. Change it in its own PR.
- PRs only, never push to `main`. Keep commits small.

## 2. Layout

```
fleets/<name>.yml
labels/{dynamic,manual,host-vitals}/<label>.yml
platforms/<macos|windows|linux|ios|ipados|android|all>/<kind>/<file>
tools/   docs/runbooks/
```

Flat folders, no sub-folders. Kinds: `policies`, `reports`, `scripts`, `software`,
`configuration-profiles`, `declaration-profiles`, `enrollment-profiles`, `commands`.

## 3. File names

Lowercase kebab-case, subject first.

| Kind | Pattern | Example |
|---|---|---|
| Apple profile | `<subject>-<category>.mobileconfig` | `zoom-pppc-system-extension.mobileconfig` |
| DDM / Windows / Android | `<subject>-<detail>.json` / `.xml` | `softwareupdate-settings-automatic.json` |
| Policy | `<subject>-<expected-state>.yml` | `filevault-key-escrowed.yml` |
| Report | `<subject>.yml` | `listening-ports.yml` |
| Script | `<verb>-<object>.sh` | `flush-dns-cache.sh` |
| Software | `<app>.yml`; scripts in `scripts/install-<app>.sh` | |
| Label | `<label-name>.yml` | `macos-27-or-later-hosts.yml` |

## 4. Names inside files

- **Policies:** `<Platform> - <Subject> <passing state>`, e.g. `macOS - FileVault key escrowed`.
  Always set `description` and `resolution`. Automations must be safe to re-run; see the
  fleet-gitops skill's [policy reference](.claude/skills/fleet-gitops/references/queries.md).
- **Reports:** `<Platform> - <What>`, with `description` and `interval`.
- **Labels:** plain English, ASCII, unique, e.g. `macOS 27 or later hosts`.
- **Apple profiles:**

  | Field | Value |
  |---|---|
  | `PayloadDisplayName` | `<Subject> - <Category>` |
  | `PayloadIdentifier` | `com.fleetdm.cse.<file-name>` |
  | `PayloadOrganization` | `Fleet CSE` |
  | `PayloadUUID` | fresh from `uuidgen` |

## 5. Customer data: never in git

This repo is public. Before bringing anything over from a customer, remove:

- customer names, domains, hostnames, emails, and people
- IPs, SSIDs, and tenant or org IDs
- serials, ticket numbers, and the customer's own Team IDs
- certificates, keys, and tokens

Use `example.com` and `$FLEET_SECRET_<NAME>` instead.

`check-conventions.py` flags anything that looks like customer data. Read each flag before you commit.

## 6. Before you commit

```bash
python3 tools/check-conventions.py
python3 .claude/skills/fleet-gitops/scripts/validate.py
```

Optional: `flint dry-run`, `contour profile validate <file>`.

## 7. MDM commands

For fixes only an MDM command can make, see [tools/mdm-commands](tools/mdm-commands/README.md).
