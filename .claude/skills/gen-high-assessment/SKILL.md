Generate the TRUEOMX Migration Assessment Excel report.

The source code folder name is read from `scripts/config.json`. If the user provides a folder name as an argument (e.g. `/generate-assessment TRUEOMX_20250725 - AI`), pass it via `--source-folder`.

## Steps

1. Determine the source folder:
   - If `$ARGUMENTS` is not empty, use it as the `--source-folder` value
   - Otherwise, the script reads `scripts/config.json` automatically

2. Run the script:

If `$ARGUMENTS` is not empty:
```powershell
cd "c:\Users\ChailucK\OneDrive - True Corporation Public Company Limited\DTAC\Source code\TRUE OMX\TRUEOMX AI"
python scripts/generate_assessment.py --source-folder "$ARGUMENTS"
```

If no arguments:
```powershell
cd "c:\Users\ChailucK\OneDrive - True Corporation Public Company Limited\DTAC\Source code\TRUE OMX\TRUEOMX AI"
python scripts/generate_assessment.py
```

3. After the script completes, report:
   - Output file path (`output/summary/TRUEOMX_Assessment.xlsx`)
   - 10 sheets: Executive Summary, Order Journey Map, Activity Detail, Service Catalog, Interface Catalog, Dependency Matrix, Migration Complexity, Activity Reuse Analysis, Data Mapping Matrix, Modernization Recommendations
   - Key statistics (number of processes, activities, services)
   - Any errors or warnings

## To change the default folder permanently
Edit `scripts/config.json` and update the `source_folder` value:
```json
{ "source_folder": "TRUEOMX_20250725 - AI" }
```
