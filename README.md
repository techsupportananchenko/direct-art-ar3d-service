# AR Generator Service

Separate Python service for AR model generation. This isolates the GLB/USDZ compute pipeline from the Remix app, which is useful when the Shopify app is deployed on Vercel and the generator runs elsewhere.

## Run locally

```bash
python3 -m pip install -r requirements.txt
python3 server.py
```

The service listens on `http://localhost:3003` by default.

## Environment

- `AR_SERVICE_PORT`: service port. Default: `3003`
- `PORT`: Render-compatible fallback port for web services
- `AR_SERVICE_MODELS_DIR`: directory for generated files and metadata. In production this must live on persistent disk/storage.
- `AR_SERVICE_PUBLIC_BASE_URL`: public base URL used in returned `viewerUrl`, `glbUrl`, and `usdzUrl`
- `AR_GENERATOR_SERVICE_TOKEN`: shared bearer token for app-to-service auth. It must match the Remix app value.
- `AR_SERVICE_GENERATOR_MODULES_DIR`: optional absolute or relative path to the folder that contains `enhanced_ar_server.py` and `enhanced_create_usdz.py`

The service auto-loads parent `.env`, parent `.env.local`, local `.env`, and local `.env.local` if present. Explicit shell env vars still win.

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

## Render Deploy

Yes, this project can be deployed to Render as a `Web Service`.

Important before deploy:

- this repo must contain the generator modules, usually under `Shopify/`
- or you must point `AR_SERVICE_GENERATOR_MODULES_DIR` to a directory that contains `enhanced_ar_server.py` and `enhanced_create_usdz.py`
- for production you need a persistent disk, because generated `.glb`, `.usdz`, and `.json` files are stored on the filesystem

Recommended file layout for this repo:

```text
direct-art-ar3d-service/
  server.py
  render.yaml
  Shopify/
    enhanced_ar_server.py
    enhanced_create_usdz.py
```

This repo now includes [`render.yaml`](/Users/admin/Desktop/Stellar Soft/direct-art-ar3d-service/render.yaml). The intended setup is:

- runtime: Python web service
- build command: `pip install -r requirements.txt`
- start command: `python server.py`
- health check: `/health`
- generator modules dir: `./Shopify`
- disk mount: `/opt/render/project/src/data/models`

If you use a custom domain such as `https://ar.direct.art`, set:

```bash
AR_SERVICE_PUBLIC_BASE_URL=https://ar.direct.art
```

If you do not set it, the service falls back to Render request headers and `RENDER_EXTERNAL_HOSTNAME`.

## Wrapper Architecture On Render

Render wrapper usually means a second backend service in front of this microservice.

Recommended split:

- this repo on Render = public AR microservice
- your main API on Render or elsewhere = private wrapper for `POST /api/ar/generate-model`

The wrapper should:

- authenticate the caller
- validate the payload
- call this microservice with `Authorization: Bearer <AR_GENERATOR_SERVICE_TOKEN>`
- return the generated `viewerUrl`, `glbUrl`, and `usdzUrl`

The browser should open viewer and model URLs directly from the AR microservice domain. Do not proxy model files through the wrapper unless you explicitly need that.

## Production notes

- Use a stable public domain for `AR_SERVICE_PUBLIC_BASE_URL`
- Store `AR_SERVICE_MODELS_DIR` on persistent storage; local ephemeral disk is not sufficient for production
- Restart the microservice after changing `.env` values such as `AR_GENERATOR_SERVICE_TOKEN` or `AR_SERVICE_PUBLIC_BASE_URL`
