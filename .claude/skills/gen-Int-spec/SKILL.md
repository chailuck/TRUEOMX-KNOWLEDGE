Generate the TRUEOMX Integration Specification Excel report with full ProcessConfig→FM→ESB→REST/EJB mapping chain.

The source code folder name is read from `scripts/config.json`. If the user provides a folder name as an argument (e.g. `/generate-integration-spec TRUEOMX_20250725 - AI`), pass it via `--source-folder` to both scripts.

## Steps

1. Determine the source folder:
   - If `$ARGUMENTS` is not empty, use it as the `--source-folder` value
   - Otherwise, both scripts read `scripts/config.json` automatically

2. Run both scripts in sequence:

If `$ARGUMENTS` is not empty:
```powershell
cd "c:\Users\ChailucK\OneDrive - True Corporation Public Company Limited\DTAC\Source code\TRUE OMX\TRUEOMX AI"
python scripts/extract_mapping.py --source-folder "$ARGUMENTS"
python scripts/generate_integration_spec.py --source-folder "$ARGUMENTS"
```

If no arguments:
```powershell
cd "c:\Users\ChailucK\OneDrive - True Corporation Public Company Limited\DTAC\Source code\TRUE OMX\TRUEOMX AI"
python scripts/extract_mapping.py
python scripts/generate_integration_spec.py
```

3. After the scripts complete, report:
   - Mapping coverage stats from `extract_mapping.py` (total rules, matched, unmatched)
   - Output file path (`output/summary/TRUEOMX_Integration_Spec.xlsx`)
   - 8 sheets: Cover, Integration Chain (All), Integration Chain (Summary), FM Service Catalog, ESB Service Catalog, Protocol Distribution, Data Flow Map, Schema Reference
   - Row counts for the main Integration Chain sheets
   - Any errors or warnings

## To change the default folder permanently
Edit `scripts/config.json` and update the `source_folder` value:
```json
{ "source_folder": "TRUEOMX_20250725 - AI" }
```
