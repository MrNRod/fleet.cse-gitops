#!/usr/bin/env python3
"""Check this repo against CONVENTIONS.md: layout, file names, in-file names, and leaks.

Usage (from the repo root):
  python3 tools/check-conventions.py                 # check everything
  python3 tools/check-conventions.py --who-uses PATH # which fleets reference a library file
  python3 tools/check-conventions.py --leaks-only    # only the customer-data scan

Exit code 1 when there is at least one FAIL. WARNs are advice.

Customer names can't live in a committed file, so put your own denylist (one term per
line, # for comments) in .leakcheck.local at the repo root. It's gitignored.
"""
import argparse
import fnmatch
import glob
import ipaddress
import os
import plistlib
import re
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("pyyaml is required: python3 -m pip install pyyaml")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

PLATFORMS = {"macos", "windows", "linux", "ios", "ipados", "android", "all"}
KINDS = {
    "policies": {".yml"},
    "reports": {".yml"},
    "scripts": {".sh", ".ps1", ".zsh", ".py"},
    "software": {".yml"},
    "configuration-profiles": {".mobileconfig", ".xml", ".json"},
    "declaration-profiles": {".json"},
    "enrollment-profiles": {".json"},
    "commands": {".plist", ".xml"},
    "managed-app-configurations": {".json"},
    "icons": {".png"},
}
KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
POLICY_PREFIX = {
    "darwin": "macOS", "windows": "Windows", "linux": "Linux",
    "ios": "iOS", "ipados": "iPadOS", "android": "Android", "chrome": "ChromeOS",
}
SCRIPT_VERBS = {
    "install", "uninstall", "enable", "disable", "set", "reset", "fix", "remove",
    "rename", "collect", "diagnose", "flush", "show", "hide", "configure", "update",
    "restart", "check", "create", "delete", "mitigate", "export", "sync", "run",
}
IGNORE_FILES = {".gitkeep", ".DS_Store", "README.md"}
# Files that predate CONVENTIONS.md and are live in someone's fleet. Fleet identifies scripts
# (and Windows/DDM profiles) by file name, so renaming them deletes and recreates them on hosts.
# Rename only with the fleet owner's OK, then drop the entry here.
LEGACY_NAMES = {
    "platforms/macos/scripts/fleetd_healthcheck_macos.sh",
    "platforms/linux/scripts/chrome-extensions.sh",
    "platforms/linux/scripts/firefox-extensions.sh",
}

# Leak patterns. Hosts in these domains are public and fine to mention.
SAFE_EMAIL_DOMAINS = {"example.com", "example.org", "example.net", "fleetdm.com", "apple.com", "users.noreply.github.com"}
PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----")
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
IPV4 = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?![\d.])")
SECRETS = [
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"), "GitHub token"),
    (re.compile(r"\bxox[abpr]-[A-Za-z0-9-]{10,}"), "Slack token"),
    (re.compile(r"hooks\.slack\.com/services/[A-Z0-9/]+", re.I), "Slack webhook URL"),
]
TEXT_EXT = {".yml", ".yaml", ".json", ".mobileconfig", ".xml", ".plist", ".sh", ".ps1",
            ".zsh", ".py", ".md", ".txt", ".toml"}

findings = []


def rel(p):
    return os.path.relpath(p, ROOT)


def add(level, path, msg):
    findings.append((level, rel(path) if os.path.isabs(path) else path, msg))


def git_files():
    """Tracked plus untracked-but-not-ignored files, so new work is checked before commit."""
    import subprocess
    try:
        out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
        return [os.path.join(ROOT, line) for line in out.splitlines() if line and os.path.isfile(os.path.join(ROOT, line))]
    except Exception:
        return [p for p in glob.glob(os.path.join(ROOT, "**", "*"), recursive=True)
                if os.path.isfile(p) and "/.git/" not in p]


def load_yaml(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except Exception as exc:
        add("FAIL", path, f"YAML doesn't parse: {exc}")
        return None


def stem(name):
    for suffix in (".dep.json", ".package.yml"):
        if name.endswith(suffix):
            return name[: -len(suffix)], suffix
    base, ext = os.path.splitext(name)
    return base, ext


# ---------------------------------------------------------------- layout and file names

def check_layout(files):
    for path in files:
        r = rel(path)
        parts = r.split(os.sep)
        name = parts[-1]
        if name in IGNORE_FILES:
            continue
        top = parts[0]
        if top == "platforms":
            if len(parts) < 4 or parts[1] not in PLATFORMS or parts[2] not in KINDS:
                add("FAIL", path, "must live at platforms/<platform>/<kind>/<file> (see CONVENTIONS.md section 2)")
                continue
            kind = parts[2]
            nested = parts[3:-1]
            if nested:
                add("FAIL", path, f"no sub-folders inside {kind}/; put scripts in platforms/{parts[1]}/scripts/")
            base, ext = stem(name)
            allowed = KINDS[kind] | ({".dep.json"} if kind == "enrollment-profiles" else set())
            if ext not in allowed:
                add("FAIL", path, f"unexpected file type {ext} in {kind}/")
            if r in LEGACY_NAMES:
                continue
            if not KEBAB.match(base):
                add("FAIL", path, "file name must be lowercase kebab-case ASCII, no spaces or underscores")
            if kind == "scripts":
                verb = base.split("-")[0]
                if verb not in SCRIPT_VERBS:
                    add("WARN", path, f"script names start with a verb (install-, set-, reset-, collect-...); got '{verb}-'")
        elif top == "labels":
            if len(parts) != 3 or parts[1] not in {"dynamic", "manual", "host-vitals"}:
                add("FAIL", path, "labels live in labels/dynamic/, labels/manual/, or labels/host-vitals/")
            elif not KEBAB.match(stem(name)[0]) or not name.endswith(".yml"):
                add("FAIL", path, "label file names are kebab-case .yml")
        elif top == "fleets":
            if len(parts) != 2 or not name.endswith(".yml") or not KEBAB.match(stem(name)[0]):
                add("FAIL", path, "fleet files are fleets/<kebab-name>.yml (no sub-folders)")


# ---------------------------------------------------------------- in-file names

def iter_items(doc):
    if isinstance(doc, list):
        for item in doc:
            if isinstance(item, dict):
                yield item
    elif isinstance(doc, dict):
        yield doc


def check_policies_and_reports(files):
    for path in files:
        r = rel(path)
        if not r.endswith(".yml"):
            continue
        is_policy = "/policies/" in r and r.startswith("platforms/")
        is_report = "/reports/" in r and r.startswith("platforms/")
        if not (is_policy or is_report):
            continue
        doc = load_yaml(path)
        for item in iter_items(doc):
            name = str(item.get("name", ""))
            if not name:
                add("FAIL", path, "item has no name")
                continue
            if not name.isascii() and is_report:
                add("FAIL", path, f"report name must be ASCII: {name!r}")
            plats = [p.strip() for p in str(item.get("platform", "")).split(",") if p.strip()]
            if len(plats) == 1 and plats[0] in POLICY_PREFIX:
                want = POLICY_PREFIX[plats[0]] + " - "
                if not name.startswith(want):
                    add("WARN", path, f"name should start with '{want}': {name!r}")
            if is_policy:
                for key in ("description", "resolution"):
                    if not item.get(key):
                        add("WARN", path, f"policy {name!r} has no {key}")
            if is_report:
                for key in ("description", "interval"):
                    if key not in item:
                        add("WARN", path, f"report {name!r} has no {key}")


def check_labels(files):
    seen = {}
    for path in files:
        r = rel(path)
        if not (r.startswith("labels/") and r.endswith(".yml")):
            continue
        for item in iter_items(load_yaml(path)):
            name = str(item.get("name", ""))
            if not name.isascii():
                add("FAIL", path, f"label name must be ASCII: {name!r}")
            if name in seen:
                add("FAIL", path, f"duplicate label name {name!r} (also in {seen[name]})")
            seen[name] = r
            if not item.get("description"):
                add("WARN", path, f"label {name!r} has no description")
            mtype = item.get("label_membership_type", "dynamic")
            folder = r.split("/")[1]
            expected = {"dynamic": "dynamic", "manual": "manual", "host-vitals": "host_vitals"}[folder]
            if mtype != expected:
                add("FAIL", path, f"label {name!r} is {mtype} but lives in labels/{folder}/")
            if mtype == "dynamic" and not item.get("platform"):
                add("WARN", path, f"dynamic label {name!r} has no platform; it will run on every host")


def check_profiles(files):
    uuids = {}
    for path in files:
        r = rel(path)
        if not r.endswith(".mobileconfig"):
            continue
        try:
            with open(path, "rb") as fh:
                pl = plistlib.load(fh)
        except Exception as exc:
            add("FAIL", path, f"profile doesn't parse as a plist: {exc}")
            continue
        base = stem(os.path.basename(r))[0]
        ident = str(pl.get("PayloadIdentifier", ""))
        if not ident.startswith("com.fleetdm.cse."):
            add("WARN", path, f"PayloadIdentifier should be com.fleetdm.cse.{base} (got {ident!r})")
        if pl.get("PayloadOrganization") not in ("Fleet CSE",):
            add("WARN", path, "PayloadOrganization should be 'Fleet CSE'")
        payloads = [pl] + [p for p in pl.get("PayloadContent", []) if isinstance(p, dict)]
        for p in payloads:
            u = str(p.get("PayloadUUID", "")).upper()
            if u:
                if u in uuids and uuids[u] != r:
                    add("FAIL", path, f"PayloadUUID {u} is also used in {uuids[u]}; run uuidgen")
                uuids[u] = r
        for p in payloads[1:]:
            if str(p.get("PayloadDisplayName", "")).strip() in ("", "Custom Settings", "Settings"):
                add("WARN", path, f"inner payload {p.get('PayloadType')} needs a descriptive PayloadDisplayName")


def check_fleets(files):
    names = {}
    for path in files:
        r = rel(path)
        if not (r.startswith("fleets/") and r.endswith(".yml")):
            continue
        doc = load_yaml(path) or {}
        name = doc.get("name")
        if name in names:
            add("FAIL", path, f"fleet name {name!r} also used by {names[name]}")
        names[name] = r
        if r != "fleets/unassigned.yml":
            for key in ("agent_options", "controls", "policies", "reports", "software", "settings"):
                if key not in doc:
                    add("WARN", path, f"top-level '{key}' is missing; omitting a key clears that section in Fleet")


# ---------------------------------------------------------------- leaks

def load_denylist():
    terms = []
    path = os.path.join(ROOT, ".leakcheck.local")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.split("#", 1)[0].strip()
                if line:
                    terms.append(line)
    return terms


def ip_is_leak(s):
    try:
        ip = ipaddress.ip_address(s)
    except ValueError:
        return False
    if any(ip in ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")):
        return False
    if ip.is_loopback or ip.is_unspecified or ip.is_multicast or ip.is_link_local:
        return False
    if str(ip) in ("255.255.255.255", "1.1.1.1", "1.0.0.1", "8.8.8.8", "8.8.4.4", "9.9.9.9") or s.startswith("0."):
        return False  # public resolvers are fine
    if ip.is_private:
        return True  # private ranges reveal a customer's network layout
    # Benchmark control IDs (CIS 6.1.4.1) look like IPs; real public IPs almost always have a big octet.
    return max(int(o) for o in s.split(".")) >= 20


def check_leaks(files):
    deny = load_denylist()
    deny_res = [(t, re.compile(r"(?<![A-Za-z0-9])" + re.escape(t) + r"(?![A-Za-z0-9])", re.I)) for t in deny]
    for path in files:
        r = rel(path)
        if r == ".leakcheck.local" or r.startswith(".claude/skills/fleet-gitops/"):
            continue  # upstream skill is vendored verbatim
        base_lower = r.lower()
        for t, rx in deny_res:
            if rx.search(base_lower):
                add("FAIL", path, f"file path contains denylisted term {t!r}")
        if os.path.splitext(r)[1].lower() not in TEXT_EXT:
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for t, rx in deny_res:
                if rx.search(line):
                    add("FAIL", path, f"line {lineno}: denylisted term {t!r}")
            if PRIVATE_KEY.search(line):
                add("FAIL", path, f"line {lineno}: private key material")
            for rx, what in SECRETS:
                if rx.search(line):
                    add("FAIL", path, f"line {lineno}: looks like a {what}")
            for m in EMAIL.finditer(line):
                dom = m.group(1).lower()
                if not any(dom == d or dom.endswith("." + d) for d in SAFE_EMAIL_DOMAINS):
                    add("WARN", path, f"line {lineno}: email address {m.group(0)!r}; use @example.com")
            for m in IPV4.finditer(line):
                if ip_is_leak(m.group(1)):
                    add("WARN", path, f"line {lineno}: IP address {m.group(1)}; use 192.0.2.x or a variable")
        if "<key>PayloadContent</key>" in text and re.search(r"<data>\s*MII", text):
            add("WARN", path, "embedded certificate data; make sure it's a public CA, not a customer's")


# ---------------------------------------------------------------- who uses

def who_uses(target):
    target_abs = os.path.abspath(target)
    hits = []
    configs = [os.path.join(ROOT, "default.yml")] + sorted(glob.glob(os.path.join(ROOT, "fleets", "*.yml")))
    configs += sorted(glob.glob(os.path.join(ROOT, "platforms", "*", "policies", "*.yml")))

    def walk(node, base, cfg):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("path", "paths", "package_path", "hash_sha256") and isinstance(v, str):
                    pattern = os.path.normpath(os.path.join(base, v))
                    if fnmatch.fnmatch(target_abs, pattern) or pattern == target_abs:
                        hits.append((rel(cfg), v))
                else:
                    walk(v, base, cfg)
        elif isinstance(node, list):
            for v in node:
                walk(v, base, cfg)

    for cfg in configs:
        try:
            with open(cfg, encoding="utf-8") as fh:
                doc = yaml.safe_load(fh)
        except Exception:
            continue
        walk(doc, os.path.dirname(cfg), cfg)
    if not hits:
        print(f"{rel(target_abs)}: not referenced by any fleet, default.yml, or policy")
        return
    print(f"{rel(target_abs)} is referenced by:")
    for cfg, v in hits:
        print(f"  {cfg}  ({v})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--who-uses", metavar="PATH")
    ap.add_argument("--leaks-only", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="only print FAILs")
    args = ap.parse_args()

    if args.who_uses:
        who_uses(args.who_uses)
        return 0

    files = git_files()
    if not args.leaks_only:
        check_layout(files)
        check_policies_and_reports(files)
        check_labels(files)
        check_profiles(files)
        check_fleets(files)
    check_leaks(files)

    fails = [f for f in findings if f[0] == "FAIL"]
    warns = [f for f in findings if f[0] == "WARN"]
    for level, path, msg in sorted(findings, key=lambda f: (f[0] != "FAIL", f[1])):
        if args.quiet and level != "FAIL":
            continue
        print(f"{level} {path}: {msg}")
    deny = "with" if os.path.exists(os.path.join(ROOT, ".leakcheck.local")) else "WITHOUT"
    print(f"\nChecked {len(files)} files ({deny} a .leakcheck.local denylist): {len(fails)} FAIL, {len(warns)} WARN")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
