#!/bin/bash
# Fix nginx module loading issues before nginx starts.
#
# Problem: In production ARM64 containers (fastapi_react_mongo base image),
# nginx-extras .so modules (Lua, NDK, Perl, GeoIP, etc.) may NOT be installed.
# But /etc/nginx/modules-enabled/ still has symlinks referencing them, and
# /etc/nginx/nginx-code-server.conf has explicit load_module directives.
# When nginx tries to load missing .so files it exits immediately.
#
# Solution: Remove broken symlinks and comment out missing load_module lines.

echo "[fix-nginx] Starting nginx module compatibility check..."

# Get nginx modules absolute path from binary (e.g., /usr/lib/nginx/modules)
MODULES_PATH=$(nginx -V 2>&1 | tr ' ' '\n' | grep "modules-path" | cut -d= -f2)
[ -z "$MODULES_PATH" ] && MODULES_PATH="/usr/lib/nginx/modules"
echo "[fix-nginx] Modules path: $MODULES_PATH"

# Helper: given a load_module path (relative or absolute), return absolute path
resolve_module() {
    local path="$1"
    # Remove quotes and semicolons
    path=$(echo "$path" | tr -d '"' | tr -d "'" | tr -d ';')
    if [[ "$path" = /* ]]; then
        echo "$path"
    else
        # Relative path: prepend modules dir
        echo "$MODULES_PATH/$(basename "$path")"
    fi
}

# -------------------------------------------------------------------
# STEP 1: Fix /etc/nginx/modules-enabled/ symlinks
# -------------------------------------------------------------------
REMOVED=0
for conf in /etc/nginx/modules-enabled/*.conf; do
    [ -f "$conf" ] || continue
    # Extract path from "load_module <path>;" line
    mod_line=$(grep "load_module" "$conf" 2>/dev/null | head -1)
    [ -z "$mod_line" ] && continue
    # Get everything after "load_module " and before ";"
    rel_path=$(echo "$mod_line" | awk '{print $2}' | tr -d '";')
    [ -z "$rel_path" ] && continue
    abs_path=$(resolve_module "$rel_path")

    if [ ! -f "$abs_path" ]; then
        echo "[fix-nginx] Removing broken symlink: $(basename $conf) -> $abs_path (not found)"
        rm -f "$conf"
        REMOVED=$((REMOVED + 1))
    fi
done
echo "[fix-nginx] Removed $REMOVED broken module symlink(s) from modules-enabled/"

# -------------------------------------------------------------------
# STEP 2: Fix /etc/nginx/nginx-code-server.conf explicit load_module
# -------------------------------------------------------------------
CODE_CONF="/etc/nginx/nginx-code-server.conf"
if [ -f "$CODE_CONF" ]; then
    PATCHED=0
    # Process each load_module line
    while IFS= read -r line; do
        if echo "$line" | grep -q "load_module"; then
            rel_path=$(echo "$line" | awk '{print $2}' | tr -d '";')
            if [ -n "$rel_path" ]; then
                abs_path=$(resolve_module "$rel_path")
                if [ ! -f "$abs_path" ]; then
                    # Comment out the line using Python for reliable substitution
                    python3 -c "
import re, sys
content = open('$CODE_CONF').read()
# Comment out this specific load_module line
escaped = re.escape('$line'.strip())
content = re.sub(r'^\s*' + escaped + r'\s*$', '# DISABLED (missing .so): $line'.strip(), content, flags=re.MULTILINE)
open('$CODE_CONF', 'w').write(content)
print('Commented out: $line'.strip())
" 2>/dev/null || true
                    PATCHED=$((PATCHED + 1))
                    echo "[fix-nginx] Disabled in nginx-code-server.conf: $abs_path"
                fi
            fi
        fi
    done < <(grep "load_module" "$CODE_CONF" 2>/dev/null)
    echo "[fix-nginx] Patched $PATCHED load_module line(s) in nginx-code-server.conf"
fi

# -------------------------------------------------------------------
# STEP 3: Verify nginx configs
# -------------------------------------------------------------------
if nginx -t -c /etc/nginx/nginx.conf 2>/dev/null; then
    echo "[fix-nginx] nginx.conf: OK"
else
    echo "[fix-nginx] WARNING: nginx.conf still invalid"
fi

if [ -f "$CODE_CONF" ]; then
    if nginx -t -c "$CODE_CONF" 2>/dev/null; then
        echo "[fix-nginx] nginx-code-server.conf: OK"
    else
        echo "[fix-nginx] nginx-code-server.conf: still has issues (code-server IDE will not work, app unaffected)"
    fi
fi

echo "[fix-nginx] Done."
exit 0
