FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Run as non-root
RUN useradd -m app && chown -R app:app /app
USER app

# Daily job by default. ECS can only override CMD (not ENTRYPOINT), so the
# backfill runs with a command override: ["-m", "ingestion.backfill", "--days", "400"]
ENTRYPOINT ["python"]
CMD ["-m", "ingestion.main"]
