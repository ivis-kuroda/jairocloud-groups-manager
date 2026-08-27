# syntax=docker/dockerfile:1

ARG OS_VERSION=trixie
ARG PYTHON_VERSION=3.14
ARG UV_VERSION=0.12

FROM docker.io/astral/uv:${UV_VERSION} AS uv

# ==============================
# Base stage: common setup
# ==============================
FROM docker.io/python:${PYTHON_VERSION}-${OS_VERSION} AS base

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
    # Install system dependencies
    apt-get install --yes --no-install-recommends \
        git

# Setup uv
# From https://docs.astral.sh/uv/guides/integration/docker/
# but using docker.io/astral/uv because failure to fetch oauth token
COPY --from=uv /uv /uvx /bin/
RUN uv venv --allow-existing --python $(which python)
ENV PATH=${VIRTUAL_ENV}/bin:/uvx/bin:${PATH}

RUN groupadd -g ${GID} ${GROUPNAME} && \
    useradd -m -u ${UID} -g ${GID} -s /bin/bash ${USERNAME}
RUN chown -R ${USERNAME}:${GROUPNAME} /code
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
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv pip install -e .

ENV FLASK_ENV=development
ENV FLASK_APP="server.app"
ENV FLASK_RUN_HOST="0.0.0.0"
ENV FLASK_RUN_PORT=5050
ENV FLASK_DEBUG=1

EXPOSE 5050
CMD ["flask", "run", "--reload"]


# ==============================
# Build stage:
#   compile uwsgi and install prod dependencies
# ==============================
FROM base AS build

USER root
RUN \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    # Install build dependencies
    apt-get install --yes --no-install-recommends \
        build-essential \
        python3-dev \
        libssl-dev \
        libpcre2-dev
RUN uv pip install uwsgi --system

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen --no-install-project

COPY . .
RUN uv pip install .


# ==============================
# Production stage:
#   copy build artifacts only, keep the image lightweight
# ==============================
FROM base AS prod

USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libssl3 \
        libpcre2-8-0 \
        supervisor && \
    rm -rf /var/lib/apt/lists/*

# uwsgi is installed into the system python (--system), not the venv
COPY --from=build /usr/local /usr/local
COPY --from=build /code /code

ENV FLASK_ENV=production
ENV FLASK_APP="server.app"

CMD ["/usr/bin/supervisord", "-c", "supervisord.web.conf"]
