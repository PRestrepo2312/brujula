#!/usr/bin/env bash
# Front Angular: crea (una vez) S3 + CloudFront, construye con ng build, sube los archivos e invalida la caché.
# Uso: PERFIL=brujula REGION=us-east-1 API_URL=https://xxxx.lambda-url.us-east-1.on.aws ./deploy/front.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PERFIL="${PERFIL:-brujula}"
REGION="${REGION:-us-east-1}"

aws cloudformation deploy --profile "$PERFIL" --region "$REGION" --stack-name brujula-front --template-file deploy/front.yml
BUCKET=$(aws cloudformation describe-stacks --profile "$PERFIL" --region "$REGION" --stack-name brujula-front --query "Stacks[0].Outputs[?OutputKey=='BucketFront'].OutputValue" --output text)
DIST=$(aws cloudformation describe-stacks --profile "$PERFIL" --region "$REGION" --stack-name brujula-front --query "Stacks[0].Outputs[?OutputKey=='DistribucionId'].OutputValue" --output text)
URL=$(aws cloudformation describe-stacks --profile "$PERFIL" --region "$REGION" --stack-name brujula-front --query "Stacks[0].Outputs[?OutputKey=='UrlFront'].OutputValue" --output text)
echo "Front: $URL"

# La configuración del front (API, Cognito) se escribe en front/public/config.json antes de construir.
if [ -n "${API_URL:-}" ]; then
  POOL=$(aws cloudformation describe-stacks --profile "$PERFIL" --region "$REGION" --stack-name brujula-cognito --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" --output text 2>/dev/null || echo "")
  CLIENTE=$(aws cloudformation describe-stacks --profile "$PERFIL" --region "$REGION" --stack-name brujula-cognito --query "Stacks[0].Outputs[?OutputKey=='ClientId'].OutputValue" --output text 2>/dev/null || echo "")
  DOMINIO=$(aws cloudformation describe-stacks --profile "$PERFIL" --region "$REGION" --stack-name brujula-cognito --query "Stacks[0].Outputs[?OutputKey=='Domain'].OutputValue" --output text 2>/dev/null || echo "")
  mkdir -p front/public
  printf '{"apiUrl":"%s","cognito":{"domain":"%s","clientId":"%s","userPoolId":"%s","region":"%s"},"frontUrl":"%s"}\n' \
    "${API_URL%/}" "$DOMINIO" "$CLIENTE" "$POOL" "$REGION" "$URL" > front/public/config.json
fi

(cd front && npm run build -- --configuration production)
aws s3 sync front/dist/front/browser "s3://$BUCKET" --delete --profile "$PERFIL" --region "$REGION"
aws cloudfront create-invalidation --distribution-id "$DIST" --paths "/*" --profile "$PERFIL" --region "$REGION" >/dev/null
echo "Listo: $URL  (agregue $URL/callback a la pila brujula-cognito con FrontCallbackUrl y a CORS_ORIGINS de la pila brujula)"
