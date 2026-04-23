# Integrating the AR Microservice into the Direct.Art Platform API

## Goal

The recommended Direct.Art platform integration is:

- Direct.Art platform API owns the authenticated generation endpoint
- AR microservice owns the actual 3D/AR generation and all public viewer/file pages

In other words:

```text
Direct.Art client
  -> Direct.Art platform API
    -> AR microservice
Browser
  -> AR microservice viewer/files
```

This is the same architecture already used by the Shopify app and is the cleanest model if you do not want to expose the generation token to the frontend.

## Recommended contract split

### Direct.Art platform API should own

- request authentication and rate limiting
- request validation
- business rules
- seller/account-level authorization
- calling the AR microservice with the secret token
- returning the resulting metadata to clients

### AR microservice should own

- actual model generation
- model storage
- public 3D viewer page
- public file serving for `GLB` and `USDZ`

## Required microservice configuration

On the AR service:

```bash
AR_GENERATOR_SERVICE_TOKEN=super-secret
AR_SERVICE_PUBLIC_BASE_URL=https://ar.direct.art
AR_SERVICE_MODELS_DIR=/persistent/path/to/models
AR_SERVICE_PORT=3003
```

## Required Direct.Art platform API configuration

On the Direct.Art backend service:

```bash
AR_GENERATOR_SERVICE_URL=https://ar.direct.art
AR_GENERATOR_SERVICE_TOKEN=super-secret
AR_GENERATOR_SERVICE_TIMEOUT_MS=120000
```

The token values must match exactly.

## What the Direct.Art platform API route should do

Create a backend route such as:

```text
POST /api/ar/generate-model
```

That route should:

1. authenticate the platform caller
2. validate `imageData`, `frameData`, `artworkData`
3. forward the request to the AR microservice
4. include both:
   - `Authorization: Bearer <token>`
   - `X-AR-Service-Token: <token>`
5. return the microservice payload to the caller

## Why this split is important

If the browser calls the microservice generation route directly:

- you must expose the token
- or leave generation open

Both are bad fits.

By keeping generation behind the Direct.Art platform API:

- the token remains server-side
- you can add your own auth, rate limits, logging, and billing logic
- the browser still gets public `viewerUrl`, `glbUrl`, and `usdzUrl`

## Reference backend flow

### Request from client to platform API

```json
{
  "imageData": "data:image/jpeg;base64,...",
  "frameData": {
    "id": "MOULDING-001",
    "faceWidthMm": 24
  },
  "artworkData": {
    "title": "Artwork title",
    "width_mm": 500,
    "height_mm": 700
  }
}
```

### Platform API forwards to microservice

```http
POST https://ar.direct.art/api/ar/generate-model
Authorization: Bearer super-secret
X-AR-Service-Token: super-secret
Content-Type: application/json
Accept: application/json
```

### Platform API returns to client

```json
{
  "success": true,
  "data": {
    "modelId": "uuid",
    "viewerUrl": "https://ar.direct.art/ar-viewer?modelId=uuid",
    "glbUrl": "https://ar.direct.art/api/ar/files/uuid/glb",
    "usdzUrl": "https://ar.direct.art/api/ar/files/uuid/usdz",
    "dimensions": {
      "width_inches": 23.6,
      "height_inches": 31.5,
      "depth_inches": 0.3
    }
  }
}
```

## Example server-side forwarding logic

Node-style pseudo implementation:

```js
async function generateArModel(req, res) {
  const { imageData, frameData, artworkData } = req.body || {};

  if (!imageData || !frameData || !artworkData) {
    return res.status(400).json({
      error: "Missing required data: imageData, frameData, artworkData",
    });
  }

  const upstream = await fetch(
    `${process.env.AR_GENERATOR_SERVICE_URL}/api/ar/generate-model`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        Authorization: `Bearer ${process.env.AR_GENERATOR_SERVICE_TOKEN}`,
        "X-AR-Service-Token": process.env.AR_GENERATOR_SERVICE_TOKEN,
      },
      body: JSON.stringify({ imageData, frameData, artworkData }),
    },
  );

  const payload = await upstream.json().catch(() => null);
  return res.status(upstream.status).json(payload || { error: "Invalid upstream response" });
}
```

## Important design rule

Do not proxy the viewer and file routes through the Direct.Art platform API unless you have a strong reason.

Current architecture works best when:

- platform API proxies only generation
- browser opens the microservice domain directly for viewer and file delivery

That keeps:

- static asset delivery simpler
- large model file serving out of the main API path
- iframe/QR/mobile behavior consistent

## Public routes that must remain reachable

From browsers and mobile devices, these microservice routes must be publicly reachable:

- `GET /ar-viewer?modelId=...`
- `GET /api/ar/files/:id/glb`
- `GET /api/ar/files/:id/usdz`
- optionally `GET /api/ar/model/:id`

If the platform API returns URLs but these routes are not public, the integration is incomplete.

## Suggested Direct.Art platform route shape

If Direct.Art wants a stable public API surface, a good shape is:

### Platform API

- `POST /api/ar/generate-model`

### Microservice public delivery

- `GET https://ar.direct.art/ar-viewer?...`
- `GET https://ar.direct.art/api/ar/models/...`

This gives clients one stable generation endpoint and one stable delivery domain.

## Observability recommendations

Add logging at the platform API layer for:

- request id
- user/account id
- seller id
- payload size
- upstream latency
- upstream status
- returned model id

The microservice itself is intentionally minimal. The platform layer is the right place for business-level observability.

## Security checklist

- keep `AR_GENERATOR_SERVICE_TOKEN` only on server-side services
- never inject the token into frontend JS
- keep `POST /api/ar/generate-model` behind your platform auth
- use HTTPS for both platform API and AR microservice
- set `AR_SERVICE_PUBLIC_BASE_URL` to the final public AR domain

## Deployment checklist

1. Deploy the AR microservice on its own domain or subdomain.
2. Configure persistent storage for `AR_SERVICE_MODELS_DIR`.
3. Set the shared token on both services.
4. Verify:
   - `GET /health`
   - server-to-server `POST /api/ar/generate-model`
   - browser `GET /ar-viewer?modelId=...`
   - browser `GET /api/ar/files/:id/glb`
   - iOS Quick Look via `usdzUrl`

## Recommended future improvement

If Direct.Art platform wants stronger lifecycle control later, the next architectural step is:

- keep metadata in the platform database
- move binary files from local filesystem to object storage

But that is an infrastructure improvement, not a blocker for the current integration model.
