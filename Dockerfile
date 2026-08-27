# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.14
ARG UV_VERSION=0.12

FROM docker.io/astral/uv:${UV_VERSION} AS uv

# ==============================
# Base stage: common setup
# ==============================
FROM python:${PYTHON_VERSION}-slim AS base

ARG USERNAME=pyuser
ARG GROUPNAME=${USERNAME}
ARG UID=1000
ARG GID=1000

ENV VIRTUAL_ENV="/code/.venv"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /code
RUN \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get upgrade --yes \
    && \
    apt-get install -y --no-install-recommends \
        git

# Setup uv
# From https://docs.astral.sh/uv/guides/integration/docker/
# but using docker.io/astral/uv because failure to fetch oauth token
COPY --from=uv /uv /uvx /bin/

RUN groupadd -g ${GID} ${GROUPNAME} && \
    useradd -m -u ${UID} -g ${GID} -s /bin/bash ${USERNAME}
RUN chown ${USERNAME}:${GROUPNAME} /code
USER ${USERNAME}


# ==============================
# Development stage:
#   install dev dependencies and start dev server
# ==============================
FROM base AS dev

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv sync --frozen --no-install-project

COPY --chown=${USERNAME}:${GROUPNAME} . .
RUN uv pip install -e .

ENV FLASK_ENV=development
ENV FLASK_APP="server.app"
ENV FLASK_RUN_HOST="0.0.0.0"
ENV FLASK_RUN_PORT=5050
ENV FLASK_DEBUG=1

EXPOSE 5050
CMD ["flask", "run", "--reload"]

# ==============================
# Production stage:
#   install only prod dependencies and start prod server
# ==============================
FROM base AS prod

USER root
RUN \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update \
    && \
    apt-get install -y --no-install-recommends \
        build-essential \
        python3-dev \
        libssl-dev \
        libpcre2-dev \
        supervisor
RUN uv pip install uwsgi --system


COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen --no-install-project

COPY . .
RUN uv pip install .

ENV FLASK_ENV=production
ENV FLASK_APP="server.app"

CMD ["/usr/bin/supervisord", "-c", "supervisord.web.conf"]
