# Use (basic) Python image as a base to build Econ Sentinel image on top of
FROM python:3.12-slim

# Set the folder in the image where files will be stored
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Copy code into image
COPY . . 

# Run as non-root (a regular user)
RUN useradd -m app && chown -R app:app /app
USER app


# In ECS, ENTRYPOINT can't be overriden but CMD can
# Run backfill: ["-m", "ingestion.backfill", "--days", "400"]
ENTRYPOINT ["python"]
# Default daily ingestion
CMD ["-m", "ingestion.main"]

