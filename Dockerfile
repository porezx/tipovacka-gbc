FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pou�ijeme shell formu, aby se $PORT rozbalil:
CMD sh -c 'gunicorn main:app --bind 0.0.0.0:${PORT:-8080}'
