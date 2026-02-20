#!/bin/bash
# Fix nginx module symlinks before nginx starts.
#
# In production ARM64 containers (fastapi_react_mongo base image), 
# nginx-extras modules (Lua, NDK, Perl, etc.) may NOT be installed.
# But the symlinks in /etc/nginx/modules-enabled/ still reference them.
# When nginx tries to load missing .so files it immediately exits.
#
# This script removes symlinks pointing to non-existent .so files
# so nginx can start cleanly with only the modules that are available.

echo "[fix-nginx-modules] Checking nginx module availability..."

# Get nginx modules path from nginx binary (e.g., /usr/lib/nginx/modules)
MODULES_PATH=$(nginx -V 2>&1 | grep -oP "(?<=--modules-path=)\S+")
if [ -z "$MODULES_PATH" ]; then
    MODULES_PATH="/usr/lib/nginx/modules"
fi
echo "[fix-nginx-modules] Modules path: $MODULES_PATH"

REMOVED=0
for conf in /etc/nginx/modules-enabled/*.conf; do
    [ -f "$conf" ] || continue
    # Extract relative module path from load_module directive
    rel_path=$(grep -oP "(?<=load_module\s+)\S+" "$conf" 2>/dev/null | tr -d '";' | head -1)
    [ -z "$rel_path" ] && continue

    # Resolve to absolute path
    if [[ "$rel_path" = /* ]]; then
        abs_path="$rel_path"
    else
        # relative: modules/xxx.so → MODULES_PATH/xxx.so
        module_name=$(basename "$rel_path")
        abs_path="$MODULES_PATH/$module_name"
    fi

    if [ ! -f "$abs_path" ]; then
        echo "[fix-nginx-modules] REMOVING: $conf → $abs_path (not found)"
        rm -f "$conf"
        REMOVED=$((REMOVED + 1))
    fi
done

echo "[fix-nginx-modules] Done. Removed $REMOVED broken module symlink(s)."

# Verify nginx config is now valid
nginx -t 2>/dev/null
if [ $? -eq 0 ]; then
    echo "[fix-nginx-modules] nginx -t: OK"
else
    echo "[fix-nginx-modules] WARNING: nginx config still has issues"
fi

exit 0
