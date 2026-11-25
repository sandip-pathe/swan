"""Fetch a consistent Oracle SQLite backup and encrypt it locally using the SSH key.

Run with --key PATH; no credentials, database rows or plaintext backup are printed.
Keep that SSH key: losing it also loses access to these encrypted backups.
"""

import argparse
import os
import sqlite3
import subprocess
import tempfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--host", default="ubuntu@137.23.62.124")
    parser.add_argument("--directory", type=Path, default=Path(".local/backups"))
    args = parser.parse_args()
    remote = (
        "sudo docker exec swan-bot-bot-api-1 python -c "
        "'from services.bot.store import Store; import sys; "
        'p=Store("/app/bot-data/bot.sqlite3").backup(); '
        'sys.stdout.buffer.write(open(p,"rb").read())\''
    )
    result = subprocess.run(
        [
            "ssh",
            "-i",
            str(args.key),
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            args.host,
            remote,
        ],
        capture_output=True,
        timeout=90,
        check=True,
    )
    data = result.stdout
    if not data.startswith(b"SQLite format 3\x00") or len(data) > 100_000_000:
        raise ValueError("Backup format or size is invalid")
    salt, nonce = os.urandom(32), os.urandom(12)
    key = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=salt, info=b"swan-bot-offhost-backup-v1"
    ).derive(args.key.read_bytes())
    cipher = AESGCM(key)
    encrypted = b"SWANBACKUP1" + salt + nonce + cipher.encrypt(nonce, data, b"SWANBACKUP1")
    recovered = cipher.decrypt(nonce, encrypted[55:], b"SWANBACKUP1")
    with tempfile.TemporaryDirectory(prefix="swan-recovery-") as directory:
        recovered_path = Path(directory) / "recovered.sqlite3"
        recovered_path.write_bytes(recovered)
        os.chmod(recovered_path, 0o600)
        with closing(sqlite3.connect(recovered_path)) as db:
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Recovered backup failed integrity check")
    args.directory.mkdir(parents=True, exist_ok=True)
    target = args.directory / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + ".enc")
    target.write_bytes(encrypted)
    os.chmod(target, 0o600)
    for old in sorted(args.directory.glob("*.enc"), reverse=True)[7:]:
        old.unlink()
    print(f"Encrypted backup saved: {target}; decrypted SQLite integrity: ok")


if __name__ == "__main__":
    main()
