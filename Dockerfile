FROM python:3.11-slim

WORKDIR /app

# Install archive tools
# Добавляем non-free репозиторий для unrar-nonfree
RUN sed -i 's/deb \(.*\) main/deb \1 main contrib non-free/g' /etc/apt/sources.list 2>/dev/null || \
    sed -i 's/deb \(.*\) main/deb \1 main contrib non-free/g' /etc/apt/sources.list.d/*.sources 2>/dev/null || \
    echo "deb http://deb.debian.org/debian/ $(cat /etc/os-release | grep VERSION_CODENAME | cut -d= -f2) main contrib non-free" >> /etc/apt/sources.list 2>/dev/null || true && \
    apt-get update && \
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

