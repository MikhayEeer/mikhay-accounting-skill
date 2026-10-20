#!/usr/bin/env python3
"""Maintainer-only: publish this skill to ClawHub, SkillHub.cn, and ModelScope.

Credentials are read from one clearly named file per platform under
~/.secrets/publishing/ (see its README). Nothing is written into the
repository, and no tool-specific token file is created.

Examples:

    python tools/publish.py --dry-run
    python tools/publish.py --platform clawhub
    python tools/publish.py --platform skillhub --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PUBLISH_DIR = Path.home() / ".secrets" / "publishing"
SKILLHUB_KIT_URL = "https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/install/latest.tar.gz"
SOURCE_URL = "https://github.com/MikhayEeer/mikhay-accounting-skill"
DEFAULT_SLUG = "mikhay-accounting-skill"
DEFAULT_CATEGORIES = "finance,productivity"
DEFAULT_TOPICS = "bookkeeping,accounting,personal-finance,ledger,chinese"
MODELSCOPE_CATEGORY = "other"
MODELSCOPE_TAGS = ["accounting", "bookkeeping", "personal-finance", "chinese", "ledger"]


def read_frontmatter() -> dict[str, str]:
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise SystemExit("SKILL.md must start with a YAML frontmatter block")
    front = parts[1]
    fields: dict[str, str] = {}
    for key in ("name", "version", "displayName", "summary"):
        match = re.search(rf"^{key}:\s*(.+)$", front, re.MULTILINE)
        if not match:
            continue
        value = match.group(1).strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        fields[key] = value
    return fields


def is_placeholder(value: str) -> bool:
    text = value.strip()
    return text.startswith("<") and text.endswith(">")


def load_platform_config(platform: str) -> dict[str, str]:
    """Read ~/.secrets/publishing/<platform>.json, with environment overrides."""
    path = PUBLISH_DIR / f"{platform}.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise SystemExit(f"missing publish config: {path}\nSee {PUBLISH_DIR / 'README.md'}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise SystemExit(f"{path} must be a JSON object")
    return {str(key): str(value) for key, value in raw.items()}


def config_value(
    config: dict[str, str],
    key: str,
    env_names: list[str] | None = None,
    default: str = "",
) -> str:
    for env_name in env_names or []:
        value = os.environ.get(env_name, "").strip()
        if value and not is_placeholder(value):
            return value
    value = str(config.get(key, "")).strip()
    if value and not is_placeholder(value):
        return value
    return default


def require(config: dict[str, str], platform: str, keys: list[str]) -> None:
    missing = [key for key in keys if not config_value(config, key)]
    if missing:
        raise SystemExit(
            f"Missing {platform} config: " + ", ".join(missing)
            + f"\nFill {PUBLISH_DIR / (platform + '.json')}"
        )


def build_staging() -> tuple[Path, Path]:
    temp = Path(tempfile.mkdtemp(prefix="mikhay-publish-"))
    archive = temp / "skill.zip"
    # core.autocrlf=true would turn LF into CRLF inside the archive; some
    # registries (ModelScope) parse SKILL.md frontmatter line-by-line and fail
    # on CRLF, so archive from the index without EOL conversion.
    subprocess.run(
        [
            "git",
            "-C",
            str(ROOT),
            "-c",
            "core.autocrlf=false",
            "archive",
            "--format=zip",
            "-o",
            str(archive),
            "HEAD",
        ],
        check=True,
        capture_output=True,
    )
    target = temp / "skill"
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(target)
    archive.unlink()
    for name in ("tests", "tools", ".github"):
        shutil.rmtree(target / name, ignore_errors=True)
    # SkillHub.cn rejects dotfiles such as .clawhubignore; they are irrelevant
    # for the publish archive because the heavy directories are already gone.
    for name in (".clawhubignore", ".gitignore"):
        (target / name).unlink(missing_ok=True)
    return temp, target


def node_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    if extra:
        env.update(extra)
    node = shutil.which("node")
    if node:
        env["PATH"] = str(Path(node).parent) + os.pathsep + env.get("PATH", "")
    return env


def run_npx(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    npx = shutil.which("npx") or "npx"
    cmd = [npx, "-y", *args]
    if os.name == "nt":
        completed = subprocess.run(
            subprocess.list2cmdline(cmd),
            shell=True,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    else:
        completed = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    return completed


def report(name: str, completed: subprocess.CompletedProcess[str], dry_run: bool) -> bool:
    output = (completed.stdout or "").strip()
    error = (completed.stderr or "").strip()
    if output:
        print(output)
    if completed.returncode != 0:
        print(f"[{name}] failed with exit code {completed.returncode}", file=sys.stderr)
        if error:
            print(error, file=sys.stderr)
        return False
    if error:
        print(error)
    print(f"[{name}] {'validated' if dry_run else 'published'} successfully")
    return True


def publish_clawhub(
    staging: Path,
    *,
    slug: str,
    name: str,
    version: str,
    changelog: str,
    dry_run: bool,
) -> bool:
    config = load_platform_config("clawhub")
    if not dry_run:
        require(config, "clawhub", ["token"])
    token = config_value(config, "token", ["CLAWHUB_TOKEN"])
    owner = config_value(config, "owner", ["CLAWHUB_OWNER"])
    registry = config_value(config, "registry", ["CLAWHUB_REGISTRY"], "https://clawhub.ai")
    config_path: Path | None = None
    extra: dict[str, str] = {}
    if token:
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump({"registry": registry, "token": token}, handle)
        handle.write("\n")
        handle.close()
        config_path = Path(handle.name)
        extra["CLAWHUB_CONFIG_PATH"] = str(config_path)

    source_commit = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
    ).strip()
    args = [
        "clawhub@latest",
        "skill",
        "publish",
        str(staging),
        "--slug",
        slug,
        "--name",
        name,
        "--version",
        version,
        "--categories",
        DEFAULT_CATEGORIES,
        "--topics",
        DEFAULT_TOPICS,
        "--changelog",
        changelog,
        "--source-repo",
        SOURCE_URL,
        "--source-commit",
        source_commit,
    ]
    if owner:
        args.extend(["--owner", owner])
    if dry_run:
        args.append("--dry-run")
    try:
        completed = run_npx(args, node_env(extra))
    finally:
        if config_path is not None:
            config_path.unlink(missing_ok=True)
    return report("clawhub", completed, dry_run)


def ensure_skillhub_cli(temp_dir: Path) -> Path:
    """Download the skillhub.cn CLI kit and return skills_store_cli.py."""
    override = os.environ.get("SKILLHUB_CLI", "").strip()
    if override and Path(override).is_file():
        return Path(override)
    kit = temp_dir / "skillhub-kit.tar.gz"
    urllib.request.urlretrieve(SKILLHUB_KIT_URL, kit)
    target = temp_dir / "skillhub-cli"
    target.mkdir(parents=True, exist_ok=True)
    members = ("cli/skills_store_cli.py", "cli/skills_upgrade.py")
    with tarfile.open(kit, "r:gz") as archive:
        for member in archive.getmembers():
            if member.name in members and member.isfile():
                member.name = Path(member.name).name
                try:
                    archive.extract(member, target, filter="data")
                except TypeError:
                    archive.extract(member, target)
    cli = target / "skills_store_cli.py"
    if not cli.is_file():
        raise SystemExit(f"skillhub.cn CLI kit did not contain {members[0]}")
    return cli


def publish_skillhub(
    staging: Path,
    temp_dir: Path,
    *,
    changelog: str,
    dry_run: bool,
) -> bool:
    config = load_platform_config("skillhub")
    host = config_value(config, "host", ["SKILLHUB_HOST"], "https://api.skillhub.cn")
    token = config_value(config, "token", ["SKILLHUB_TOKEN"])
    if not dry_run:
        require(config, "skillhub", ["token"])
    # SkillHub.cn rejects extensionless files such as LICENSE (and dotfiles);
    # keep them in the repo but publish without them.
    skillhub_dir = temp_dir / "skillhub-package"
    if skillhub_dir.exists():
        shutil.rmtree(skillhub_dir)
    shutil.copytree(staging, skillhub_dir, ignore=shutil.ignore_patterns("LICENSE"))
    cli = ensure_skillhub_cli(temp_dir)
    env = dict(os.environ)
    env["SKILLHUB_SKIP_SELF_UPGRADE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    args = [
        sys.executable,
        str(cli),
        "publish",
        str(skillhub_dir),
        "--host",
        host,
        "--changelog",
        changelog,
        "--json",
    ]
    if token:
        args.extend(["--token", token])
    if dry_run:
        args.append("--dry-run")
    completed = subprocess.run(
        args,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return report("skillhub", completed, dry_run)


def build_modelscope_zip(staging: Path, dest: Path) -> Path:
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(staging).as_posix())
    size = dest.stat().st_size
    if size > 5 * 1024 * 1024:
        raise SystemExit(f"ModelScope skill zip is {size} bytes; the limit is 5 MB")
    return dest


def http_json(
    url: str,
    token: str,
    payload: dict[str, Any] | None = None,
    method: str = "POST",
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {url}: {detail}") from exc
    parsed = json.loads(body)
    if isinstance(parsed, dict) and parsed.get("success") is False:
        raise RuntimeError(f"{url}: {parsed.get('message') or parsed}")
    return parsed


def http_upload_skill_zip(url: str, token: str, zip_path: Path) -> dict[str, Any]:
    boundary = uuid.uuid4().hex
    chunk = zip_path.read_bytes()
    body = b""
    body += f'--{boundary}\r\nContent-Disposition: form-data; name="type"\r\n\r\nskill\r\n'.encode()
    body += (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{zip_path.name}"\r\n'
        "Content-Type: application/zip\r\n\r\n"
    ).encode()
    body += chunk + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {url}: {detail}") from exc
    if isinstance(payload, dict) and payload.get("success") is False:
        raise RuntimeError(f"{url}: {payload.get('message') or payload}")
    return payload


def publish_modelscope(
    staging: Path,
    *,
    frontmatter: dict[str, str],
    dry_run: bool,
) -> bool:
    config = load_platform_config("modelscope")
    endpoint = config_value(config, "endpoint", ["MODELSCOPE_ENDPOINT"], "https://modelscope.cn").rstrip("/")
    owner = config_value(config, "owner", ["MODELSCOPE_OWNER"])
    skill_name = config_value(config, "skill_name", ["MODELSCOPE_SKILL_NAME"], DEFAULT_SLUG)
    token = config_value(config, "token", ["MODELSCOPE_API_KEY", "MODELSCOPE_API_TOKEN"])
    zip_path = build_modelscope_zip(staging, staging.parent / f"{skill_name}.zip")
    description = frontmatter.get("summary") or frontmatter.get("description") or ""
    payload = {
        "owner": owner,
        "skill_name": skill_name,
        "display_name": frontmatter.get("displayName", skill_name),
        "description": description,
        "category": MODELSCOPE_CATEGORY,
        "license": "MIT License",
        "tags": MODELSCOPE_TAGS,
        "source_url": SOURCE_URL,
    }
    plan = dict(payload)
    plan["zip"] = str(zip_path)
    plan["zip_bytes"] = zip_path.stat().st_size
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if dry_run:
        print("[modelscope] validated package locally (no token needed for dry-run)")
        return True
    require(config, "modelscope", ["token"])
    if not owner:
        raise SystemExit(f"Missing modelscope config: owner. Fill {PUBLISH_DIR / 'modelscope.json'}")
    try:
        uploaded = http_upload_skill_zip(f"{endpoint}/openapi/v1/files/upload", token, zip_path)
        data = uploaded.get("data") if isinstance(uploaded, dict) else None
        file_id = (data or {}).get("id") or (data or {}).get("file_id")
        if not file_id:
            raise RuntimeError(f"upload response has no data.id: {uploaded}")
        create_payload = dict(payload, skill_file=file_id)
        try:
            created = http_json(f"{endpoint}/openapi/v1/skills", token, create_payload)
            print(json.dumps(created, ensure_ascii=False, indent=2))
        except RuntimeError as create_error:
            settings_url = (
                f"{endpoint}/openapi/v1/skills/"
                f"{urllib.parse.quote(owner, safe='')}/{urllib.parse.quote(skill_name, safe='')}/settings"
            )
            print(f"[modelscope] create failed, trying update: {create_error}", file=sys.stderr)
            updated = http_json(settings_url, token, {
                "display_name": payload["display_name"],
                "description": payload["description"],
                "skill_file": file_id,
                "tags": payload["tags"],
                "source_url": payload["source_url"],
            }, method="PATCH")
            print(json.dumps(updated, ensure_ascii=False, indent=2))
        print(f"[modelscope] published: {endpoint}/skills/@{owner}/{skill_name}")
        return True
    finally:
        zip_path.unlink(missing_ok=True)


def main() -> int:
    frontmatter = read_frontmatter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--platform",
        action="append",
        choices=["clawhub", "skillhub", "modelscope"],
        help="Publish only this platform. Can be repeated. Default: all three.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--staging", type=Path, help="Use an existing staging folder instead of git HEAD")
    parser.add_argument("--slug", default=DEFAULT_SLUG)
    parser.add_argument("--name", default=frontmatter.get("displayName", DEFAULT_SLUG))
    parser.add_argument("--version", default=frontmatter.get("version", "0.0.0"))
    parser.add_argument("--changelog", default=f"Release {frontmatter.get('version', '')}")
    args = parser.parse_args()
    platforms = args.platform or ["clawhub", "skillhub", "modelscope"]

    temp_dir: Path | None = None
    staging: Path
    if args.staging:
        staging = args.staging.resolve()
        if not (staging / "SKILL.md").is_file():
            raise SystemExit(f"staging folder has no SKILL.md: {staging}")
    else:
        temp_dir, staging = build_staging()

    work_dir = temp_dir or Path(tempfile.mkdtemp(prefix="mikhay-publish-work-"))
    results: dict[str, bool] = {}
    try:
        for platform in platforms:
            print(f"\n=== {platform} ===")
            if platform == "clawhub":
                results["clawhub"] = publish_clawhub(
                    staging,
                    slug=args.slug,
                    name=args.name,
                    version=args.version,
                    changelog=args.changelog,
                    dry_run=args.dry_run,
                )
            elif platform == "skillhub":
                results["skillhub"] = publish_skillhub(
                    staging,
                    work_dir,
                    changelog=args.changelog,
                    dry_run=args.dry_run,
                )
            else:
                results["modelscope"] = publish_modelscope(
                    staging,
                    frontmatter=frontmatter,
                    dry_run=args.dry_run,
                )
    finally:
        if temp_dir is not None:
            shutil.rmtree(temp_dir, ignore_errors=True)
        elif work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)

    print("\n=== summary ===")
    for name, ok in results.items():
        print(f"{name}: {'ok' if ok else 'FAILED'}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
