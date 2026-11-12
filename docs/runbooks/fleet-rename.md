# Renaming a fleet

How to rename a fleet without deleting it. Proven on several production renames: fleet IDs, hosts and VPP assignments all survived.

## Why a plain YAML rename is destructive

Fleet GitOps matches a fleet by its `name:`, not by an ID or the filename. CI applies with `--delete-other-fleets`, so changing `name:` in YAML alone makes the apply:

- create a new fleet with the new name (new ID), and
- delete the old fleet, dropping its hosts to Unassigned. They lose every fleet-scoped profile, policy, software assignment and Apple Business (ADE) default assignment until moved back.

Renaming only the **file** (`fleets/<name>.yml`) is harmless: CI globs `fleets/*.yml` and Fleet never sees the filename.

## Procedure

1. **Open the PR with the YAML rename, and don't merge it.** Include the dependent changes listed below in the same PR.
2. **Run the dry run.** Expect `[!] would've deleted team <old name>`. That is the destructive path you are about to defuse.
3. **The operator renames the fleet in the Fleet UI** to exactly the new `name:`. This is a server mutation, so an agent never does it.
4. **Run the dry run again.** These lines must be gone:
   - `would've deleted team <old name>`
   - `would've applied DDM assets for new fleet <new name>`

   If either remains, stop. (`would've applied MDM profiles for new fleet` prints for every fleet and means nothing.)
5. **Merge promptly.** Between the UI rename and the merge, the server holds a fleet that no YAML on `main` names, so **any** apply deletes it: another merge, a manual pipeline run, or a scheduled apply. Freeze other merges and finish before the next scheduled run.
6. **Watch the apply after the merge**, then confirm the fleet ID and host count are unchanged (`fleetctl get fleets`) and a dry run against `main` is clean.

**CI green is not a safety gate here.** The `would've deleted team` line is informational and the dry run still exits 0, so a destructive rename passes CI. A person has to read the line.

## What else changes with the name

In the same PR:

- **`default.yml`**: `mdm.apple_business.*_fleet` (`macos_fleet`, `ios_fleet`, `ipados_fleet`) and every `volume_purchasing_program[].fleets` entry naming the fleet. Leave VPP entries in their current position; reordering is noise.
- **Docs that name or link the fleet or its file.** These break silently.
- **Repo tooling that hardcodes the fleet file path or name**: grep `tools/` and `.github/` for both before renaming.

Leave alone:

- **Enroll secret variable names.** CI secrets can't be renamed in place, and a YAML reference to a secret that doesn't exist yet breaks enrollment with an empty value. Renaming one is a separate, sequenced change.

## Pairs and kiosks

Rename a production fleet and its maintenance twin (for example a kiosk fleet and its "Maintenance Mode" fleet) together, in one PR, and not while a device is mid-transfer between them. Rename fleets with unattended kiosks when someone can reach the devices, since a kiosk that drops to Unassigned needs a physical visit to recover.

## Not yet verified

Whether Apple Business (ADE) default assignment follows a renamed `ios_fleet` / `ipados_fleet` / `macos_fleet` for the next enrolling device. Check the first enrollment after renaming a default fleet.
