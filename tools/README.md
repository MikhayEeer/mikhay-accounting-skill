# Maintainer tools

This directory is not part of the end-user skill.

`package_skill.py` builds a handoff archive for maintainers. ClawHub publish ignores this directory via `.clawhubignore`. The script also omits `tools/` and `package_skill.py` from the archive it writes.

`publish.py` publishes the same folder to ClawHub, SkillHub, and ModelScope. Credentials come from `~/.secrets/secrets.json` or environment variables; the script does not store tokens in tool configs or the repository.

```bash
python tools/publish.py --dry-run
python tools/publish.py --platform clawhub
python tools/publish.py --platform skillhub
python tools/publish.py --platform modelscope
```

It publishes committed `HEAD` (via `git archive`), dropping `tests/`, `tools/`, and `.github/`. See `~/.secrets/README.md` for the key names.

```bash
python tools/package_skill.py
```

Output:

```text
dist/mikhay-accounting-skill.tar.gz
dist/mikhay-accounting-skill.zip
```

Do not point ledger users at this command. Ledger import, validation, and totals stay in `scripts/`.
