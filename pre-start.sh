#!/bin/bash
# Pre-startup hook: run before nginx is started by the deployment script.
# Fixes nginx module loading issues in production containers where 
# nginx-extras .so files may not be installed (ARM64 base image).
exec /bin/bash /app/fix_nginx_modules.sh
