# syntax=docker/dockerfile:1.7
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:/root/.local/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && apt-get purge -y curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --extra dev

COPY tools/chat_ui.py ./tools/chat_ui.py

EXPOSE 8501

CMD ["uv", "run", "streamlit", "run", "tools/chat_ui.py", \
     "--server.address", "0.0.0.0", "--server.port", "8501", \
     "--server.headless", "true"]
