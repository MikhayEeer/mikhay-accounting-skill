# Maintainer tools

This directory is not part of the end-user skill.

`package_skill.py` builds a handoff archive for maintainers. ClawHub publish ignores this directory via `.clawhubignore`. The script also omits `tools/` and `package_skill.py` from the archive it writes.

```bash
python tools/package_skill.py
```

Output:

```text
dist/mikhay-accounting-skill.tar.gz
dist/mikhay-accounting-skill.zip
```

Do not point ledger users at this command. Ledger import, validation, and totals stay in `scripts/`.
