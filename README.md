# BioX-A Biostimulant — End-to-End AI/ML POC with Experiments Management

A self-contained proof-of-concept that demonstrates how an AI/ML platform can augment
BioX's R&D and field-validation workflow for the seaweed biostimulant **BioX-A** on tomato
in tropical Asia.

> **Framing:** The synthetic data embeds a *known ground-truth* treatment effect (BioX-A
> helps under **moderate water stress**, is neutral under no stress, and does not help under
> severe drought / high salinity or wrong crop stage). The POC proves the **platform can
> recover the correct response pattern** — it does **not** prove product efficacy. All
> outputs are framed as *"based on synthetic POC evidence and model behavior."*

---

## What's in this project

| File | Purpose |
|------|---------|
| `biox_e2e_poc.ipynb` | The end-to-end notebook: synthetic data → Postgres → EDA → features → models → experiments layer → recommendations |
| `biox_experiments_dashboard.py` | Streamlit dashboard (7 pages) — a read-only viewer over the experiments schema + MLflow |
| `prompt.md` | Original agronomic POC specification |
| `experiments_management_prompt.md` | Experiments management layer specification |

### Two layers, one build

1. **Agronomic POC** — 7 tables (`fields`, `treatments`, `satellite_indices`, `weather`,
   `soil`, `formulations`, `outcomes`), a `feature_store`, and three models:
   yield prediction (Linear / Random Forest / XGBoost), causal uplift (OLS causal /
   EconML Causal Forest), and a deterministic recommendation engine.
2. **Experiments management** — MLflow tracking + a Postgres `biox_experiments` schema
   (12 tables + 2 views) organized as **Project → Experiment → Run → Evaluation → Metrics**,
   plus the Streamlit dashboard.

---

## Prerequisites

- Python 3.9+
- A local PostgreSQL server
- Python packages (installed from the notebook's cell 0, or manually):

```
pandas numpy sqlalchemy psycopg2-binary
scikit-learn xgboost lightgbm shap statsmodels
matplotlib seaborn plotly mlflow streamlit
econml            # optional; falls back to statsmodels OLS if missing
```

---

## Setup

### 1. Install & start Postgres

macOS (Homebrew):

```bash
brew install postgresql@16
brew services start postgresql@16
createdb biox_poc
```

Ubuntu/Debian:

```bash
sudo apt-get install postgresql
sudo service postgresql start
sudo -u postgres createdb biox_poc
```

Docker (alternative):

```bash
docker run --name biox-pg -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=biox_poc -p 5432:5432 -d postgres:16
```

### 2. Configure the connection

The notebook and dashboard default to:

```
host=localhost port=5432 dbname=biox_poc user=postgres password=postgres
```

Override via environment variables if your setup differs:

```bash
export BIOX_PG_HOST=localhost
export BIOX_PG_PORT=5432
export BIOX_PG_DB=biox_poc
export BIOX_PG_USER=postgres
export BIOX_PG_PASSWORD=postgres
```

(Or edit `PG_CONFIG` in the notebook's Config cell directly.)

---

## Run order

1. **Run the notebook** top-to-bottom: open `biox_e2e_poc.ipynb` and choose
   `Kernel → Restart & Run All`. It is idempotent — safe to re-run. This:
   - creates the agronomic schema and generates ~500 synthetic fields
   - engineers features into `feature_store`
   - trains the three models
   - creates the `biox_experiments` schema, runs genuine experiments + evaluations,
     seeds mock history, and writes `field_recommendations`
   - MLflow logs to a local `./mlruns` folder (no server needed)

2. **Launch the dashboard**:

   ```bash
   streamlit run biox_experiments_dashboard.py
   ```

   The dashboard is **read-only** — it requires Postgres running and the notebook to have
   been run at least once. If the schema is empty it shows a friendly setup message.

3. **(Optional) Browse MLflow**:

   ```bash
   mlflow ui --backend-store-uri ./mlruns
   ```

---

## Dashboard pages

1. **Project Browser** — projects with experiment/run/evaluation counts
2. **Experiment Browser** — experiments within a project; drill into runs + evaluations
3. **Evaluation Comparison** — side-by-side metrics + grouped bar chart for 2–5 evaluations
4. **Metric Trends** — a chosen metric across evaluations over time (with zero-bias line for uplift)
5. **Best Models Leaderboard** — top evaluations by RMSE, |uplift bias|, recommendation precision
6. **Field Recommendations Diff** — recommendation set + ROI-threshold what-if slider
7. **Run / Evaluation Detail** — training params, artifacts (SHAP / pred-vs-actual / uplift-by-segment), per-evaluation metrics

---

## Key concepts

- **Ground-truth recovery**: every uplift evaluation logs `uplift_bias` = estimated −
  known synthetic effect (`+0.45 t/ha` in moderate stress), so you can see how faithfully
  each configuration recovers the truth.
- **Per-scenario evaluations**: one trained model (a Run) is scored under multiple scenarios
  (leave-site-out, moderate-stress-only, recommendation rule sets). Folds are stored in the
  `fold` column of `evaluation_metrics`.
- **Deterministic recommendations**: apply BioX-A only if predicted uplift > 0, ROI ≥ threshold,
  lower confidence bound acceptable, crop stage appropriate, and soil not severely saline.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `could not connect to Postgres` | Ensure the server is running and `biox_poc` exists (`createdb biox_poc`). |
| Dashboard shows "No experiment data found" | Run `biox_e2e_poc.ipynb` fully first. |
| `econml` import errors | It's optional; the uplift model falls back to statsmodels OLS. |
| SHAP/plot cells slow | SHAP is best-effort and wrapped in try/except; it will skip on error. |

---

*This POC demonstrates AI/ML platform readiness for BioX. It does not constitute proof of
BioX-A product efficacy; all evidence is synthetic.*
