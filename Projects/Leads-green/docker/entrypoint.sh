#!/bin/sh
# Inject API_BASE into dashboard at container start
# Replaces the null placeholder with the actual API URL from env

API_BASE="${API_BASE:-http://localhost:8001}"

sed -i "s|window.API_BASE = null;|window.API_BASE = '${API_BASE}';|g" \
    /usr/share/nginx/html/index.html

echo "Dashboard starting — API_BASE=${API_BASE}"
exec nginx -g 'daemon off;'
