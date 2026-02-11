FROM python:3.11-slim

WORKDIR /app

# Install archive tools
RUN apt-get update && apt-get install -y \
    unrar \
    unzip \
    p7zip-full \
 && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (requirements.txt лежит в корне репозитория)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project sources
COPY . .

# Run bot
CMD ["python", "-m", "src.main"]


