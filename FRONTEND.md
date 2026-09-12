# Frontend

The existing dark dashboard layout now loads `/dashboard` automatically without login. It displays nodes, GPS coordinates, heart-rate readings, threats, commands and summary counts. It refreshes every three seconds and retries after connection failures. Failed requests never produce demo data.

Run from the project folder in PowerShell:

```powershell
.\.venv\Scripts\python.exe -B backend\app.py
```

Open http://127.0.0.1:5000. The unchanged backend uses port 5000.

For a UI-only preview without contacting hardware, use process-local settings:

```powershell
$env:ENABLE_SERIAL_INGEST='false'
$env:HEART_RATE_SOURCES_FILE=Join-Path $env:TEMP 'citadel-no-hardware.json'
.\.venv\Scripts\python.exe -B backend\app.py
```

The preview config path should point to a nonexistent file or an empty JSON object. Remove these environment overrides or open a new terminal when returning to hardware use. The backend does not implement an `ENABLE_HEART_RATE_POLLING` switch.

Device and threat markers use relative GPS bounds over the existing satellite image, which is not georeferenced. Missing coordinates are not plotted. Heart-rate values are displayed as received, without clinical classification. Command history is limited to the 20 entries retained by the backend. Its telemetry store is in memory and resets when the server restarts.

The operator note is stored only in this browser. See `frontend/VERIFICATION.md` for the ZIP comparison and test results. All backend files remain unchanged.
