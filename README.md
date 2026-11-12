# Fleet CSE GitOps

The CSE team's test instance. Each of us has a sandbox fleet in `fleets/<name>.yml`; everything in
`platforms/` and `labels/` is a shared library.

**This repo is public.** Sanitize anything from a customer before committing
([CONVENTIONS.md § 5](CONVENTIONS.md#5-customer-data-never-in-git)).

## Workflow

1. Branch, change, open a PR. The `fleet-gitops` check dry-runs it against the live instance.
2. Merge when it's green. Merging to `main` applies it.

Before committing:

```bash
python3 tools/check-conventions.py
python3 .claude/skills/fleet-gitops/scripts/validate.py
```

## Gotchas

- A fleet that isn't in `fleets/` gets deleted on apply.
- Changing a fleet's `name:` deletes and recreates it. See [docs/runbooks/fleet-rename.md](docs/runbooks/fleet-rename.md).
- Before editing a shared file: `python3 tools/check-conventions.py --who-uses <path>`.

## More

- [CONVENTIONS.md](CONVENTIONS.md): layout, naming, sanitizing
- [tools/mdm-commands](tools/mdm-commands/README.md): MDM command on policy failure
- [GitOps YAML reference](https://fleetdm.com/docs/configuration/yaml-files)
