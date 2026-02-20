#!/bin/bash
# Fix nginx module loading issues before nginx starts.
#
# Problem: In production ARM64 containers, nginx-extras .so modules
# (Lua, NDK, Perl, GeoIP) may NOT be installed, causing nginx to fail.
#
# This script is run as supervisor program with priority=0 (before nginx).
# It:
# 1. Removes broken symlinks from /etc/nginx/modules-enabled/
# 2. If Lua missing, replaces nginx-code-server.conf with Lua-free version
# 3. Updates /etc/nginx/sites-enabled/default to serve /health and proxy to app

echo "[fix-nginx] Starting nginx module compatibility check..."

# Get nginx modules path (e.g., /usr/lib/nginx/modules)
MODULES_PATH=$(nginx -V 2>&1 | tr ' ' '\n' | grep "modules-path" | cut -d= -f2)
[ -z "$MODULES_PATH" ] && MODULES_PATH="/usr/lib/nginx/modules"
echo "[fix-nginx] Modules path: $MODULES_PATH"

# Helper: resolve relative module path to absolute
resolve_module() {
    local path="$1"
    path=$(echo "$path" | tr -d '"' | tr -d "'" | tr -d ';')
    if [[ "$path" = /* ]]; then echo "$path"
    else echo "$MODULES_PATH/$(basename "$path")"
    fi
}

# Check if Lua module is available
LUA_MISSING=false
if [ ! -f "$MODULES_PATH/ngx_http_lua_module.so" ] || [ ! -f "$MODULES_PATH/ndk_http_module.so" ]; then
    LUA_MISSING=true
    echo "[fix-nginx] Lua/NDK modules NOT found - production mode"
fi

# -------------------------------------------------------------------
# STEP 1: Fix /etc/nginx/modules-enabled/ symlinks
# -------------------------------------------------------------------
REMOVED=0
for conf in /etc/nginx/modules-enabled/*.conf; do
    [ -f "$conf" ] || continue
    mod_line=$(grep "load_module" "$conf" 2>/dev/null | head -1)
    [ -z "$mod_line" ] && continue
    rel_path=$(echo "$mod_line" | awk '{print $2}' | tr -d '";')
    [ -z "$rel_path" ] && continue
    abs_path=$(resolve_module "$rel_path")
    if [ ! -f "$abs_path" ]; then
        echo "[fix-nginx] Removing broken symlink: $(basename $conf) (missing: $abs_path)"
        rm -f "$conf"
        REMOVED=$((REMOVED + 1))
    fi
done
echo "[fix-nginx] Removed $REMOVED broken module symlink(s)"

# -------------------------------------------------------------------
# STEP 2: If Lua is missing, replace nginx-code-server.conf
# -------------------------------------------------------------------
CODE_CONF="/etc/nginx/nginx-code-server.conf"
if [ "$LUA_MISSING" = true ] && [ -f "$CODE_CONF" ]; then
    echo "[fix-nginx] Replacing nginx-code-server.conf with Lua-free version..."
    cat > "$CODE_CONF" << 'NGINX_CONF'
user root;
events { worker_connections 1024; }
http {
    access_log /var/log/nginx/code-access.log;
    error_log /var/log/nginx/code-error.log;
    upstream code-server { server 127.0.0.1:8080; }
    server {
        listen 1111;
        server_name _;
        location / {
            proxy_pass http://code-server;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_read_timeout 3600s;
            proxy_intercept_errors on;
            error_page 502 503 504 = @loading;
        }
        location @loading {
            default_type text/html;
            return 503 '<html><body><h2>IDE starting...</h2><script>setTimeout(()=>location.reload(),5000)</script></body></html>';
        }
    }
}
NGINX_CONF
    echo "[fix-nginx] nginx-code-server.conf replaced with Lua-free version"
fi

# -------------------------------------------------------------------
# STEP 3: Update sites-enabled/default to include /health endpoint
#         and proxy to app backend/frontend
# -------------------------------------------------------------------
DEFAULT_SITE="/etc/nginx/sites-enabled/default"
if [ -f "$DEFAULT_SITE" ] && ! grep -q "emergent-app-proxy" "$DEFAULT_SITE" 2>/dev/null; then
    echo "[fix-nginx] Replacing /etc/nginx/sites-enabled/default with app proxy config..."
    cat > "$DEFAULT_SITE" << 'SITE_CONF'
# emergent-app-proxy - managed by fix_nginx_modules.sh
# Serves health check on port 80 and proxies to app services
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    # Health check endpoint (for deployment probe)
    location = /health {
        default_type application/json;
        return 200 '{"status":"healthy","service":"nginx-proxy"}';
        add_header Content-Type application/json;
    }

    # Proxy API requests to FastAPI backend
    location /api/ {
        proxy_pass http://127.0.0.1:8001/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_connect_timeout 5s;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    # Proxy asset/export requests to FastAPI
    location /exports/ {
        proxy_pass http://127.0.0.1:8001/exports/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_read_timeout 300s;
    }

    # Proxy frontend (React dev server)
    location / {
        proxy_pass http://127.0.0.1:3000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_connect_timeout 5s;
        proxy_read_timeout 300s;
        proxy_intercept_errors on;
        error_page 502 503 504 = @loading;
    }

    location @loading {
        default_type text/html;
        return 503 '<html><body><h2>Application loading...</h2><script>setTimeout(()=>location.reload(),5000)</script></body></html>';
    }
}
SITE_CONF
    echo "[fix-nginx] /etc/nginx/sites-enabled/default updated"
fi

# -------------------------------------------------------------------
# STEP 4: Verify and (re)start nginx
# -------------------------------------------------------------------
if nginx -t -c /etc/nginx/nginx.conf 2>/dev/null; then
    echo "[fix-nginx] nginx.conf: OK"
    # Try to start/reload nginx on port 80
    if ss -tln 2>/dev/null | grep -q ":80 "; then
        echo "[fix-nginx] Port 80 active - reloading nginx config"
        nginx -s reload 2>/dev/null || true
    else
        echo "[fix-nginx] Starting nginx on port 80..."
        nginx
        if [ $? -eq 0 ]; then
            echo "[fix-nginx] nginx started successfully on port 80"
        else
            echo "[fix-nginx] Could not start nginx (non-fatal - backend health check still works on :8001)"
        fi
    fi
else
    echo "[fix-nginx] WARNING: nginx.conf still invalid - deployment health check will use :8001 directly"
fi

echo "[fix-nginx] Done."
exit 0
