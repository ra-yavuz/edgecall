# edgecall server image.
#
# A small image that runs the edgecall HTTP API. It does NOT host a model:
# point it at any OpenAI-compatible endpoint (llama.cpp, ollama, LM Studio,
# hydra-llm) via EDGECALL_MODEL_BASE_URL. See docker-compose.yml.

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/edgecall
COPY pyproject.toml README.md LICENSE ./
COPY lib ./lib
COPY functions ./functions

RUN pip install --no-cache-dir .

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    EDGECALL_HOST=0.0.0.0 \
    EDGECALL_PORT=8900 \
    EDGECALL_FUNCTIONS_DIR=/opt/edgecall/functions

EXPOSE 8900
CMD ["edgecall", "serve"]
