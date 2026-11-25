"""Build an allowlisted source archive; never package local runtime secrets."""

import hashlib
import json
import tarfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    files = [ROOT / name for name in ("pyproject.toml", "uv.lock", "alembic.ini", ".dockerignore")]
    for source_directory, pattern in (("services", "*.py"), ("migrations", "*.py")):
        files.extend((ROOT / source_directory).rglob(pattern))
    files.extend(
        ROOT / "config" / name
        for name in (
            "agents.json",
            "exchange-calendar.json",
            "news-sources.json",
            "paper-execution.json",
        )
    )
    files.extend(
        ROOT / "hosting/oracle" / name
        for name in (
            "Dockerfile",
            "Dockerfile.bot",
            "compose.yaml",
            "compose.micro.yaml",
            "compose.bot-isolated.yaml",
            "swan-broker-login.service",
            "swan-broker-login.timer",
            "Caddyfile",
            "deploy.env.example",
            "runtime.env.example",
            "swan",
            "backup.sh",
            "README.md",
        )
    )
    directory = ROOT / ".local/release"
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / "swan-oracle-source.tar.gz"
    manifest = {}
    with tarfile.open(archive, "w:gz") as bundle:
        for path in sorted(set(files)):
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"Invalid release input: {path.relative_to(ROOT)}")
            name = path.relative_to(ROOT).as_posix()
            if "__pycache__" in path.parts:
                continue
            manifest[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            info = bundle.gettarinfo(str(path), arcname=name)
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = 0o755 if path.name in {"swan", "backup.sh"} else 0o644
            with path.open("rb") as source:
                bundle.addfile(info, source)
    record = {
        "created_at": datetime.now(UTC).isoformat(),
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "files": manifest,
    }
    (directory / "swan-oracle-source.manifest.json").write_text(
        json.dumps(record, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Source bundle: {archive} ({len(manifest)} files; runtime secrets excluded)")


if __name__ == "__main__":
    main()
