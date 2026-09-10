FROM node:22-alpine AS frontend
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY index.html tsconfig.json vite.config.ts ./
COPY src ./src
COPY scripts/build.mjs ./scripts/build.mjs
COPY public ./public
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/app/data
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd -m -u 10001 appuser
COPY backend ./backend
COPY public ./public
COPY --from=frontend /app/dist ./dist
RUN mkdir -p /app/data && chown -R appuser:appuser /app/data
USER appuser
EXPOSE 8000
CMD ["uvicorn","backend.main:app","--host","0.0.0.0","--port","8000"]
