# Direct File Integration

## Goal

Use the AR microservice as a file source for `3D` and `AR` assets without redirecting the user to the microservice viewer page.

In this flow:

- your backend triggers generation
- your frontend receives file URLs
- your frontend opens or embeds those files directly
- `viewerUrl` is not used

## Use these URLs

After successful generation, the microservice returns:

- `data.modelId`
- `data.glbUrl`
- `data.usdzUrl`
- `data.viewerUrl`

For direct file integration, use:

- `glbUrl` for 3D viewers
- `usdzUrl` for iPhone/iPad Safari Quick Look

Ignore `viewerUrl` unless you explicitly want the hosted viewer page.

## Recommended architecture

```text
Frontend
  -> your backend
Your backend
  -> POST /api/ar/generate-model
AR microservice
  -> returns modelId + glbUrl + usdzUrl
Your backend
  -> returns those URLs to frontend
Frontend
  -> loads glbUrl/usdzUrl directly
```

## Generation request

Your backend should call:

```text
POST /api/ar/generate-model
```

with:

```json
{
  "imageData": "data:image/jpeg;base64,...",
  "frameData": {},
  "artworkData": {}
}
```

## File delivery routes

Current canonical file routes:

- `GET /api/ar/files/:modelId/glb`
- `GET /api/ar/files/:modelId/usdz`

Legacy-compatible routes still work:

- `GET /api/ar/models/:modelId?fileType=glb`
- `GET /api/ar/models/:modelId?fileType=usdz`

## Frontend usage

### Web 3D viewer

Use `glbUrl` as the `src` of your viewer component.

Example with `<model-viewer>`:

```html
<model-viewer
  src="https://ar.example.com/api/ar/files/<modelId>/glb"
  camera-controls
  auto-rotate
></model-viewer>
```

### iOS native AR

On iPhone/iPad Safari, open `usdzUrl`.

Example:

```js
window.location.href = usdzUrl;
```

That will hand off to Quick Look instead of opening the hosted viewer page.

## Best practice

- store `modelId` in your database
- also store `glbUrl` and `usdzUrl` returned at generation time
- do not try to reconstruct files later without a stable key
- do not expose the generation token in frontend code

## Recommended backend response

Return only what the frontend needs:

```json
{
  "modelId": "uuid",
  "glbUrl": "https://ar.example.com/api/ar/files/uuid/glb",
  "usdzUrl": "https://ar.example.com/api/ar/files/uuid/usdz"
}
```

## Fallback lookup

If your frontend later has only `modelId`, it can still request:

```text
GET /api/ar/model/:modelId
```

and read `glbUrl` / `usdzUrl` from metadata.

## What not to do

- do not use `viewerUrl` when you need the raw file
- do not proxy large binary files through your main API unless you need access control there
- do not drop `modelId` after generation if you will need the file again later
