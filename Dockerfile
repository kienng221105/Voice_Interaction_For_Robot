FROM python:3.12-slim

# Build tools for llama-cpp-python
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./backend/

# Download the GGUF model from Google Drive
RUN pip install --no-cache-dir gdown && \
    gdown "1ky7b68l8cnA7goJUK7ZEvVVjKK2rZ-6E" -O ./model.gguf
ENV MODEL_PATH=/app/model.gguf

# Default port for GCP Cloud Run
ENV PORT=8080
EXPOSE 8080

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
