# MDM command on policy failure

Some drift can only be fixed by an MDM command. Remote Management is the classic case: since macOS 12.1,
nothing on the host can turn it on, only Apple's `EnableRemoteDesktop` command. GitOps can't declare
commands, so this pairs a **policy** (detects) with a **command** (fixes), and runs the command
on a schedule from GitHub Actions.

```
policy "macOS - Remote Management enabled"   (in any fleet that includes it)
   │ failing
   ▼
send.py   (scheduled workflow, or by hand)
   │ one command per host, fresh CommandUUID each
   │ skipped if that host already has the same command pending
   ▼
host acknowledges ──► refetch requested ──► policy re-runs at next check-in
   └─ still failing next run? it's sent again
```

- **Acknowledged** means the OS accepted the command. The policy passing is the proof.
- **An offline host** keeps its one queued command until it checks in. Later runs see it pending and skip it.

## Add a job

1. Write or reuse a policy under `platforms/<platform>/policies/` that fails when the fix is needed.
2. Put the command in `platforms/<platform>/commands/<request-type-in-kebab>.plist`. Any `CommandUUID` value
   works; it's replaced at send time.
3. Add an entry to [`jobs.yml`](jobs.yml) with the policy's exact `name:`.
4. Add the policy to the fleets that should get the fix. A job acts on every fleet that includes its policy,
   unless you list `fleets:`.
5. The API user needs Maintainer on those fleets (see below). Then dry-run it from Actions.

## Run it

**From Actions:** go to **MDM command on policy failure**, then **Run workflow**. Optionally pick a job; `mode` is
`failing` or `all`. It defaults to a dry run; untick `dry_run` to send.

**On a schedule:** set the repository variable `MDM_COMMANDS_SCHEDULE` to `hourly`, `daily` (recommended)
or `weekly`. It's found under **Settings → Secrets and variables → Actions → Variables**. Unset means
manual runs only.

**Locally:**

```bash
export FLEET_URL="https://fleet.example.com"
export FLEET_API_TOKEN="..."   # the API-only user's token, never the GitOps one
python3 tools/mdm-commands/send.py --list
python3 tools/mdm-commands/send.py --dry-run
python3 tools/mdm-commands/send.py --job "Enable Remote Desktop" --wait 300
```

Exit codes: `0` ok, `1` config or API error, `2` a host returned an error, `3` some hosts still pending.

## One-time setup

1. **In Fleet:** go to **Settings > Users > Create user > API-only**, named `MDM commands (GitHub Actions)`.
   Give it the **Maintainer** role on the target fleets only, never global. Under **API access**, set it to
   **Specific API endpoints**:

   | Endpoint | Used for |
   |---|---|
   | List fleets: `GET /api/v1/fleet/fleets` | Map fleet names to IDs. Don't pick *Create a fleet*, which shares the path. |
   | List fleet-level policies: `GET /api/v1/fleet/fleets/:id/policies` | Find the job's policy |
   | List hosts: `GET /api/v1/fleet/hosts` | Hosts failing the policy |
   | List MDM commands: `GET /api/v1/fleet/commands` | Skip hosts with one already pending |
   | Run MDM command: `POST /api/v1/fleet/commands/run` | Send |
   | Get MDM command results: `GET /api/v1/fleet/commands/results` | Per-host result |
   | Refetch host: `POST /api/v1/fleet/hosts/:id/refetch` | Re-run the policy sooner |

2. **In GitHub:** go to **Settings → Environments** and create `mdm-commands`. Limit its deployment branches
   to `main` and add **no** required reviewers. Add the environment secret `MDM_COMMANDS_API_TOKEN`. The
   workflow also reads the repository secret `FLEET_URL`, which the GitOps workflow already uses.
