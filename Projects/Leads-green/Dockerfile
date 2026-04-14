# Green Landscape AI Lead Engine — FastAPI container
# Uses Microsoft Playwright base image for scraper support
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /app

# Install Python dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY src/ src/
COPY tools/ tools/
COPY schema.sql .
COPY .env.example .

# Default port — override with PORT env var if needed
EXPOSE 8001

# 2 workers: enough for VPS, keeps memory predictable
CMD ["uvicorn", "src.api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8001", \
     "--workers", "2", \
     "--log-level", "info"]
