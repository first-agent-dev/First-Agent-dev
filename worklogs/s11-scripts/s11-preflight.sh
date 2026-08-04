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

# --- SID: the session that OWNS this sheet's `fa run` evidence.
# R19: `ls -1t` also lists FILES, and a stray `sessions/session.db` was picked.
# R20: "newest directory" is ALSO wrong. S11.7's workflow created a newer
# session, so newest returned the workflow session while 8a/8b/8c assert on the
# S11.5 runs (s11-run-a..d). That is not a crash - it is a confident answer
# about the wrong session, with the positive control still passing.
# Correct rule: pick the session whose event_log actually CONTAINS s11-run-b.
# Falls back to newest-with-a-db only if no session owns it, and says so.
export SID=$(docker compose -f "$COMPOSE" exec -T "$SERVICE" python - <<'PYSID' | tr -d '\r\n'
import pathlib, sqlite3
root = pathlib.Path("/home/fa/.fa/sessions")
owner = fallback = ""
for d in sorted((p for p in root.iterdir() if p.is_dir() and p.name.startswith("session-")),
                key=lambda p: p.stat().st_mtime, reverse=True):
    db = d / "session.db"
    if not db.is_file():
        continue
    fallback = fallback or d.name
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        hit = con.execute(
            "SELECT 1 FROM event_log WHERE run_id='s11-run-b' LIMIT 1").fetchone()
        con.close()
    except Exception:
        continue
    if hit:
        owner = d.name
        break
print(owner or fallback)
PYSID
)
<<<<<<< ours

# --- DEPLOY_SHA: R25. The sheet's 10a prints "(expected $DEPLOY_SHA)" and it
# came out EMPTY in a fresh terminal, because only S11.0 ever set it. Recover
# it from the evidence dir, which is the durable record, not shell memory.
export DEPLOY_SHA=$(cat "$EVID/00-deploy-sha.txt" 2>/dev/null | tr -d '\r\n')
=======
>>>>>>> theirs

# --- DEPLOY_SHA: R25. The sheet's 10a prints "(expected $DEPLOY_SHA)" and it
# came out EMPTY in a fresh terminal, because only S11.0 ever set it. Recover
# it from the evidence dir, which is the durable record, not shell memory.
export DEPLOY_SHA=$(cat "$EVID/00-deploy-sha.txt" 2>/dev/null | tr -d '\r\n')

echo "EVID    = $EVID"
echo "SID     = ${SID:-<EMPTY>}"
echo "DEPLOY  = ${DEPLOY_SHA:-<EMPTY - 00-deploy-sha.txt missing>}"
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
