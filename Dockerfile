FROM python:3.12-slim

WORKDIR /app

# Install git and essential tools for sandbox AST analysis
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
COPY config ./config
COPY console ./console
COPY demo_app ./demo_app
COPY NOTICE ./NOTICE
COPY LICENSE ./LICENSE

RUN pip install --no-cache-dir .

EXPOSE 8080

ENV CHAOSMEDIC_DB_PATH=/app/data/chaosmedic.db
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["chaosmedic-api"]
