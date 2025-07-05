FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

# Зробити entrypoint скрипт виконуваним
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Використовувати entrypoint скрипт
ENTRYPOINT ["/app/docker-entrypoint.sh"] 