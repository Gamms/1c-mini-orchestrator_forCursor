#!/usr/bin/env bash
# Auto-sync 1C XML dumps from /opt/mcp-xml/<project>/src to Gitea.
#
# Deployed on <vm-docker-host>. Each project dir is a git repo with
# remote pointing to admin/<PROJECT>-src.git. Run idempotently on a timer:
# if the working tree has uncommitted changes, snapshot them as a single
# auto-commit and push.
#
# Wired up by a systemd timer (sync-xml-to-gitea.timer) firing every 30min.
# Manual run: ssh root@<vm-docker-host> /opt/mcp-xml/sync-xml-to-gitea.sh
#
# Exit codes:
#   0  - all projects either clean or successfully pushed
#   1  - one or more project pushes failed (see stderr/log for details)
#   2  - unexpected error before project loop

set -u
LOG="/var/log/mcp-xml-sync.log"
PROJECTS=(example-erp example-trade)
FAILED=0

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" | tee -a "$LOG"; }

for p in "${PROJECTS[@]}"; do
    dir="/opt/mcp-xml/${p}/src"
    if [[ ! -d "${dir}/.git" ]]; then
        log "SKIP ${p}: ${dir}/.git missing (repo not initialized)"
        continue
    fi
    cd "$dir" || { log "FAIL ${p}: cannot cd ${dir}"; FAILED=1; continue; }

    # Skip if working tree is clean — no-op fast path.
    if git diff --quiet && git diff --cached --quiet && [[ -z "$(git ls-files --others --exclude-standard)" ]]; then
        log "CLEAN ${p}"
        continue
    fi

    git add -A
    msg="auto-sync ${p}: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    if git commit -q -m "$msg"; then
        if git push -q origin master; then
            log "PUSHED ${p}: $(git rev-parse --short HEAD)"
        else
            log "PUSH_FAIL ${p}"
            FAILED=1
        fi
    else
        log "COMMIT_FAIL ${p}"
        FAILED=1
    fi
done

exit $FAILED
