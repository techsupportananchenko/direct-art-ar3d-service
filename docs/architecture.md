# AR Microservice Architecture

## Source of truth

- `ar-generator-service/server.py`

## Why this service exists

The main app is a Shopify-facing web app.

The AR service exists to isolate:

- Python-based 3D generation
- model file storage
- public 3D/AR surfaces

from the main app runtime.

This is especially important when the main app is deployed on platforms such as Vercel, where keeping compute-heavy generation and persistent model files inside the same runtime is a poor fit.

## Responsibilities

### Owned by the microservice

- accept generation payloads
- authenticate generation requests with a shared secret
- calculate real model dimensions
- generate `GLB`
- generate `USDZ`
- write model metadata
- host a public 3D viewer page
- serve model files

### Not owned by the microservice

- storefront widget logic
- Shopify authentication
- quote pricing
- frame/mount catalogue lookup
- cart integration

## Surface split

The service has two different surfaces.

### 1. Private generation surface

`POST /api/ar/generate-model`

This route is server-to-server and requires the shared secret token unless the token is empty.

### 2. Public delivery surface

These routes are intentionally public:

- `GET /health`
- `GET /ar-viewer`
- `GET /api/ar/model/:id`
- `GET /api/ar/models/:id`

This is by design, because browsers and iframes need to open the returned `viewerUrl`, `glbUrl`, and `usdzUrl` directly.

## Auth model

Current rule in `server.py`:

- all `GET` and `HEAD` requests are public
- `POST` requires token if `AR_GENERATOR_SERVICE_TOKEN` is configured

Accepted auth headers:

- `Authorization: Bearer <token>`
- `X-AR-Service-Token: <token>`

This dual-header support is deliberate and makes the service more tolerant of intermediate proxies or tunnels that may strip `Authorization`.

## Request flow

### Current app integration

```text
Widget
  -> POST /apps/da-framing/api/ar/generate-model
App
  -> POST AR service /api/ar/generate-model
AR service
  -> writes .glb, .usdz, .json metadata
App
  -> returns normalized URLs
Widget
  -> opens viewerUrl / glbUrl / usdzUrl on the microservice domain
```

### Desired Direct.Art platform integration

```text
Direct.Art client
  -> Direct.Art platform API
Direct.Art platform API
  -> POST AR service /api/ar/generate-model with token
AR service
  -> returns model metadata and public URLs
Direct.Art platform API
  -> returns those URLs to client
Client
  -> opens viewer/files directly from AR microservice domain
```

## Storage model

Default storage is the local filesystem under:

```text
ar-generator-service/data/models
```

Generated artifacts per model:

- `<modelId>.glb`
- `<modelId>.usdz`
- `<modelId>.json`

The `.json` metadata file acts as the registry record for:

- title
- frame name
- dimensions
- URLs
- raw `frameData`
- raw `artworkData`

## Public URL strategy

Returned public URLs are built from:

1. `AR_SERVICE_PUBLIC_BASE_URL`, if set
2. otherwise `X-Forwarded-Host` + `X-Forwarded-Proto`
3. otherwise current `Host` header and local port fallback

This is critical because the service must generate browser-usable public URLs even when running behind ngrok, reverse proxies, or production gateways.

## Environment contract

### Core env vars

- `AR_SERVICE_PORT`
- `AR_SERVICE_MODELS_DIR`
- `AR_SERVICE_PUBLIC_BASE_URL`
- `AR_GENERATOR_SERVICE_TOKEN`

### Auto-loaded env files

The service loads, in this order:

- project root `.env`
- project root `.env.local`
- `ar-generator-service/.env`

Explicit process env still wins over file-loaded values.

## Failure boundary

The service is intentionally self-contained:

- if generation fails, it cleans up partial model files
- if metadata is missing, viewer and model lookup fail cleanly
- if public URL config is wrong, generation may still succeed but browser delivery will break

That means generation success and public delivery correctness are related but not the same thing.
