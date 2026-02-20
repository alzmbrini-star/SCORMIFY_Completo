#!/bin/bash
# Fix nginx module loading issues before nginx starts.
#
# In production ARM64 containers (fastapi_react_mongo base image), 
# nginx-extras modules (Lua, NDK, Perl, GeoIP, etc.) may NOT be installed.
# Two nginx configs need fixing:
#   1. /etc/nginx/nginx.conf - includes modules-enabled/*.conf symlinks
#   2. /etc/nginx/nginx-code-server.conf - has explicit load_module directives
#
# This script:
#   a) Removes symlinks in modules-enabled/ pointing to non-existent .so files
#   b) Comments out load_module lines in nginx-code-server.conf for missing modules

set -e

echo "[fix-nginx-modules] Starting nginx module check..."

# Get nginx modules path (e.g., /usr/lib/nginx/modules)
MODULES_PATH=$(nginx -V 2>&1 | grep -oP "(?<=--modules-path=)\S+")
[ -z "$MODULES_PATH" ] && MODULES_PATH="/usr/lib/nginx/modules"
echo "[fix-nginx-modules] Modules path: $MODULES_PATH"

# -------------------------------------------------------------------
# STEP 1: Fix /etc/nginx/modules-enabled/ symlinks
# -------------------------------------------------------------------
REMOVED=0
for conf in /etc/nginx/modules-enabled/*.conf; do
    [ -f "$conf" ] || continue
    rel_path=$(grep -oP "(?<=load_module\s+)\S+" "$conf" 2>/dev/null | tr -d '";' | head -1)
    [ -z "$rel_path" ] && continue

    if [[ "$rel_path" = /* ]]; then
        abs_path="$rel_path"
    else
        module_name=$(basename "$rel_path")
        abs_path="$MODULES_PATH/$module_name"
    fi

    if [ ! -f "$abs_path" ]; then
        echo "[fix-nginx-modules] Removing broken symlink: $conf (missing: $abs_path)"
        rm -f "$conf"
        REMOVED=$((REMOVED + 1))
    fi
done
echo "[fix-nginx-modules] Removed $REMOVED broken module symlink(s) from modules-enabled/"

# -------------------------------------------------------------------
# STEP 2: Fix /etc/nginx/nginx-code-server.conf explicit load_module
# -------------------------------------------------------------------
CODE_CONF="/etc/nginx/nginx-code-server.conf"
if [ -f "$CODE_CONF" ]; then
    PATCHED=0
    # Read each load_module line and check if .so exists
    while IFS= read -r line; do
        if echo "$line" | grep -q "load_module"; then
            rel_path=$(echo "$line" | grep -oP "(?<=load_module\s+)\S+" | tr -d '";' | head -1)
            if [ -n "$rel_path" ]; then
                if [[ "$rel_path" = /* ]]; then
                    abs_path="$rel_path"
                else
                    module_name=$(basename "$rel_path")
                    abs_path="$MODULES_PATH/$module_name"
                fi
                if [ ! -f "$abs_path" ]; then
                    # Comment out the line in place
                    escaped=$(printf '%s\n' "$line" | sed 's/[[\.*^$()+?{|]/\\&/g')
                    sed -i "s|^${line}$|# DISABLED (missing .so): ${line}|" "$CODE_CONF" 2>/dev/null || true
                    PATCHED=$((PATCHED + 1))
                    echo "[fix-nginx-modules] Disabled load_module in nginx-code-server.conf: $abs_path"
                fi
            fi
        fi
    done < "$CODE_CONF"
    echo "[fix-nginx-modules] Patched $PATCHED load_module line(s) in nginx-code-server.conf"
fi

# -------------------------------------------------------------------
# STEP 3: Verify nginx configs are valid
# -------------------------------------------------------------------
nginx -t -c /etc/nginx/nginx.conf 2>/dev/null && \
    echo "[fix-nginx-modules] nginx.conf: OK" || \
    echo "[fix-nginx-modules] WARNING: nginx.conf still has issues"

if [ -f "$CODE_CONF" ]; then
    nginx -t -c "$CODE_CONF" 2>/dev/null && \
        echo "[fix-nginx-modules] nginx-code-server.conf: OK" || \
        echo "[fix-nginx-modules] nginx-code-server.conf still has issues (non-blocking)"
fi

echo "[fix-nginx-modules] Done."
exit 0
