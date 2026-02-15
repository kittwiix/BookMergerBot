FROM python:3.11-slim

WORKDIR /app

# Install archive tools
# Пытаемся установить unrar (nonfree или free версию)
RUN apt-get update && \
    apt-get install -y unzip p7zip-full && \
    (apt-get install -y unrar-nonfree || \
     apt-get install -y unrar-free || \
     echo "unrar недоступен, поддержка RAR будет отключена") && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project sources
COPY . .

# Run bot
CMD ["python", "-m", "src.main"]

