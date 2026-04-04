FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

COPY . /app

ENV DATABASE_URL=sqlite:////data/junit_dashboard.db
ENV PORT=5100

EXPOSE ${PORT}

CMD ["python", "run_web.py", "--config", "/config/config.yaml"]

