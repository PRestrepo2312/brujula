# Etapa 1: el front Angular se compila dentro de la imagen (build reproducible, sin pasos a mano).
# Se sirve desde la misma Lambda en /app, así que no necesita CloudFront ni dominio.
FROM node:22-alpine AS front
WORKDIR /front
COPY front/package.json front/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY front/ ./
RUN npm run build -- --configuration production --base-href /app/

# Etapa 2: el servicio Python.
FROM python:3.12-slim
# Lambda Web Adapter: la misma imagen corre en Lambda (Function URL) y en cualquier contenedor normal.
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.0 /lambda-adapter /opt/extensions/lambda-adapter
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080 AWS_LWA_READINESS_CHECK_PATH=/healthz
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY brujula ./brujula
COPY cli.py icp.json ./
COPY --from=front /front/dist/front/browser ./front_dist
RUN mkdir -p data
EXPOSE 8080
CMD ["sh", "-c", "uvicorn brujula.web.app:app --host 0.0.0.0 --port ${PORT}"]
