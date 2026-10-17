#!/usr/bin/env bash
# Despliegue de Brújula en AWS: ECR (imagen) + CloudFormation (Lambda con Function URL, RDS, Secrets Manager, S3, EventBridge) + Cognito.
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
# SALTAR_IMAGEN=1 TAG=<etiqueta ya publicada> reutiliza una imagen que ya está en ECR (reanudar un despliegue a medias).
if [ -z "${SALTAR_IMAGEN:-}" ]; then
  aws ecr get-login-password --profile "$PERFIL" --region "$REGION" | docker login --username AWS --password-stdin "$ECR"
  # Lambda solo acepta manifiestos Docker v2 (sin attestations OCI de BuildKit): una sola plataforma, sin provenance ni SBOM.
  docker build --platform linux/amd64 --provenance=false --sbom=false -t "$REPO:$TAG" .
  docker tag "$REPO:$TAG" "$ECR/$REPO:$TAG"
  for intento in 1 2 3 4; do
    if docker push "$ECR/$REPO:$TAG"; then break; fi
    echo "push a ECR falló (intento $intento), reintentando en 15 s"; sleep 15
    [ "$intento" = 4 ] && exit 1
  done
fi

aws cloudformation deploy --profile "$PERFIL" --region "$REGION" --stack-name "$PILA" --template-file deploy/cloudformation.yml \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides ImageUri="$ECR/$REPO:$TAG" DbPassword="$DB_PASSWORD" CronKey="$CRON_KEY" \
    DaptaApiKey="${DAPTA_API_KEY:-}" DaptaAgentId="${DAPTA_AGENT_ID:-}" DaptaSequenceId="${DAPTA_SEQUENCE_ID:-}" DaptaTextAgentId="${DAPTA_TEXT_AGENT_ID:-}" OpenRouterApiKey="${OPENROUTER_API_KEY:-}" ResendApiKey="${RESEND_API_KEY:-}" EmailProvider="${EMAIL_PROVIDER:-ses}" EmailFrom="${EMAIL_FROM:-Brujula <hola@example.com>}" \
    ModoPrueba="${MODO_PRUEBA:-1}" TelefonoPrueba="${TELEFONO_PRUEBA:-}" CorreosPrueba="${CORREOS_PRUEBA:-}" CronLotes="${CRON_LOTES:-ENABLED}" DenueToken="${DENUE_TOKEN:-}" Despliegue="$TAG-$(date +%H%M%S)"

URL=$(aws cloudformation describe-stacks --profile "$PERFIL" --region "$REGION" --stack-name "$PILA" --query "Stacks[0].Outputs[?OutputKey=='Url'].OutputValue" --output text)
URL="${URL%/}"
echo "Servicio: $URL"

# Paso 2: Cognito necesita la URL del servicio, y el servicio necesita los ids de Cognito: dos pasos, una vez.
aws cloudformation deploy --profile "$PERFIL" --region "$REGION" --stack-name brujula-cognito --template-file deploy/cognito.yml \
  --parameter-overrides CallbackUrl="$URL/callback" LogoutUrl="$URL/login" DomainPrefix="${COGNITO_PREFIX:-brujula-jfb}" FrontBaseUrl="${FRONT_BASE_URL:-$URL/app}"
POOL=$(aws cloudformation describe-stacks --profile "$PERFIL" --region "$REGION" --stack-name brujula-cognito --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" --output text)
CLIENTE=$(aws cloudformation describe-stacks --profile "$PERFIL" --region "$REGION" --stack-name brujula-cognito --query "Stacks[0].Outputs[?OutputKey=='ClientId'].OutputValue" --output text)
DOMINIO=$(aws cloudformation describe-stacks --profile "$PERFIL" --region "$REGION" --stack-name brujula-cognito --query "Stacks[0].Outputs[?OutputKey=='Domain'].OutputValue" --output text)
SESION="${SESSION_SECRET:-$(openssl rand -hex 32)}"
aws cloudformation deploy --profile "$PERFIL" --region "$REGION" --stack-name "$PILA" --template-file deploy/cloudformation.yml \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides ImageUri="$ECR/$REPO:$TAG" DbPassword="$DB_PASSWORD" CronKey="$CRON_KEY" \
    DaptaApiKey="${DAPTA_API_KEY:-}" DaptaAgentId="${DAPTA_AGENT_ID:-}" DaptaSequenceId="${DAPTA_SEQUENCE_ID:-}" DaptaTextAgentId="${DAPTA_TEXT_AGENT_ID:-}" OpenRouterApiKey="${OPENROUTER_API_KEY:-}" ResendApiKey="${RESEND_API_KEY:-}" EmailProvider="${EMAIL_PROVIDER:-ses}" EmailFrom="${EMAIL_FROM:-Brujula <hola@example.com>}" \
    ModoPrueba="${MODO_PRUEBA:-1}" TelefonoPrueba="${TELEFONO_PRUEBA:-}" CorreosPrueba="${CORREOS_PRUEBA:-}" CronLotes="${CRON_LOTES:-ENABLED}" DenueToken="${DENUE_TOKEN:-}" Despliegue="$TAG-$(date +%H%M%S)" \
    CognitoUserPoolId="$POOL" CognitoClientId="$CLIENTE" CognitoDomain="$DOMINIO" SessionSecret="$SESION" PublicBaseUrl="$URL" \
    CorsOrigins="${CORS_ORIGINS:-$URL,http://localhost:4200}"

aws cloudformation describe-stacks --profile "$PERFIL" --region "$REGION" --stack-name "$PILA" --query 'Stacks[0].Outputs' --output table
echo "Usuarios: aws cognito-idp admin-create-user --user-pool-id $POOL --username correo --user-attributes Name=email,Value=correo Name=email_verified,Value=true --profile $PERFIL"
echo "Dapta: corra 'python cli.py dapta-setup' con PUBLIC_BASE_URL=$URL para que el webhook post-llamada apunte al servicio."
