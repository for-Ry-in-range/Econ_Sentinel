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

# Daily job runs by default
ENTRYPOINT ["python"]
CMD ["-m", "ingestion.main"]
