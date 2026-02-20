#!/bin/bash
# Fix nginx module symlinks before nginx starts.
# In production ARM64 containers, nginx-extras modules (Lua, NDK) may not be installed.
# This script removes symlinks that point to non-existent .so files so nginx can start.

echo "=== nginx module check ==="
REMOVED=0

for conf in /etc/nginx/modules-enabled/*.conf; do
    [ -f "$conf" ] || continue
    # Extract the .so path from load_module directive
    module_path=$(grep -oP "(?<=load_module\s)[^;]+" "$conf" 2>/dev/null | tr -d '"' | tr -d "'" | xargs)
    if [ -n "$module_path" ]; then
        if [ ! -f "$module_path" ]; then
            echo "Removing broken module symlink: $conf (missing: $module_path)"
            rm -f "$conf"
            REMOVED=$((REMOVED + 1))
        else
            echo "OK: $module_path"
        fi
    fi
done

echo "=== nginx module check done (removed $REMOVED broken symlinks) ==="
exit 0
