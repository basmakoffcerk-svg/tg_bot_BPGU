FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    sqlite3 \
    tzdata \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Timezone configuration
ENV TZ=Europe/Minsk
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ensure data directories exist
RUN mkdir -p /app/data /app/data/backups

EXPOSE 8000

CMD ["python", "main.py"]
