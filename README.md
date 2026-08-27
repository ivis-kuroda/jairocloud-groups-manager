# JAIRO Cloud Groups Manager

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.14+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3BABC3?logo=flask&labelColor=000000)](https://flask.palletsprojects.com)
[![Nuxt UI](https://img.shields.io/badge/Nuxt%20UI-00DC82?logo=nuxt&labelColor=020420)](https://ui.nuxt.com)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://pre-commit.com)

A web client for JAIRO Cloud repository administrators to manage groups in the GakuNin Cloud Gateway.

## Development Setup
With DevContainer, your development environment is ready in no time!

1. Install [Visual Studio Code](https://code.visualstudio.com/) and [Docker](https://www.docker.com/) with [Docker Compose](https://docs.docker.com/compose/).
2. Install the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) for Visual Studio Code.
3. Open this repository in Visual Studio Code.
4. When prompted, click "Reopen in Container" to start the DevContainer.


**Manual Setup**

1. Install [Python 3.14+](https://www.python.org/downloads/) and [Node.js 24+](https://nodejs.org/en/download/).
2. Install dependencies:
    ```bash
    uv sync
    pnpm install -r
    ```
3. Create docker network:
    ```bash
    docker network create jairocloud-groups-manager_default
    ```
4. Start the development server:
    ```bash
    LOCAL_WORKSPACE_FOLDER=$(pwd) docker compose up --watch
    ```

> [!TIP]
> When the Vite dev server fails to start due to permission problems, create a `.nuxt` directory on the host machine or run `pnpm postinstall`, then try again.
