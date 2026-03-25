# syntax=docker/dockerfile:1

ARG NGINX_VERSION=1.29.6
ARG NODE_VERSION=24
ARG SHIB_MOD_VERSION=2.0.2
ARG HEADERS_MORE_VERSION=0.37

# ==============================
# Build stage:
#   build modules nginx-http-shibboleth
# ==============================
FROM debian:trixie-slim AS build

ARG NGINX_VERSION
ARG SHIB_MOD_VERSION
ARG HEADERS_MORE_VERSION
WORKDIR /usr/src

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential git wget ca-certificates libpcre2-dev zlib1g-dev libssl-dev && \
    rm -rf /var/lib/apt/lists/*

RUN wget http://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz && \
    tar xzf nginx-${NGINX_VERSION}.tar.gz
RUN wget https://github.com/nginx-shib/nginx-http-shibboleth/archive/v${SHIB_MOD_VERSION}.tar.gz && \
    tar xzf v${SHIB_MOD_VERSION}.tar.gz
RUN wget https://github.com/openresty/headers-more-nginx-module/archive/v${HEADERS_MORE_VERSION}.tar.gz && \
    tar xzf v${HEADERS_MORE_VERSION}.tar.gz

WORKDIR /usr/src/nginx-${NGINX_VERSION}
RUN ./configure --with-compat \
      --add-dynamic-module=../nginx-http-shibboleth-${SHIB_MOD_VERSION} \
      --add-dynamic-module=../headers-more-nginx-module-${HEADERS_MORE_VERSION} && \
    make modules


# ==============================
# Build stage:
#   build the Nuxt application
# ==============================
FROM node:${NODE_VERSION}-slim AS app

WORKDIR /code
RUN chown node:node /code
RUN npm install -g npm && npm install -g pnpm

USER node
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm i --frozen-lockfile

COPY --chown=node:node . .
RUN NODE_ENV=production pnpm nuxt generate


# ==============================
# Base stage:
#   install dependencies and configure nginx + shibboleth
# ==============================
FROM nginx:${NGINX_VERSION}-trixie AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    supervisor \
    libapache2-mod-shib \
    shibboleth-sp-utils \
    shibboleth-sp-common \
    xmlsec1 &&\
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/shibboleth /var/log/supervisor && \
    chown nginx:nginx /opt/shibboleth /var/log/supervisor
RUN mkdir -p /var/run/shibboleth && \
    chown _shibd:_shibd /var/run/shibboleth

# nginx-http-shibboleth module
COPY --from=build \
    /usr/src/nginx-${NGINX_VERSION}/objs/ngx_http_shibboleth_module.so \
    /usr/src/nginx-${NGINX_VERSION}/objs/ngx_http_headers_more_filter_module.so \
    /etc/nginx/modules/

COPY nginx/supervisord.conf /etc/supervisord.conf
COPY nginx/shibboleth2.xml /etc/shibboleth/shibboleth2.xml
COPY nginx/cgidp-metadata.xml /etc/shibboleth/cgidp-metadata.xml

COPY nginx/attribute-map.inc.xml /etc/shibboleth/attribute-map.inc.xml
RUN sed -i \
    '/Other eduPerson attributes/r /etc/shibboleth/attribute-map.inc.xml' \
    /etc/shibboleth/attribute-map.xml

COPY nginx/attribute-policy.inc.xml /etc/shibboleth/attribute-policy.inc.xml
RUN AWK_PATTERN='Catch-all that passes everything else through unmolested.' && \
    awk -v p="$AWK_PATTERN" -v target_file="/etc/shibboleth/attribute-policy.inc.xml" \
        '$0 ~ p { system("cat " target_file); } { print }' \
        /etc/shibboleth/attribute-policy.xml > /tmp/temp_policy.xml && \
    mv /tmp/temp_policy.xml /etc/shibboleth/attribute-policy.xml

COPY nginx/conf.d /etc/nginx/conf.d
COPY nginx/ssl/server.crt /etc/nginx/server.crt
COPY nginx/ssl/server.key /etc/nginx/server.key

COPY nginx/ssl/server.crt /etc/shibboleth/server.crt
COPY nginx/ssl/server.key /etc/shibboleth/server.key
RUN chmod 644 /etc/shibboleth/server.crt /etc/shibboleth/server.key

RUN sed -i \
    '1s|^|load_module modules/ngx_http_shibboleth_module.so;\n|' \
    /etc/nginx/nginx.conf
RUN sed -i \
    '1s|^|load_module modules/ngx_http_headers_more_filter_module.so;\n|' \
    /etc/nginx/nginx.conf


# ==============================
# Development stage:
#   override nginx config for dev server
# ==============================
FROM base AS dev

RUN sed -i \
    '1s|^|upstream app_server {\n  server app:3000;\n}\n\n|' \
    /etc/nginx/conf.d/default.conf
RUN sed -i \
    '/# Application resources requests/,/# replace this for dev server/ \
    s|app[.]inc|app.dev.inc|' \
    /etc/nginx/conf.d/default.conf
RUN sed -i \
    '/# Application api requests/,/# replace this for dev server/ \
    s|api[.]inc|api.dev.inc|' \
    /etc/nginx/conf.d/default.conf

EXPOSE 80 443

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]


# ==============================
# Production stage:
#   copy built app to nginx html folder
# ==============================
FROM base AS prod

COPY --from=app --chown=nginx:nginx /code/.output/public /usr/share/nginx/html

EXPOSE 80 443

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]
