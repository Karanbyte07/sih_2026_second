# Antarctic Twin – SIH 2026 PS 26060

Antarctic station command centre for Maitri and Bharati, combining a React/Vite frontend, FastAPI backend, NCPOR environmental ingestion, station telemetry integration points, persistent digital-twin state, and a dedicated AI/ML service.

## Integrated data architecture

```text
NCPOR AWS/DCWIS observations ─┐
                              ├─ FastAPI backend ── SQLite/PostgreSQL
Station SCADA/IoT MQTT feed ──┘          │
                                         ├─ Digital Twin API ── React UI
                                         └─ AI/ML anomaly and forecast service
```

The environmental provider accepts a validated HTTPS JSON/CSV feed hosted by an official `*.ncpor.res.in` domain. The station gateway contract uses operational MQTT topics such as:

```text
station/maitri/asset/gen1/telemetry
station/bharati/asset/gen2/telemetry
station/maitri/environment
```

Every observation carries a source timestamp and provenance label:

```text
PUBLIC       NCPOR environmental observation
MQTT         station gateway telemetry
SIMULATED    controlled digital-twin scenario data
DERIVED      calculated or forecast value
```

The API exposes provider status, source type, source timestamp, and data age so the frontend can distinguish public, measured, simulated, and derived values.

## Configuration

Copy `server(backend)/.env.example` to `server(backend)/.env` and configure the official provider and station gateway:

```env
PUBLIC_ENVIRONMENT_ENABLED=true
PUBLIC_ENVIRONMENT_URL=https://data.ncpor.res.in/<verified-json-or-csv-endpoint>
PUBLIC_ENVIRONMENT_REFRESH_SECONDS=900
PUBLIC_ENVIRONMENT_TIMEOUT_SECONDS=15

MQTT_ENABLED=true
MQTT_BROKER_HOST=<approved-broker-host>
MQTT_BROKER_PORT=8883
MQTT_TLS_ENABLED=true
MQTT_USERNAME=<broker-user>
MQTT_PASSWORD=<broker-password>
MQTT_TOPIC_PREFIX=station
MQTT_CLIENT_ID=antarctic-twin-backend
```

Use an approved VPN/private route and TLS for station MQTT connectivity. Keep credentials and certificates outside version control. NCPOR public pages and datasets are available at [data.ncpor.res.in](https://data.ncpor.res.in/), including [Maitri](https://data.ncpor.res.in/maitri/live) and [Bharati](https://data.ncpor.res.in/bharati/live) observations.

## Run

Install the JavaScript and Python dependencies:

```powershell
npm install
npm run setup
cd server(backend)
.\venv\Scripts\python.exe -m pip install -r requirements.txt
cd ..\aiml
..\server(backend)\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Start the backend and frontend:

```powershell
npm run dev
```

Start the AI/ML service separately on port 8001:

```powershell
cd aiml
..\server(backend)\venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8001
```

Open http://localhost:5173. The demo password is `antarctic`.

## API and ingestion operations

```text
GET  /api/health
GET  /api/ml/health
GET  /api/environment/provider-status
POST /api/environment/ingest
GET  /api/ml/stations/{station_id}/forecast
GET  /api/ml/stations/{station_id}/anomalies
```

The protected manual ingestion endpoint requires an administrator token. Automatic ingestion runs according to `PUBLIC_ENVIRONMENT_REFRESH_SECONDS`. Telemetry records use the same source metadata and validation contract when connected through the station gateway.

## AI/ML service

The AI/ML service loads the trained artifacts from `aiml/models/`:

- Isolation Forest anomaly detection
- Gradient Boosting energy forecasting
- Gradient Boosting fuel/inventory forecasting

Run model training with the telemetry pipeline when a validated training export is available:

```powershell
cd aiml
..\server(backend)\venv\Scripts\python.exe telemetry_simulator.py
..\server(backend)\venv\Scripts\python.exe anomaly_model.py
..\server(backend)\venv\Scripts\python.exe forecasting_models.py
```

## Demo workflow

1. Sign in and select Maitri or Bharati.
2. Open Overview to inspect the digital twin, environment, energy, and source status.
3. Open AI Analytics for anomaly scores, energy forecasts, fuel forecasts, health, and recommendations.
4. Use Digital Twin simulation controls for controlled what-if scenarios.
5. Review Alerts and Maintenance for operational follow-up.

The frontend communicates only with `/api/*`; the backend coordinates persistence, ingestion, simulation, and AI/ML calls.
