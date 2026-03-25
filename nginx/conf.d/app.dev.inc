# Proxy requests to the application dev server

location ~ ^/(_nuxt|_fonts)/ {
  proxy_pass http://app_server;
  proxy_set_header Host $host;
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto $scheme;
  proxy_set_header Connection "Upgrade";
  proxy_set_header Upgrade $http_upgrade;

  proxy_buffer_size   128k;
  proxy_buffers       4 256k;
  proxy_busy_buffers_size 256k;

  access_log off;
  log_not_found off;
}

location / {
  proxy_pass http://app_server/;
  proxy_set_header Host $host;
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto $scheme;
}
