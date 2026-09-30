# FacultyHelp

FacultyHelp is a server-rendered campus support portal built with Python, FastAPI, Jinja2, and SQLite. The database and uploaded evidence are stored in `data/` by default.

## Run locally

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm install
npm run dev
```

Open the React interface at `http://127.0.0.1:5173`; Vite proxies `/api` and `/uploads` to FastAPI on port `8000`. Sample accounts and tickets are created on first startup. Demo passwords are `faculty123` for faculty, `team123` for support staff, and `admin123` for the administrator. Change these before exposing the app beyond a local demo.

## Deploy a preview to Vercel

Push the repository to GitHub, import it in Vercel, and deploy from the repository root. `vercel.json` builds the React frontend, and FastAPI serves it alongside the API. Vercel deployments use temporary `/tmp` storage for the SQLite database and uploads; data may be lost or differ between function instances. Do not use this preview for real tickets or evidence. Before making the app public, replace the seeded demo accounts and move the database and uploads to persistent managed services.

For a production-style local run, build the frontend with `npm run build`, then launch both services with `npm start`.

Set `FACULTYHELP_DATA_DIR` to move the SQLite database and uploaded files outside the project directory. Set `SLA_CRON_SECRET` and call `POST /api/cron/sla-monitor` with `Authorization: Bearer <secret>` from a scheduler to run the SLA escalation scan.

## Tests

```powershell
python -m pip install -r requirements-dev.txt
npm run test
```

The JSON API remains available under `/api` for authentication, bootstrap data, ticket management, and reports. `npm run build` creates the frontend production bundle.