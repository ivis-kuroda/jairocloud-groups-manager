# Proxy configuration for application resources

root /usr/share/nginx/html;

index index.html;

location ~ ^/(_nuxt|_fonts)/ {
  access_log off;
  log_not_found off;

  add_header Cache-Control "public, immutable";

  try_files $uri =404;
}

location / {
  try_files $uri $uri/ /index.html;
}
