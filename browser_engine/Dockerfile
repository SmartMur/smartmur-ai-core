FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2t64 \
    libxshmfence1 \
    libx11-xcb1 \
    libxcb1 \
    fonts-liberation \
    fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    fastapi>=0.110 \
    uvicorn>=0.27 \
    playwright>=1.40 \
    pydantic>=2.0

# Install Playwright browsers (Chromium only for smaller image)
RUN playwright install chromium

# Copy application
COPY browser_engine/ browser_engine/

# Create data directory for profiles
RUN mkdir -p /data/browser/profiles

EXPOSE 8300

CMD ["uvicorn", "browser_engine.app:app", "--host", "0.0.0.0", "--port", "8300"]
