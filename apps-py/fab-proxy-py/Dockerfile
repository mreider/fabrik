FROM python:3.11-slim

WORKDIR /app

# Copy service files
COPY fab-proxy-py/requirements.txt requirements.txt
COPY fab-proxy-py/app.py app.py

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "app:app"]
