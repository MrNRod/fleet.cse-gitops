# Policy automation recovery

How to diagnose and recover a policy automation (`run_script` or `install_software`) that has stopped firing. This is the runbook for when something is already broken. The rules for *writing* a policy so it does not get into this state live in the `fleet-generic-add-policy` skill.

Every command here is either a mutation or a host-level read, so **an agent never runs any of it**. Hand it to the operator for their own admin terminal.

## Continuous is the default, so start there

Every policy with a `run_script` or `install_software` automation should set `continuous_automations_enabled: true` (Premium, Fleet 4.87.0+). Such a policy re-fires on every failing result, so it should not get stuck the way the rest of this runbook describes. When one of those keeps failing, the remediation is running and failing (or "succeeding" without fixing anything), not stuck: read the script output in the host's activity instead of resetting. Check the policy for the key first; everything below applies to a policy without it.

The failure mode that makes continuous necessary: on a freshly migrated Mac, orbit started osquery about 30 seconds before it enrolled itself. osquery's first policy results arrived while the host had no orbit node key, so Fleet skipped every automation while storing the failures, and nothing fired again.

## Why an automation stops firing (without continuous)

Fleet triggers `run_script` on a Pass→Fail *transition* or a first-ever failure, not on every check-in where the policy is still failing. It decides by diffing the incoming result against the host's stored `policy_membership.passes`: no stored row counts as a first run. A still-failing host with its row intact is neither newly failing nor newly passing, which is exactly why fail→fail never re-fires on its own.

So a script that no-ops on an unmet precondition (exits 0) burns its one shot, and the policy stays red with no further attempts.

`install_software` shares the same gate (the `newFailingSet` filter in `server/service/osquery.go`). Within a failing episode, a *failed* run is retried while the policy is still failing, capped at `MaxPolicyAutomationRetries = 3` attempts. Since Fleet 4.80.0 this applies to both a script that exits non-zero (`shouldRetryPolicyAutomationScript`) and a failed install (`shouldRetryPolicyAutomationSoftwareInstall`, which also stops after `MaxPolicyAutomationInstallAttempts = 10` failures per host and installer, a counter that expires 24h after the last failure). After that, nothing fires until the policy passes and fails again.

A script can also be skipped on a genuine pass→fail transition when the host has too many pending scripts, or when the same script is already pending.

Both automations are skipped, while the failure is still stored, when the host has no orbit node key yet (`hostOrbitNodeKey == nil` in `server/service/osquery.go`).

## Finding which host burned its shot

The policy details page has an automation-runs table with per-host outcomes, filtering, search, and a reset button. It is backed by:

```
GET /api/v1/fleet/policies/:id/automation_activities
```

Per-host activity entries also record whether an automation succeeded or failed.

## Resetting a policy (Fleet 4.89.0+)

```
POST /api/v1/fleet/policies/:policy_id/reset
```

Clears the policy's pass/fail results, counts and membership, so the next check-in counts as a first-ever failure and re-triggers the automation.

**`reset` is policy-wide, not per-host. Check the blast radius first.** The endpoint takes only a policy ID. It drops the membership rows for **every host on that policy** and clears its counts, so:

- the policy's results go blank until each host reports again, and
- *every* other host currently failing it re-fires its remediation at the same time.

On a fleet-wide policy that is a fleet-wide script run. Before recommending it, state how many hosts are currently failing the policy and confirm that re-running the script on all of them is safe.

The older `POST /api/v1/fleet/automations/reset` is a different, webhook-and-ticket-only endpoint and does not help with `run_script`.

## What continuous does, and what it does not fix

- It re-fires on every failing policy result while the policy keeps failing, and resets `attempt_number` to 0 on each re-fire, so the 3-attempt budget refreshes every time.
- A script already pending on the host is not queued again.
- A successful install is not re-queued within the policy update interval. A script has no such cooldown.
- Failed installs still stop after `MaxPolicyAutomationInstallAttempts = 10` per host and installer, until 24h pass without a new failure.

It recovers from transient faults and missed first attempts. **It does not fix a remediation that cannot make the policy pass**: a script that no-ops on an unmet precondition, or an install that never satisfies the query, just repeats every policy check. Anything that script does to the user (notifications, quitting apps, restart prompts) repeats with it. Fix the remediation instead.

## Recovery is not a substitute for design

If you are here often, the policy or its script breaks the automation rules in the fleet-gitops skill's [policy reference](../../.claude/skills/fleet-gitops/references/queries.md) (script listed in `controls.scripts`, `continuous_automations_enabled`, idempotent scripts). Fix the design rather than resetting on a schedule.
