# Proxy requests to the flask api server
# included by nginx.conf

location /secure {
    limit_except GET { deny all; }
    shib_request /shibauthorizer;
    shib_request_use_headers on;

    more_clear_input_headers 'EPPN' 'DisplayName' 'JaDisplayName' 'IsMemberOf';

    uwsgi_pass api_server;
    include uwsgi_params;

    uwsgi_param Host              $host;
    uwsgi_param X-Forwarded-For   $proxy_add_x_forwarded_for;
    uwsgi_param X-Forwarded-Proto $scheme;

    uwsgi_param SCRIPT_NAME  "";
    uwsgi_param PATH_INFO    https://api_server/api/auth/login;
    uwsgi_param QUERY_STRING $query_string;
}

location /api/ {
    uwsgi_pass api_server;
    include uwsgi_params;

    uwsgi_param SCRIPT_NAME "";

    uwsgi_param Host $host;
    uwsgi_param X-Real-IP $remote_addr;
    uwsgi_param X-Forwarded-For $proxy_add_x_forwarded_for;
    uwsgi_param X-Forwarded-Proto $scheme;

}

