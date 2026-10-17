#!/usr/bin/env bash
# Despliegue de Brújula en AWS: ECR (imagen) + CloudFormation (App Runner, RDS, Secrets Manager, S3, EventBridge).
# Uso: PERFIL=brujula REGION=us-east-1 ./deploy/deploy.sh
# Lee las claves de .env (DAPTA_API_KEY, OPENROUTER_API_KEY, RESEND_API_KEY, EMAIL_FROM) y pide DB_PASSWORD y CRON_KEY si no están.
set -euo pipefail
cd "$(dirname "$0")/.."
PERFIL="${PERFIL:-brujula}"
REGION="${REGION:-us-east-1}"
REPO="brujula"
TAG="${TAG:-$(date +%Y%m%d%H%M)}"
PILA="brujula"

set -a; [ -f .env ] && . ./.env; set +a
: "${DB_PASSWORD:?Defina DB_PASSWORD (12+ caracteres)}"
: "${CRON_KEY:?Defina CRON_KEY (16+ caracteres)}"

CUENTA=$(aws sts get-caller-identity --profile "$PERFIL" --query Account --output text)
ECR="$CUENTA.dkr.ecr.$REGION.amazonaws.com"
aws ecr describe-repositories --repository-names "$REPO" --profile "$PERFIL" --region "$REGION" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "$REPO" --profile "$PERFIL" --region "$REGION" >/dev/null
aws ecr get-login-password --profile "$PERFIL" --region "$REGION" | docker login --username AWS --password-stdin "$ECR"
docker build --platform linux/amd64 -t "$REPO:$TAG" .
docker tag "$REPO:$TAG" "$ECR/$REPO:$TAG"
docker push "$ECR/$REPO:$TAG"

aws cloudformation deploy --profile "$PERFIL" --region "$REGION" --stack-name "$PILA" --template-file deploy/cloudformation.yml \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides ImageUri="$ECR/$REPO:$TAG" DbPassword="$DB_PASSWORD" CronKey="$CRON_KEY" \
    DaptaApiKey="${DAPTA_API_KEY:-}" OpenRouterApiKey="${OPENROUTER_API_KEY:-}" ResendApiKey="${RESEND_API_KEY:-}" EmailFrom="${EMAIL_FROM:-Brújula <hola@example.com>}"

aws cloudformation describe-stacks --profile "$PERFIL" --region "$REGION" --stack-name "$PILA" --query 'Stacks[0].Outputs' --output table
echo "Después: ponga la URL de salida como PUBLIC_BASE_URL (webhook de Dapta y enlaces de correo) y vuelva a correr cli.py dapta-setup si cambió."
