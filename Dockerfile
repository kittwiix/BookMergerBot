FROM python:3.11-slim

WORKDIR /app

# Install archive tools
# Пытаемся установить unrar-nonfree, если не получается - используем unrar-free
RUN apt-get update && \
    (apt-get install -y unrar-nonfree 2>/dev/null || \
     apt-get install -y unrar-free 2>/dev/null || \
     echo "unrar не установлен, поддержка RAR будет отключена") && \
    apt-get install -y \
    unzip \
    p7zip-full \
 && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project sources
COPY . .

# Run bot
CMD ["python", "-m", "src.main"]

