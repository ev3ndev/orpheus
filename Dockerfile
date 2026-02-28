FROM python:3.12-slim

RUN apt-get update && apt-get install -y supervisor prometheus && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY supervisord.conf .
COPY orpheus.py .
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /var/log/supervisor

COPY prometheus.yml /etc/prometheus/prometheus.yml
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
