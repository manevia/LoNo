#!/usr/bin/env bash
# lono-backup db|media  - database dump (keep 14) or media archive (keep 2) in /var/backups/lono.
set -euo pipefail
DEPLOY="${LONO_DEPLOY:-$(cd "$(dirname "$0")" && pwd)}"
DEST=/var/backups/lono; mkdir -p "$DEST"; chmod 700 "$DEST"
STAMP="$(date +%Y%m%d-%H%M)"
COMPOSE=(docker compose -f "$DEPLOY/docker-compose.yml" --env-file "$DEPLOY/.env")
case "${1:-db}" in
  db)
    "${COMPOSE[@]}" exec -T mongo mongodump --archive --gzip --quiet > "$DEST/mongo-$STAMP.archive.gz"
    ls -1t "$DEST"/mongo-*.archive.gz | tail -n +15 | xargs -r rm -f
    echo "$(date -Is) database backup: mongo-$STAMP.archive.gz" ;;
  media)
    docker run --rm -v lono_lono-data:/data:ro -v "$DEST":/backup alpine:3.20 tar -czf "/backup/media-$STAMP.tar.gz" -C /data .
    ls -1t "$DEST"/media-*.tar.gz | tail -n +3 | xargs -r rm -f
    echo "$(date -Is) media backup: media-$STAMP.tar.gz" ;;
  *) echo "usage: lono-backup db|media" >&2; exit 2 ;;
esac
# Copy /var/backups/lono to another machine or storage regularly: a backup on the same disk isn't enough.
