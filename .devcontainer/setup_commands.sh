#!/bin/bash

install_deps() {
    # Install Python dependencies
    pip install --upgrade pip && pip install uv
    uv sync && uv pip install -e .

    if ! grep -q "venv_activate_reload" ~/.bashrc 2>/dev/null; then
        {
        echo ""
        echo "# venv_activate_reload"
        echo "if [ -f ~/.venv/bin/activate ]; then"
        echo "  source ~/.venv/bin/activate"
        echo "fi"
        } >> ~/.bashrc
    fi

    # Install Node.js dependencies
    npm install -g npm && npm install -g pnpm
    pnpm config set global-bin-dir "$HOME/.local/bin"
    pnpm config set store-dir "$HOME/.pnpm-store"
    pnpm install -r
}

genarate_ssl_key() {

    SSL_DIR="nginx/ssl"
    CRT_FILE="server.crt"
    KEY_FILE="server.key"
    GEN_KEY_SCRIPT="gen_key.sh"

    if [ ! -f "$SSL_DIR/$CRT_FILE" ] || [ ! -f "$SSL_DIR/$KEY_FILE" ]; then
        if [ -f "$SSL_DIR/$GEN_KEY_SCRIPT" ]; then
            echo "Generating SSL key and certificate..."
            (
                cd "$SSL_DIR" && bash "$GEN_KEY_SCRIPT"
            )
        else
            echo "Error: $SSL_DIR/$GEN_KEY_SCRIPT not found."
            exit 1
        fi
    else
        echo "SSL key and certificate already exist."
    fi
}

container_watch() {
    pkill -9 -f 'docker compose up --watch' || true && docker compose up --watch
}


FUNCTION_NAME=$1

if [ -z "$FUNCTION_NAME" ]; then
    echo "Error: Function name argument is missing."
    exit 1
fi

shift

if type -t "$FUNCTION_NAME" | grep -q 'function'; then
    "$FUNCTION_NAME" "$@"
else
    echo "Error: Function '$FUNCTION_NAME' not found."
    exit 1
fi
