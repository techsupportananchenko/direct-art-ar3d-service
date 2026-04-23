# AR Microservice Endpoints

## Base implementation

- `ar-generator-service/server.py`

## Auth summary

| Route | Auth |
| --- | --- |
| `GET /health` | Public |
| `GET /ar-viewer` | Public |
| `POST /api/ar/generate-model` | Shared token if configured |
| `GET /api/ar/model/:id` | Public |
| `GET /api/ar/files/:id/:fileType` | Public |
| `GET /api/ar/models/:id?fileType=...` | Public |

## `GET /health`

### Purpose

Simple service liveness endpoint.

### Response

```json
{
  "ok": true
}
```

### Use cases

- container health checks
- load balancer health probes
- tunnel/public URL verification

## `POST /api/ar/generate-model`

### Purpose

Generate a new model and persist its artifacts.

### Required headers

When `AR_GENERATOR_SERVICE_TOKEN` is configured:

- `Authorization: Bearer <token>`
  or
- `X-AR-Service-Token: <token>`

### Request body

```json
{
  "imageData": "data:image/jpeg;base64,...",
  "frameData": {},
  "artworkData": {}
}
```

### Success response

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "modelId": "uuid",
    "title": "Framed Artwork",
    "frameName": "Selected Frame",
    "dimensions": {
      "width_mm": 600,
      "height_mm": 800,
      "width_inches": 23.62,
      "height_inches": 31.49,
      "depth_mm": 8,
      "depth_inches": 0.31
    },
    "glbUrl": "https://ar-service.example.com/api/ar/files/uuid/glb",
    "usdzUrl": "https://ar-service.example.com/api/ar/files/uuid/usdz",
    "viewerUrl": "https://ar-service.example.com/ar-viewer?modelId=uuid"
  }
}
```

### Errors

- `400` invalid JSON or missing required data
- `401` unauthorized
- `500` generation failure

## `GET /api/ar/model/:id`

### Purpose

Return metadata for a previously generated model.

### Response

Returns the metadata JSON, with URLs normalized to the current public base.

### Typical use cases

- server-side lookup
- client-side inspection/debugging
- future API orchestration

## `GET /api/ar/files/:id/:fileType`

### Purpose

Return the generated binary file itself.

### Path param

- `fileType = glb`
- `fileType = usdz`

### Errors

- `400` missing or invalid `fileType`
- `404` file missing

## `GET /api/ar/models/:id?fileType=glb|usdz`

### Purpose

Legacy-compatible file route. It serves the same binary file as `/api/ar/files/:id/:fileType`.

## `GET /ar-viewer?modelId=...`

### Purpose

Render the public 3D viewer page.

### Notes

- requires a metadata file for the model
- supports `embed=1`
- supports theme override query params
- uses `<model-viewer>` under the hood

## `OPTIONS`

The service also supports:

- `OPTIONS` for CORS/preflight

Allowed headers:

- `Content-Type`
- `Accept`
- `Authorization`
- `X-AR-Service-Token`
