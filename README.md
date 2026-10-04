# Antarctic Twin – SIH 2026 PS 26060 (Maitri & Bharati)
React + Vite frontend (`client/`) with a small Express backend (`server/`) that generates **simulated** station data.
## Run
```
npm i && npm run setup   # one-time install (root, server, client)
npm run dev              # starts API :4000 and web :5173
```
Open http://localhost:5173 — demo password for all accounts: `antarctic`
(admin@ncpor.in, ops@ncpor.in, maint@ncpor.in (Bharati only), logistics@ncpor.in (Maitri only))
Or run separately: `cd server && npm start` and `cd client && npm run dev`.
## Try the demo story
1. Bharati → Overview → watch Generator 02 vibration climb (simulated drift) → alert appears.
2. Alert → "Open in Digital Twin" → inspect readings → Simulate failure.
3. Energy / Logistics show the chained cause→effect. Maintenance → mark Gen 02 task done to clear the fault.
4. Replace `server/index.js` data generation with real sensor feeds later; the frontend only talks to `/api/*`.
