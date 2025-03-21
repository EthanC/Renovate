FROM python:3.12-slim-bookworm

WORKDIR /renovate
COPY . .

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
RUN uv sync --frozen --no-dev

CMD [ "uv", "run", "renovate.py" ]
