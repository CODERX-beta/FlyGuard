# FlyGuard AI — Deployment Instructions & Run Guide

This guide covers all supported ways to run, test, and deploy **FlyGuard AI**, from single-command local execution to containerized Docker deployments and production cloud environments.

---

## 1. System Requirements

| Component | Minimum Requirement | Recommended |
| :--- | :--- | :--- |
| **Operating System** | Linux, macOS, or Windows (WSL2) | Ubuntu 22.04+ / Debian 12+ |
| **Python** | Python `3.11+` | Python `3.12` |
| **Node.js & npm** | Node.js `18+` & npm `9+` | Node.js `20 LTS` |
| **Memory (RAM)** | 4 GB | 8 GB+ (for 20k+ account graph indexing) |
| **Disk Space** | 500 MB free | 2 GB+ |

---

## 2. Quick Start (One-Command Local Run)

If `.venv` and `frontend/node_modules` are already installed, start the entire platform with a single script:

```bash
chmod +x scripts/start_all.sh
./scripts/start_all.sh
```

What `scripts/start_all.sh` does automatically:
1. Checks if `data/flyguard.db` exists; if not, executes `backend/scripts/bootstrap_pipeline.py` to generate 20,000 accounts, 200,000 transactions, and train the XGBoost model.
2. Starts the FastAPI backend on `http://127.0.0.1:8000`.
3. Starts the React + Vite frontend on `http://127.0.0.1:5173`.

---

## 3. Step-by-Step Manual Run Guide

### Step 1: Clone the Repository & Configure Environment
```bash
git clone https://github.com/<your-org>/Fluguard.ai.git
cd Fluguard.ai
cp .env.example .env
```

### Step 2: Set Up Python Virtual Environment & Install Backend Dependencies
```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

### Step 3: Bootstrap the Synthetic Dataset & Train the XGBoost Model
Generate the reproducible synthetic dataset (`seed=42`) and train the calibrated `XGBClassifier`:

```bash
# Full 20,000-account / 200,000-transaction benchmark dataset:
.venv/bin/python backend/scripts/bootstrap_pipeline.py --accounts 20000 --transactions 200000 --seed 42

# Or fast 2,000-account / 20,000-transaction development dataset:
.venv/bin/python backend/scripts/bootstrap_pipeline.py --accounts 2000 --transactions 20000 --seed 42
```

### Step 4: Start the FastAPI Backend Server
```bash
.venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
- **Swagger UI / OpenAPI Docs**: `http://localhost:8000/docs`
- **System Health Endpoint**: `http://localhost:8000/api/health`
- **Database Health Endpoint**: `http://localhost:8000/api/health/db`

### Step 5: Install & Start the Frontend Command Center
Open a second terminal window:
```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```
- **Web Application**: `http://localhost:5173`

---

## 4. Docker & Docker Compose Deployment

FlyGuard AI ships with production-ready `Dockerfile` definitions for both `backend/` and `frontend/`, orchestrated via `docker-compose.yml`.

### Build and Start Containers
```bash
docker compose up --build -d
```

### Verify Running Containers
```bash
docker compose ps
curl http://localhost:8000/api/health
```

### View Logs or Stop Services
```bash
# Follow container logs
docker compose logs -f

# Stop containers
docker compose down
```

---

## 5. Production Cloud Deployment Guide

When deploying FlyGuard AI to cloud infrastructure (AWS ECS/EKS, Google Cloud Run/GKE, Azure Container Apps, Render, or Railway):

### 5.1 Environment Variables (`.env`)
Set the following environment variables in production:

```ini
APP_NAME="FlyGuard AI"
APP_ENV="production"
DEBUG=false

# Use managed PostgreSQL in production instead of local SQLite:
DATABASE_URL="postgresql+psycopg2://flyguard_user:<STRONG_PASSWORD>@<DB_HOST>:5432/flyguard_prod"

# Restrict CORS to your production frontend domain:
CORS_ORIGINS="https://app.flyguard.ai"

# CRITICAL: Disable database reset endpoints in production!
ALLOW_DB_RESET=false

# Default Triage Thresholds (0-100 Normalized Risk Score)
RISK_THRESHOLD_MODERATE=35.0
RISK_THRESHOLD_HIGH=65.0
RISK_THRESHOLD_CRITICAL=85.0
```

### 5.2 Production Backend Server (Gunicorn + Uvicorn Workers)
Run FastAPI behind `uvicorn` with multiple workers or Gunicorn:
```bash
.venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 4 --no-access-log
```

### 5.3 Production Frontend Build (Static Assets + Nginx)
Compile the TypeScript/React frontend into static optimized bundles:
```bash
npm run build --prefix frontend
```
Serve the resulting `frontend/dist/` directory via Nginx, Cloudflare Pages, Vercel, or AWS CloudFront + S3, setting `VITE_API_BASE_URL` to your backend API URL.

---

## 6. Verification & Automated Test Suite

Run the full test suite before any release or deployment:

```bash
# 1. Backend Unit, Anti-Leakage, Security & API Integration Tests (pytest)
.venv/bin/pytest backend/tests/test_flyguard.py -v

# 2. Frontend Component Tests (Vitest)
npm test --prefix frontend

# 3. Frontend Production Type-Check & Bundle Build
npm run build --prefix frontend
```

---

## 7. Publishing to a Public GitHub Repository

To publish or update your public code repository:

```bash
cd /home/that-coder-guy/Fluguard.ai
git init
git add .
git commit -m "feat: complete FlyGuard AI AML & money-mule detection platform"
git branch -M main
git remote add origin https://github.com/<your-username>/Fluguard.ai.git
git push -u origin main
```
*(Note: `.gitignore` is pre-configured so `.venv/`, `node_modules/`, and `.env` secrets are never committed).*

