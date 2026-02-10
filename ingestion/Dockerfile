FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Run as non-root
RUN useradd -m app && chown -R app:app /app
USER app

ENTRYPOINT ["python", "-m", "ingestion.main"]
