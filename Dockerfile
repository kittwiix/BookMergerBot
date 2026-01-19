FROM python:3.11-slim

WORKDIR /app

# Install all required archive tools
RUN apt-get update && apt-get install -y \
    unrar \
    unzip \
    p7zip-full \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]