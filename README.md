# AR Generator Service

Separate Python service for AR model generation. This isolates the GLB/USDZ compute pipeline from the Remix app, which is useful when the Shopify app is deployed on Vercel and the generator runs elsewhere.

## Run locally

From the project root:

```bash
python3 -m pip install -r ar-generator-service/requirements.txt
python3 ar-generator-service/server.py
```

From the `ar-generator-service` directory:

```bash
python3 -m pip install -r requirements.txt
python3 server.py
```

The service listens on `http://localhost:3003` by default.

## Environment

- `AR_SERVICE_PORT`: service port. Default: `3003`
- `AR_SERVICE_MODELS_DIR`: directory for generated files and metadata. In production this must live on persistent disk/storage.
- `AR_SERVICE_PUBLIC_BASE_URL`: public base URL used in returned `viewerUrl`, `glbUrl`, and `usdzUrl`
- `AR_GENERATOR_SERVICE_TOKEN`: shared bearer token for app-to-service auth. It must match the Remix app value.

The service auto-loads `/Framing-App/.env`, `/Framing-App/.env.local`, and `ar-generator-service/.env` if present. Explicit shell env vars still win.

## API

- `GET /ar-viewer?modelId=...`
- `GET /health`
- `POST /api/ar/generate-model`
- `GET /api/ar/model/:id`
- `GET /api/ar/models/:id?fileType=glb|usdz`

## App integration

Point the Remix app at this service with:

```bash
AR_GENERATOR_SERVICE_URL=http://localhost:3003
AR_GENERATOR_SERVICE_TOKEN=your-shared-secret
```

The intended runtime flow is:

- storefront widget -> Remix app `POST /api/ar/generate-model`
- Remix app -> AR microservice `POST /api/ar/generate-model` with token
- browser -> AR microservice `GET /ar-viewer`, `GET /api/ar/models/...`

So only generation is protected by token. Viewer and model file URLs are public surface owned by the microservice.

## Production notes

- Use a stable public domain for `AR_SERVICE_PUBLIC_BASE_URL`
- Store `AR_SERVICE_MODELS_DIR` on persistent storage; local ephemeral disk is not sufficient for production
- Restart the microservice after changing `.env` values such as `AR_GENERATOR_SERVICE_TOKEN` or `AR_SERVICE_PUBLIC_BASE_URL`
