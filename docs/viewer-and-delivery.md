# Viewer and Delivery Surface

## Viewer route

- `GET /ar-viewer?modelId=...`

## What the viewer does

The viewer is a self-contained HTML page rendered directly by `server.py`.

It is not a React app and not part of the Remix app.

It renders:

- a `<model-viewer>` element loaded from unpkg
- optional header and close button in non-embed mode
- model info such as title, frame name, and dimensions

## Viewer modes

### Standalone mode

Default when `embed` is not set.

Intended for:

- opening a separate page for 3D/AR
- QR-code target URLs
- mobile browser viewer pages

### Embed mode

Enabled with:

```text
embed=1
```

Intended for:

- iframe rendering inside the storefront widget

Changes in embed mode:

- no outer chrome/header
- tighter padding
- full-height viewer section

## Query parameters supported by the viewer

### Required

- `modelId`

### Optional metadata overrides

- `title`
- `frameName`
- `widthInches`
- `heightInches`
- `depthInches`

### Optional theme overrides

- `pageBg`
- `pageBgAlt`
- `surfaceColor`
- `textColor`
- `textMutedColor`
- `borderColor`

These are used by the storefront widget so the iframe viewer visually matches the theme block colors.

## Model source inside viewer

The page builds `<model-viewer>` with:

- `src = glbUrl`
- `ios-src = usdzUrl` when available
- `ar` attribute only when `usdzUrl` exists

That means:

- desktop and most browser 3D uses `GLB`
- iOS AR-capable flow can use `USDZ`

## Public file delivery

### `GET /api/ar/files/:id/glb`

Returns:

- content type: `model/gltf-binary`
- cache control: `public, max-age=31536000, immutable`

### `GET /api/ar/files/:id/usdz`

Returns:

- content type: `model/vnd.usdz+zip`
- same aggressive public caching

### `GET /api/ar/model/:id`

Returns the JSON metadata record for the model.

## Why delivery is public

The browser needs to load:

- iframe viewer
- `GLB`
- `USDZ`

directly from the microservice domain.

If these routes required a secret token, the storefront widget would have to expose that token to the browser, which is explicitly not desired.

## URL normalization behavior

The service can rebuild public URLs on read using `with_public_urls()`.

That means even older metadata files can still be served with corrected:

- `glbUrl`
- `usdzUrl`
- `viewerUrl`

based on the current request host or configured public base URL.

## Recommended production URL strategy

Set:

```text
AR_SERVICE_PUBLIC_BASE_URL=https://your-ar-domain.example.com
```

This avoids problems with:

- mixed content
- incorrect localhost URLs
- temporary tunnel host leakage
- inconsistent host reconstruction behind proxies

## Cross-origin behavior

The service sends:

- `Access-Control-Allow-Origin: *`
- `Cross-Origin-Resource-Policy: cross-origin` for model files

This is intentional and allows:

- storefront iframe embedding
- cross-origin model fetches by the viewer
- QR links opened outside the Shopify domain

## Delivery risks to watch

- wrong `AR_SERVICE_PUBLIC_BASE_URL`
- public host mismatch behind reverse proxy
- non-persistent storage deleting models after generation
- CDN/proxy rewriting content types incorrectly

If generation succeeds but viewer opens empty or model fetches fail, this delivery layer is the first place to inspect.

## Backward compatibility

The older query-param file route is still supported:

- `GET /api/ar/models/:id?fileType=glb`
- `GET /api/ar/models/:id?fileType=usdz`
