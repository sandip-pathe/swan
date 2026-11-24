#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(realpath "$0")")/../.."
umask 077
mkdir -p .local/backups
target=".local/backups/swan-$(date -u +%Y%m%dT%H%M%SZ)-$$.dump"
temporary="$target.partial"
trap 'rm -f -- "$temporary"' EXIT
hosting/oracle/swan exec -T db pg_dump -U swan -d swan_trade --format=custom --no-owner --no-acl > "$temporary"
test -s "$temporary"
hosting/oracle/swan exec -T db pg_restore --list < "$temporary" >/dev/null
mv -- "$temporary" "$target"
printf 'Database backup saved: %s\n' "$target"
