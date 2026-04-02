# 3D and AR Generation Pipeline

## Input contract

The microservice receives three logical inputs:

```json
{
  "imageData": "data:image/jpeg;base64,...",
  "frameData": { "...": "..." },
  "artworkData": { "...": "..." }
}
```

### `imageData`

This is the primary visual source.

In the current storefront flow it is not the raw Shopify artwork file.
It is a serialized snapshot of the already rendered framing preview canvas.

That matters because the canvas snapshot already includes:

- selected frame look
- selected mount look
- selected borders
- glazing-driven visible preview result

So the 3D model is generated from the final visual state the customer saw in the widget.

## Stage 1. Input normalization

Inside `server.py`, the service normalizes:

- frame width
- frame depth
- artwork width
- artwork height
- depth

### Artwork dimensions

The service resolves artwork size from `artworkData` using this preference order:

- `calculated_width_mm` / `calculated_height_mm`
- `width_mm` / `height_mm`
- `widthMm` / `heightMm`

If one side is missing, it reconstructs it from aspect ratio.

If both sides are missing, it falls back to a default size:

```text
1000 mm
```

with the aspect ratio preserved when possible.

### Aspect ratio

Aspect ratio is resolved from:

- explicit fields such as `natural_aspect`, `aspectRatio`, `aspect_ratio`
- or derived from width/height
- or final fallback `1`

### Frame width

Frame width is resolved from `frameData` using several aliases, with default:

```text
24 mm
```

### Depth

Depth is dynamically calculated in `server.py`.

Current defaults and clamps:

- default depth: `8 mm`
- minimum: `6 mm`
- maximum: `12 mm`

Depth sources:

1. explicit frame depth from `frameData`
2. derived frame depth from `frameWidthMm * 0.30`
3. padded artwork depth if available
4. default fallback

Artwork depth, when present, gets an extra:

```text
2 mm
```

padding before clamping.

## Stage 2. Final physical model dimensions

The service computes:

- `totalWidthMm = artworkWidthMm + frameWidthMm * 2`
- `totalHeightMm = artworkHeightMm + frameWidthMm * 2`
- `depthMeters`

Those values are converted to:

- millimeters for metadata
- meters for generator functions
- inches for viewer display

## Stage 3. GLB generation

### Source

- `Shopify/enhanced_ar_server.py`
- entry function: `create_enhanced_3d_glb_from_image(...)`

### What the GLB generator does

1. decodes `imageData`
2. converts to RGB if needed
3. saves the front texture as high-quality JPEG
4. creates a synthetic side texture by sampling edge pixels from the image
5. creates a synthetic back panel texture with dark brown cardboard noise
6. builds a glTF binary mesh with:
   - front panel
   - back panel
   - 4 side panels
   - reverse faces for solid rendering
7. packages three materials:
   - front material
   - back material
   - side material
8. embeds textures directly inside the GLB

### Geometry features currently encoded

- recessed artwork surface
- real side faces
- back panel
- thin overall depth
- separate materials per face group

Current constants inside the generator:

- recess depth: `2 mm`
- lip size constant exists in code, but current mesh implementation is effectively centered on front/back/side surfaces rather than a fully separate lip mesh

### Texture strategy

The model does not rely on a separately authored side texture asset from the frame catalogue.

Instead it synthesizes side texture from the input image edges, which gives the generated model a visually continuous side surface.

## Stage 4. USDZ generation

### Source

- `Shopify/enhanced_create_usdz.py`
- entry function: `create_enhanced_3d_usdz_from_image(...)`

### What the USDZ generator does

1. creates a temporary working directory
2. decodes the input image
3. writes:
   - `front_texture.jpg`
   - `side_texture.jpg`
   - `back_texture.jpg`
4. writes an ASCII USD scene file describing:
   - front panel
   - back panel
   - four side panels
   - reverse faces
   - three bound materials
5. packages the USD scene and textures into a USDZ archive
6. removes the temporary directory

### Why temporary files are required here

Unlike the GLB builder, the USDZ packaging flow naturally writes intermediate USD and texture assets before zipping them into the final archive.

This is one reason the service is better suited to a dedicated runtime than to a strictly stateless edge/serverless path.

## Stage 5. File validation

After generation, `server.py` validates that:

- GLB file exists
- USDZ file exists
- each file is larger than `1000` bytes

If validation fails, the request is treated as generation failure.

## Stage 6. Metadata creation

The service writes `<modelId>.json` containing:

- `id`
- `modelId`
- `title`
- `frameName`
- `dimensions`
- `frameData`
- `artworkData`
- `enhancedFeatures`
- `glbUrl`
- `usdzUrl`
- `viewerUrl`

This metadata file is then used by:

- `GET /api/ar/model/:id`
- `GET /ar-viewer?modelId=...`

## Stage 7. Delivery behavior

After generation succeeds:

- the API returns metadata immediately
- the browser can open `viewerUrl`
- the browser can request `glbUrl`
- iOS Safari can request `usdzUrl`

## Important rendering distinction: 3D vs AR

### 3D preview

Uses:

- `viewerUrl`
- internally loads `glbUrl`
- displayed in `<model-viewer>`

### Native AR

Uses:

- `usdzUrl` for iOS Safari Quick Look
- `viewerUrl` for mobile browser flow and fallback paths

So the same generation request supports both:

- embedded desktop/mobile 3D preview
- mobile AR handoff

## Known production considerations

- local filesystem storage is fine for dev, weak for production
- the service needs persistent disk or an object-storage rewrite later
- `Pillow` is required by both generators
- public URL config must be correct, otherwise the generated files exist but cannot be opened correctly by the browser
