# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.14

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
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
RUN pip install -U pip && pip install uv

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
RUN uv sync --frozen

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
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        python3-dev \
        libssl-dev \
        libpcre2-dev \
        supervisor && \
    rm -rf /var/lib/apt/lists/*
RUN uv pip install uwsgi --system


COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

COPY . .
RUN uv pip install .

ENV FLASK_ENV=production
ENV FLASK_APP="server.app"

CMD ["/usr/bin/supervisord", "-c", "supervisord.web.conf"]
