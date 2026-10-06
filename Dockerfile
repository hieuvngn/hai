# Fashion Chatbot — backend FastAPI + static frontend (single image, single origin)
# Build:  docker build -t fashion-chatbot .
# Chạy:   docker run -p 8000:8000 --env-file .env -v $(pwd)/backend/data:/app/backend/data fashion-chatbot
FROM python:3.11-slim AS backend

WORKDIR /app/backend

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/scripts ./scripts

# Frontend được build sang static rồi serve cùng origin (KHÔNG cần CORS)
FROM node:20-alpine AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app/backend
COPY --from=backend /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend /usr/local/bin /usr/local/bin
COPY --from=backend /app/backend ./
COPY --from=frontend /fe/dist /app/static

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]
