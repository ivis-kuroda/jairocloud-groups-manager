# Proxy requests to the flask dev server
# included by nginx.conf

location /secure {
    limit_except GET { deny all; }
    shib_request /shibauthorizer;
    shib_request_use_headers on;

    proxy_pass http://api_server/api/auth/login;

    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

location /api/ {
    proxy_pass http://api_server$request_uri;
    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
