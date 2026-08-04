# ─── S11 SESSION PREFLIGHT ─────────────────────────────────────────────
# Run FIRST in any new terminal:  source worklogs/s11-scripts/s11-preflight.sh
# Idempotent and resumable: re-attaches to existing evidence, never mints a
# second evidence dir, and recovers SID from deployed state rather than memory.

export COMPOSE=/srv/first-agent/repo/First-Agent-dev/docker-compose.fa.yml
export SERVICE=first-agent
export PROXY=fa-egress-proxy
export STATE=/srv/first-agent/state
export ROUTING=/srv/first-agent/routing/models.yaml
export REPO_DIR=/srv/first-agent/repo/First-Agent-dev

# --- EVID: re-attach to the newest existing dir; only mint if none exists.
export EVID=$(ls -1d /tmp/s11-evidence-* 2>/dev/null | sort | tail -1)
[ -d "$EVID" ] || { export EVID=/tmp/s11-evidence-$(date -u +%Y%m%dT%H%M%SZ); mkdir -p "$EVID"; }

# --- SID: newest session DIRECTORY.
# R19: `ls -1t` lists FILES too. A stray `sessions/session.db` (created by the
# pre-R16 8a command, because an empty sid collapses the directory level) was
# returned as the newest entry, so SID became the literal string "session.db".
# `find -maxdepth 1 -type d` cannot pick a file, and the name filter pins the
# documented shape `session-<32 hex>`.
export SID=$(docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  find /home/fa/.fa/sessions -mindepth 1 -maxdepth 1 -type d -name "session-*" \
       -printf "%T@ %f\n" 2>/dev/null | sort -rn | head -1 | cut -d" " -f2
' | tr -d '\r\n')

echo "EVID    = $EVID"
echo "SID     = ${SID:-<EMPTY>}"
echo "entries = $(ls -1 "$EVID" 2>/dev/null | wc -l)"

# --- HARD GUARDS. Each of these silently corrupted a step in this sheet.
ok=1
[ -d "$EVID" ] || { echo "STOP: EVID missing"; ok=0; }
[ -n "$SID" ]  || { echo "STOP: SID empty -> sqlite3.connect() would CREATE an empty db"; ok=0; }
case "$SID" in
  session-*) : ;;
  *) echo "STOP: SID='$SID' is not shaped session-<id>; refusing"; ok=0 ;;
esac
[ "$ok" = 1 ] && docker compose -f "$COMPOSE" exec -T -e SID="$SID" "$SERVICE" sh -lc '
  test -f "/home/fa/.fa/sessions/$SID/session.db" \
    && echo "OK: session.db exists for SID=$SID" \
    || echo "STOP: no session.db at /home/fa/.fa/sessions/$SID"'

# --- R16 residue check: a stray authority directly under sessions/ is NOT a
# session and must not exist. Report only; deletion is an operator decision.
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  for f in /home/fa/.fa/sessions/*.db /home/fa/.fa/sessions/*.db-wal /home/fa/.fa/sessions/*.db-shm; do
    [ -e "$f" ] && echo "STRAY (R16 residue): $f  $(wc -c < "$f") bytes"
  done
  exit 0'
