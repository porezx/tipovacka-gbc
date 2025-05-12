FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt . 
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Bind to whatever port Cloud Run sets (default 8080)
CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:${PORT:-8080}"]
