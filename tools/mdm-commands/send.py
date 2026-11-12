#!/usr/bin/env python3
"""Send an MDM command to hosts that fail a policy. GitOps can't declare MDM commands, so this
is the enforcement half of a "policy detects it, MDM command fixes it" pair.

Jobs live in tools/mdm-commands/jobs.yml. Each job names a policy (by its exact `name:`) and a
command plist template under platforms/<platform>/commands/. For each job, the runner:

  1. finds every fleet the token can see that has a policy with that name (or only the fleets
     the job lists),
  2. lists the MDM-enrolled hosts failing it (or every enrolled host in those fleets with --all),
  3. skips hosts that already have the same command type pending, so an offline host gets one
     queued command no matter how often this runs,
  4. sends the command one host at a time, each with a fresh CommandUUID (Fleet rejects a reused
     UUID, and a single non-MDM host in a batch request fails the whole batch),
  5. optionally waits for results, then asks acknowledged hosts to refetch so the policy re-runs.

"Acknowledged" means the OS accepted the command; the policy passing is the real proof.

Environment:
  FLEET_URL        server root, e.g. https://fleet.example.com (no /api path)
  FLEET_API_TOKEN  API-only user, maintainer on the target fleets. Not the GitOps token.

Usage:
  send.py [--job NAME]... [--all] [--wait SECONDS] [--dry-run]

Exit codes: 0 ok or nothing to do; 1 config/API error; 2 a host returned an error;
            3 some hosts still pending when --wait ran out (normal for offline hosts).
"""
import argparse
import base64
import json
import os
import plistlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("pyyaml is required: python3 -m pip install pyyaml")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
JOBS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs.yml")
PLATFORMS = {"darwin", "ios", "ipados"}


class FleetError(Exception):
    pass


class Fleet:
    def __init__(self, url, token):
        base = url.rstrip("/")
        if "/api" in base or not base.startswith(("http://", "https://")):
            raise FleetError(f"FLEET_URL must be the server root (https://host), got {base!r}")
        self.api = base + "/api/v1/fleet"
        self.token = token

    def call(self, method, route, body=None, ok404=False):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.api + route, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode() or "{}"
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and ok404:
                return None
            detail = exc.read().decode(errors="replace")[:300]
            if exc.code in (401, 403):
                raise FleetError(f"{method} {route}: HTTP {exc.code}. Check the token and its endpoint scope.")
            raise FleetError(f"{method} {route}: HTTP {exc.code}: {detail}")
        except urllib.error.URLError as exc:
            raise FleetError(f"{method} {route}: {exc.reason}")
        if raw.lstrip()[:1] not in ("{", "["):
            # An SSO gateway or a wrong URL answers 200 with HTML.
            raise FleetError(f"{method} {route}: response isn't JSON; is FLEET_URL the Fleet server root?")
        return json.loads(raw)

    def get(self, route, **params):
        q = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        return self.call("GET", route + ("?" + q if q else ""))

    def fleets(self):
        # Fleet 4.x+ serves /fleets; older servers only /teams. Same shape.
        res = self.call("GET", "/fleets?per_page=500", ok404=True)
        if res is not None:
            return res.get("fleets", []), "fleet_id"
        return self.get("/teams", per_page=500).get("teams", []), "team_id"

    def fleet_policies(self, fid):
        res = self.call("GET", f"/fleets/{fid}/policies?per_page=500", ok404=True)
        if res is None:
            res = self.get(f"/teams/{fid}/policies", per_page=500)
        return res.get("policies") or []

    def hosts(self, id_key, fid, policy_id=None):
        page = 0
        while True:
            params = {id_key: fid, "per_page": 100, "page": page, "order_key": "id"}
            if policy_id is not None:
                params.update(policy_id=policy_id, policy_response="failing")
            batch = self.get("/hosts", **params).get("hosts", [])
            yield from batch
            if len(batch) < 100:
                return
            page += 1


def load_jobs(selected):
    with open(JOBS_FILE, encoding="utf-8") as fh:
        jobs = yaml.safe_load(fh) or []
    for job in jobs:
        for key in ("name", "policy", "command"):
            if not job.get(key):
                raise FleetError(f"{JOBS_FILE}: job {job!r} is missing '{key}'")
    if selected:
        unknown = set(selected) - {j["name"] for j in jobs}
        if unknown:
            raise FleetError(f"no job named {sorted(unknown)} in {JOBS_FILE}")
        jobs = [j for j in jobs if j["name"] in selected]
    return [j for j in jobs if j.get("enabled", True) or j["name"] in selected]


def command_b64(template_path, command_uuid):
    with open(template_path, "rb") as fh:
        pl = plistlib.load(fh)
    if "Command" not in pl or "RequestType" not in pl["Command"]:
        raise FleetError(f"{template_path}: not an MDM command plist (needs Command.RequestType)")
    pl["CommandUUID"] = command_uuid
    return base64.b64encode(plistlib.dumps(pl, fmt=plistlib.FMT_XML)).decode(), pl["Command"]["RequestType"]


def run_job(fleet, job, args):
    template = os.path.join(ROOT, job["command"])
    _, request_type = command_b64(template, "00000000-0000-0000-0000-000000000000")
    platforms = set(job.get("platforms", ["darwin"])) & PLATFORMS
    only = set(job.get("fleets") or [])
    print(f"\n== {job['name']}: '{request_type}' to hosts failing '{job['policy']}'")

    fleets, id_key = fleet.fleets()
    targets, config_err = [], False
    for f in fleets:
        if only and f["name"] not in only:
            continue
        pol = next((p for p in fleet.fleet_policies(f["id"]) if p.get("name") == job["policy"]), None)
        if pol is None:
            if only:
                print(f"  {f['name']}: has no policy named '{job['policy']}'", file=sys.stderr)
                config_err = True
            continue
        hosts = fleet.hosts(id_key, f["id"], None if args.all else pol["id"])
        picked = [h for h in hosts if h.get("platform") in platforms
                  and str((h.get("mdm") or {}).get("enrollment_status") or "").startswith("On")]
        print(f"  {f['name']}: {len(picked)} host(s) {'enrolled' if args.all else 'failing'}")
        targets += picked
    missing = only - {f["name"] for f in fleets}
    for name in sorted(missing):
        print(f"  fleet '{name}' not found, or the token isn't a maintainer on it", file=sys.stderr)
        config_err = True

    if not targets:
        print("  nothing to send")
        return 1 if config_err else 0

    sent = {}
    for h in targets:
        label = f"{(h.get('display_name') or h.get('hostname') or h['uuid'])[:32]:<32} {h.get('status', '?'):<8}"
        pending = fleet.get("/commands", host_identifier=h["uuid"], request_type=request_type,
                            command_status="pending", per_page=1)
        if pending.get("count") or pending.get("results"):
            print(f"  skipped     {label} already queued")
            continue
        cuuid = str(uuid.uuid4()).upper()
        if args.dry_run:
            print(f"  would send  {label} host {h['id']}")
            continue
        b64, _ = command_b64(template, cuuid)
        try:
            fleet.call("POST", "/commands/run", {"command": b64, "host_uuids": [h["uuid"]]})
        except FleetError as exc:
            print(f"  NOT SENT    {label} {exc}", file=sys.stderr)
            continue
        sent[h["id"]] = (cuuid, label)
        print(f"  sent        {label} command {cuuid}")

    if args.dry_run or not sent:
        return 1 if config_err else 0

    status = {hid: "Pending" for hid in sent}
    deadline = time.monotonic() + args.wait
    while args.wait:
        for hid, (cuuid, _) in sent.items():
            if status[hid] not in ("Pending", "NotNow"):
                continue
            res = (fleet.get("/commands/results", command_uuid=cuuid).get("results") or [{}])[0]
            status[hid] = res.get("status") or "Pending"
            if status[hid] == "Acknowledged":
                fleet.call("POST", f"/hosts/{hid}/refetch")
        if all(s not in ("Pending", "NotNow") for s in status.values()) or time.monotonic() >= deadline:
            break
        time.sleep(10)

    rc = 0
    for hid, (cuuid, label) in sent.items():
        print(f"  {status[hid]:<12} {label} {cuuid}")
        if status[hid] in ("Error", "CommandFormatError"):
            rc = 2
        elif status[hid] != "Acknowledged" and args.wait and rc == 0:
            rc = 3
    return rc or (1 if config_err else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--job", action="append", default=[], help="run only this job (repeatable); runs disabled jobs too")
    ap.add_argument("--all", action="store_true", help="every MDM-enrolled host in the fleets, not just failing ones")
    ap.add_argument("--wait", type=int, default=120, help="seconds to wait for results (0 = don't wait)")
    ap.add_argument("--dry-run", action="store_true", help="list hosts; send nothing")
    ap.add_argument("--list", action="store_true", help="list jobs and exit (no Fleet access needed)")
    args = ap.parse_args()

    try:
        jobs = load_jobs(args.job)
        if args.list:
            for j in jobs:
                print(f"{j['name']}: '{j['policy']}' -> {j['command']}")
            return 0
        url, token = os.environ.get("FLEET_URL"), os.environ.get("FLEET_API_TOKEN")
        if not url or not token:
            raise FleetError("set FLEET_URL and FLEET_API_TOKEN")
        fleet = Fleet(url, token)
        codes = {run_job(fleet, job, args) for job in jobs}
        # Most severe first: config/API error, host error, still pending.
        return next((c for c in (1, 2, 3) if c in codes), 0)
    except FleetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
