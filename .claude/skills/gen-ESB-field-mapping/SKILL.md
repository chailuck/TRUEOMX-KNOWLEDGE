Generate end-to-end field mapping Excel tracing the chain: Order Request XPath fields → ProcessConfig Activity + Parameters → FM Service input schema → ESB Service → Backend API endpoint.

The source code folder is read from `scripts/config.json`. Pass a folder name argument to override (e.g. `/generate-field-mapping TRUEOMX_20250725 - AI`).

## Steps

If `$ARGUMENTS` is not empty:
```powershell
cd "c:\Users\ChailucK\OneDrive - True Corporation Public Company Limited\DTAC\Source code\TRUE OMX\TRUEOMX AI"
python scripts/generate_field_mapping.py --source-folder "$ARGUMENTS"
```

If no arguments:
```powershell
cd "c:\Users\ChailucK\OneDrive - True Corporation Public Company Limited\DTAC\Source code\TRUE OMX\TRUEOMX AI"
python scripts/generate_field_mapping.py
```

## After completion, report:
1. Processing stats:
   - Order processes found
   - Total activities / activities with FM mapping / activities with endpoint
   - Config parameters and order request fields extracted
   - ESB services scanned / endpoints resolved / schemas extracted
2. Output file: `output/summary/TRUEOMX_Field_Mapping.xlsx`
3. Sheet summary:
   - **Cover** — metadata and stats
   - **E2E Chain** — full chain: Order Process → Activity → FM Schema → ESB → Protocol/Method/Endpoint → API Request Fields
   - **Order Request Fields** — unique XPath fields extracted from PreExecCheck conditions
   - **Config Parameters** — all KEY=VALUE pairs from ProcessConfig
   - **API Request Schema** — per-activity FM input schema fields (from XSD)
   - **Activity-API Lookup** — flat lookup table of activity → endpoint + var key
   - **Field Lineage** — order field → downstream activities chain
4. Any warnings or unresolved services

## Output description
- **E2E Chain** is the primary sheet — each row is one activity in one order process, with the full integration chain from order data fields through to the outbound API URL
- **FM Input Schema Fields** shows the actual business request fields (from XSD) that the FM service expects — this is the payload sent downstream
- **API Request Fields** column shows the actual backend API request fields:
  - `REST` services: FM schema fields used as JSON payload (`(From FM schema)` marker)
  - `EJB` services (CCBS_*): XSD request fields from `_SharedResources/Schemas/ESB/`
  - `SOAP` services (AR_*, BL_*): fields extracted from WSDL `<wsdl:types>` sections, expanded across multiple schema sections
- **Protocol** column shows `REST`, `SOAP`, `EJB`, or `None` for each activity
- **Endpoint URL**: REST → resolved from TIBCO `.substvar` files; SOAP → from WSDL `<wsdlsoap:address>` binding
