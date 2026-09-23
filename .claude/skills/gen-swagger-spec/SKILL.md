Generate Swagger/OpenAPI 3.0 specification and HTML documentation for all non-EJB outbound integrations (REST + SOAP) in TRUEOMX ESB.

Resolves actual endpoint URLs from TIBCO substitution variable files (*.substvar).

The source code folder is read from `scripts/config.json`. Pass a folder name argument to override (e.g. `/generate-swagger-spec TRUEOMX_20250725 - AI`).

## Steps

If `$ARGUMENTS` is not empty:
```powershell
cd "c:\Users\ChailucK\OneDrive - True Corporation Public Company Limited\DTAC\Source code\TRUE OMX\TRUEOMX AI"
python scripts/generate_swagger_spec.py --source-folder "$ARGUMENTS"
```

If no arguments:
```powershell
cd "c:\Users\ChailucK\OneDrive - True Corporation Public Company Limited\DTAC\Source code\TRUE OMX\TRUEOMX AI"
python scripts/generate_swagger_spec.py
```

## After completion, report:
1. Number of REST and SOAP services discovered
2. Endpoint resolution stats (how many URLs resolved vs still using variable placeholder)
3. Output files produced:
   - `output/summary/TRUEOMX_REST_SOAP_API.json` — OpenAPI 3.0 JSON (for Swagger tooling)
   - `output/summary/TRUEOMX_REST_SOAP_API.yaml` — OpenAPI 3.0 YAML
   - `output/summary/TRUEOMX_REST_SOAP_API.html` — Interactive Swagger UI (requires internet for CDN)
   - `output/summary/TRUEOMX_REST_SOAP_Static.html` — Static offline HTML table report
4. File sizes
5. Sample of 5 services from the output

## Output description
- **JSON/YAML**: Load into Swagger UI, Postman, or any OpenAPI tool
- **Swagger UI HTML**: Interactive docs — open in browser, requires internet for CDN JS/CSS
- **Static HTML**: Fully offline table-based report — always works without internet
