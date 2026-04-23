# AR Microservice Documentation

This folder documents the dedicated 3D / AR generator service used by the Framing App.

The service is implemented in:

- `ar-generator-service/server.py`

It is responsible for:

- generating `GLB` and `USDZ` files
- storing model files and metadata
- exposing a public 3D viewer page
- serving generated model files

It is not responsible for:

- storefront widget UI
- Shopify app proxy auth
- frame catalogue lookup
- quote calculation

Those concerns stay in the main app or in external Direct.Art services.

## Documents in this folder

- `architecture.md`: service role, boundaries, request flow, public/private surfaces
- `direct-file-integration.md`: how to use direct GLB/USDZ file URLs instead of the hosted viewer page
- `generation-pipeline.md`: how 3D assets are produced from the canvas snapshot
- `viewer-and-delivery.md`: viewer HTML, file hosting, public URL rules
- `endpoints.md`: all microservice endpoints in one place
- `integration-direct-art-platform.md`: how to integrate this service behind the Direct.Art platform API

## Quick summary

### Private surface

- `POST /api/ar/generate-model`

This route is protected by `AR_GENERATOR_SERVICE_TOKEN`.

### Public surface

- `GET /health`
- `GET /ar-viewer?modelId=...`
- `GET /api/ar/model/:id`
- `GET /api/ar/files/:id/:fileType`
- `GET /api/ar/models/:id?fileType=glb|usdz` (legacy-compatible)

### Current hosting model

The intended runtime topology is:

```text
storefront widget
  -> Shopify/Direct.Art backend API
    -> AR microservice (token-authenticated POST)
browser
  -> AR microservice viewer/files (public GET)
```

That keeps the generation token on the server side while allowing 3D/AR pages and files to be loaded directly from the microservice domain.
