FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Note: Playwright is optional - only needed for Xiaohongshu HTML cards
# Uncomment below if you need XHS cards feature:
# RUN pip install playwright && playwright install chromium

# Copy PostAll source code
COPY postall/ ./postall/
COPY pyproject.toml .
COPY README.md .

# Install PostAll
RUN pip install -e .

# Create directories for project data
RUN mkdir -p /app/projects /app/output /app/database /app/logs /app/backups

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default command (will be overridden by docker-compose)
CMD ["python", "-m", "postall.cli", "daemon"]
