FROM python:3.11-slim

# Security: run as non-root user
RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY --chown=app:app . .

# Never bake secrets into the image — all secrets come from env vars at runtime
# Remove any .env if accidentally included in build context
RUN rm -f .env

# Ensure data directory exists and is writable by app user
RUN mkdir -p data && chown app:app data

USER app

EXPOSE 8000

# Use 2 workers in production; adjust based on your plan's RAM
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
