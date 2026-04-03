Place the generator modules for the Render AR service in this directory:

- `enhanced_ar_server.py`
- `enhanced_create_usdz.py`

Expected final structure:

```text
direct-art-ar3d-service/
  server.py
  render.yaml
  Shopify/
    enhanced_ar_server.py
    enhanced_create_usdz.py
```

`render.yaml` points `AR_SERVICE_GENERATOR_MODULES_DIR` at `./Shopify`, so Render will add this directory to `sys.path` before importing the generator modules.

After adding or replacing these files, redeploy the Render service and verify:

```text
GET /health
```

The response should include:

```json
{
  "generator": {
    "ready": true
  }
}
```
