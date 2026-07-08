# BioX Experiments Management Layer — Implementation Prompt

You are an expert MLOps engineer, data scientist, ML platform architect, and data engineer. Your task is to build a complete **experiments management layer** for the BioX R&D team on top of the BioX-A biostimulant AI/ML POC.

This prompt is a companion to `prompt.md`, which defines the underlying POC: a synthetic-data-driven AI/ML system that predicts tomato yield, estimates the treatment effect (uplift) of the seaweed biostimulant **BioX-A** under moderate water stress in tropical Asia, and generates deterministic, evidence-based field-level recommendations with ROI. Read `prompt.md` first for the domain context, data model (`fields`, `treatments`, `satellite_indices`, `weather`, `soil`, `formulations`, `outcomes`), and the three core models (yield prediction, causal uplift, recommendation engine).

The experiments management layer wraps that POC so the BioX team can systematically **define, run, track, compare, reproduce, and evaluate** ML experiments — without re-writing model code each time.

### Core Hierarchy (four levels)

The entire layer is organized around this hierarchy. Every table, MLflow structure, notebook helper, and dashboard page must respect it.

```
Project  →  Experiment  →  Run  →  Evaluation  →  Metrics
```

- **Project** — top-level container for a body of work (crop + product + study focus). Example: "BioX-A Tomato Tropical Asia". A project has many experiments.
- **Experiment** — a named hypothesis or question within a project. Example: "Causal Forest vs OLS uplift estimation". An experiment has many runs.
- **Run** — one execution that produces a single **trained model** under a specific configuration (model type, hyperparameters, feature set, training data). A run has many evaluations.
- **Evaluation** — a **first-class** scoring of a run's trained model against a specific dataset or scenario (e.g., a leave-site-out fold, a held-out site, a moderate-stress subset, or a recommendation rule set). One run can be evaluated many ways. An evaluation has many metrics.
- **Metrics** — the numeric results recorded for a single evaluation (RMSE, R2, uplift_bias, recommendation_precision, etc.).

Key consequence: **metrics belong to an evaluation, not directly to a run**. Training config lives on the run; scoring scenario and results live on the evaluation. This lets the team re-evaluate the same trained model against new scenarios without retraining.

---

## 1. Goal and Scope

Build a layer that lets the BioX R&D and data science team answer questions such as:
- "Which model configuration produced the best yield RMSE under leave-site-out validation?"
- "How close did each uplift-estimation method get to the known synthetic ground-truth treatment effect?"
- "If we raise the ROI threshold from 1.5x to 2.0x, how many fields flip from *apply* to *do-not-apply*?"
- "Which feature set gave the best uplift-ranking quality?"
- "Reproduce the exact run that generated last month's recommendation set."
- "Across all projects, which experiments are still active and how many runs/evaluations does each have?"
- "Take this one trained model and compare its evaluations across the leave-site-out, holdout-site, and moderate-stress-only scenarios."

The layer must combine **two complementary tracking mechanisms**:
1. **MLflow** — for experiment/run tracking, parameters, metrics, artifacts, and a model registry.
2. **Custom Postgres schema** — for BioX-specific metadata that MLflow does not model natively: the project layer, business-level experiment hypotheses, first-class evaluations, treatment configurations, recommendation rule sets, field subsets, and saved comparisons.

The team interacts through:
- A **Python notebook** (`biox_experiments.ipynb`) to define and run experiments.
- A **Streamlit dashboard** (`biox_experiments_dashboard.py`) to browse, compare, and drill into results.

Wherever real data is missing, **generate biologically and operationally plausible mock data**, including a realistic history of past experiments and runs so the dashboard is populated on first launch.

**Guardrails (inherit from `prompt.md`):** All outputs remain framed as "based on synthetic POC evidence and model behavior." Never claim proven product efficacy. Keep the recommendation logic deterministic, explainable, and auditable.

---

## 2. Deliverables

Produce all of the following, runnable end-to-end:

1. `experiments_schema.sql` — PostgreSQL DDL for the custom experiment-tracking schema.
2. `experiments_mock_data.sql` (or a Python generator cell) — mock data for the experiment tables.
3. `biox_experiments.ipynb` — notebook to create, run, log, compare, and reproduce experiments.
4. `biox_experiments_dashboard.py` — Streamlit app with the seven pages defined below.
5. A short `README` section (in the notebook markdown) explaining how the pieces connect.

Assume: existing local Postgres, single logical database shared with the POC (a separate schema `biox_experiments` is acceptable), MLflow tracking store local (SQLite backend or Postgres backend — configurable), Python for the notebook and dashboard.

---

## 3. MLflow Integration Specification

Map the four-level hierarchy onto MLflow as follows:
- **MLflow Experiment** ≈ one BioX Experiment (namespaced by project, e.g., `bioxA_tomato__uplift_estimation`).
- **Parent MLflow run** = one BioX **Run** (the trained model). Log training params here and the serialized model.
- **Nested (child) MLflow runs** = the BioX **Evaluations** of that trained model. Log evaluation params (scenario, subset, rule set) and all **metrics** on the child runs.

This keeps metrics attached to evaluations, consistent with the Postgres schema.

### Runs (parent) — training-time parameters
For every parent run, log:

**Parameters** (`mlflow.log_param`):
- `model_type` (e.g., linear_regression, random_forest, xgboost, lightgbm, causal_forest, double_ml, ols_causal)
- Model hyperparameters (n_estimators, max_depth, learning_rate, etc.)
- `feature_set` (named set, e.g., `baseline`, `with_satellite`, `with_interactions`, `full`)
- `data_subset` (e.g., `all`, `moderate_stress_only`, `site_holdout_S3`)
- `cv_strategy` (e.g., `leave_site_out`, `groupkfold_5`, `random_80_20`)
- `treatment_config_id` (FK into Postgres `treatment_configs`)
- Recommendation thresholds when applicable (`roi_threshold`, `uplift_threshold`, `confidence_bound`)
- `random_seed`

### Evaluations (child runs) — scoring scenario + metrics
For every evaluation (child run under its parent), log:
- `eval_scenario` (e.g., `leave_site_out_agg`, `holdout_site_S3`, `moderate_stress_only`, `recommendation_ruleset_v2`)
- `data_subset` / `field_subset_id` scored
- `treatment_config_id` and (for recommendation evals) the `rule_id` used
- All metrics below

**Metrics** (`mlflow.log_metric`, on the evaluation/child run):
- Yield: `rmse`, `mae`, `r2` (per fold and aggregate)
- Uplift: `treatment_effect_error`, `uplift_rank_qini`, `cate_error_moderate_stress`, `cate_error_no_stress`, `cate_error_severe`
- Ground truth comparison: `true_uplift_moderate`, `est_uplift_moderate`, `uplift_bias`
- Recommendation: `recommendation_precision`, `recommendation_recall`, `roi_accuracy`

**Artifacts** (`mlflow.log_artifact` / `mlflow.log_figure`):
- Training/run-level: serialized model (`mlflow.sklearn.log_model` / `mlflow.xgboost.log_model`), SHAP summary plot, feature importance bar chart.
- Evaluation-level (on the child run): predicted-vs-actual scatter, Qini / uplift-by-decile curve, true-vs-estimated uplift scatter, recommendation confusion matrix.

### Model Registry
- Register the best yield model as `biox_yield_model` (with stage transitions: Staging → Production).
- Register the best uplift model as `biox_uplift_model`.
- The recommendation engine reads the Production models from the registry.

### Tracking URI
- Make the tracking URI configurable in one config cell. Default to a local `mlruns` store; provide a commented alternative for a Postgres-backed MLflow backend store.

---

## 4. Custom Postgres Schema (DDL)

Create schema `biox_experiments` with the following tables. Generate complete, valid PostgreSQL DDL with primary keys, foreign keys, sensible types, `NOT NULL` where appropriate, defaults (`created_at TIMESTAMPTZ DEFAULT now()`), and indexes on foreign keys and common filter columns. Use `SERIAL`/`BIGSERIAL` or `UUID` for surrogate keys consistently.

The tables follow the four-level hierarchy: `projects` \u2192 `experiments` \u2192 `experiment_runs` \u2192 `evaluations` \u2192 `evaluation_metrics`.

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `projects` | Top-level container for a study | `project_id` (PK), `name`, `description`, `crop`, `product`, `region`, `created_by`, `created_at`, `status` (active/archived) |
| `experiments` | Business-level experiment (hypothesis) within a project | `experiment_id` (PK), `project_id` (FK), `name`, `description`, `hypothesis`, `model_family`, `created_by`, `created_at`, `status` (draft/running/completed/archived) |
| `experiment_runs` | One execution producing a trained model | `run_id` (PK), `experiment_id` (FK), `mlflow_run_id` (parent), `mlflow_experiment_name`, `model_type`, `start_time`, `end_time`, `status`, `git_commit`, `notes` |
| `run_parameters` | Training-time params per run | `param_id` (PK), `run_id` (FK), `param_name`, `param_value`, `param_type` |
| `run_artifacts` | Training/model artifacts per run | `artifact_id` (PK), `run_id` (FK), `artifact_name`, `artifact_path`, `artifact_type` (model/figure/report) |
| `evaluations` | First-class scoring of a run's model against a scenario | `evaluation_id` (PK), `run_id` (FK), `mlflow_run_id` (child), `eval_scenario`, `cv_strategy`, `treatment_config_id` (FK), `status`, `created_at`, `notes` |
| `evaluation_metrics` | Numeric metrics per evaluation | `metric_id` (PK), `evaluation_id` (FK), `metric_name`, `metric_value`, `fold`, `recorded_at` |
| `evaluation_artifacts` | Evaluation-time artifacts (Qini, confusion matrix, etc.) | `artifact_id` (PK), `evaluation_id` (FK), `artifact_name`, `artifact_path`, `artifact_type` |
| `treatment_configs` | BioX-specific treatment configurations (lookup) | `config_id` (PK), `product`, `dose_ml_ha`, `application_method`, `crop_stage`, `stress_scenario`, `description` |
| `recommendation_rules` | Rule set scored by a recommendation evaluation | `rule_id` (PK), `evaluation_id` (FK), `uplift_threshold`, `roi_threshold`, `confidence_lower_bound`, `allowed_crop_stages`, `max_soil_ec`, `description` |
| `field_subsets` | Dataset an evaluation ran on | `subset_id` (PK), `evaluation_id` (FK), `site_ids`, `stress_level_filter`, `crop_stage_filter`, `n_fields` |
| `experiment_comparisons` | Saved comparison views | `comparison_id` (PK), `name`, `scope` (run/evaluation), `evaluation_ids` (array/JSON), `run_ids` (array/JSON), `created_by`, `notes`, `created_at` |

Notes:
- Use `TEXT[]` or `JSONB` for array-like columns (`site_ids`, `evaluation_ids`, `run_ids`, `allowed_crop_stages`).
- Add `ON DELETE CASCADE` down the chain: `projects` \u2192 `experiments` \u2192 `experiment_runs` \u2192 `evaluations` \u2192 `evaluation_metrics` / `evaluation_artifacts` / `recommendation_rules` / `field_subsets`.
- Add a view `v_evaluation_summary` that joins `evaluations` \u2192 parent `experiment_runs` \u2192 `experiments` \u2192 `projects` with pivoted key metrics (rmse, r2, uplift_bias, recommendation_precision) for dashboard consumption.
- Add a view `v_run_summary` that rolls up each run's best/representative evaluation for run-level leaderboards.

---

## 5. Mock Data Specification

Generate a realistic history so the dashboard is populated immediately, respecting the four-level hierarchy:

- **1–2 projects**, for example "BioX-A Tomato Tropical Asia" (and optionally a second like "BioX-A Salinity Study") so the project layer is demonstrably populated.
- **5–8 experiments** spread across the project(s), for example:
  - "Baseline yield model (linear regression)"
  - "Random Forest hyperparameter sweep"
  - "XGBoost vs LightGBM yield comparison"
  - "Causal Forest vs OLS uplift estimation"
  - "Stress-segment CATE analysis"
  - "ROI threshold sensitivity (1.5x vs 2.0x vs 2.5x)"
  - "Feature-set ablation (satellite vs no-satellite)"
- **20–30 runs** (trained models) distributed across those experiments, each with plausible training parameters matching the model family.
- **40–80 evaluations** across those runs (each run scored under 2–4 scenarios such as leave-site-out aggregate, holdout site, moderate-stress-only, and a recommendation rule set), each with:
  - Plausible metrics (yield R2 in ~0.70–0.90, RMSE decreasing with better models, uplift_bias small for causal models near the known synthetic effect of ~+0.45 t/ha in moderate stress)
  - 3–5 evaluation-artifact references pointing to placeholder paths under `artifacts/<evaluation_id>/`
- **treatment_configs**: at least control vs BioX-A standard dose, plus stress-scenario variants (no_stress, moderate_stress, severe_drought, high_salinity).
- **recommendation_rules**: several threshold variants tied to recommendation evaluations.
- **field_subsets**: per-evaluation subsets referencing site IDs consistent with the POC's 8 sites.
- **experiment_comparisons**: 2–3 saved comparisons referencing real evaluation_ids (and/or run_ids).

Make metrics internally consistent: better-configured runs should show better metrics across their evaluations; causal models should recover the moderate-stress uplift within a small bias; recommendation precision should track with uplift accuracy.

---

## 6. Python Notebook Specification (`biox_experiments.ipynb`)

Structure the notebook in cells:

1. **Config & imports** — MLflow, sqlalchemy/psycopg2, mlflow tracking URI, Postgres connection, seed.
2. **Schema bootstrap** — run `experiments_schema.sql` (create schema + tables + view) idempotently.
3. **Mock data load** — populate the experiment tables if empty.
4. **Helper: `create_project(...)`** — insert into `projects`.
5. **Helper: `create_experiment(project_id, ...)`** — insert into `experiments` (under a project), create/get the MLflow experiment.
6. **Helper: `run_experiment(experiment_id, config)`** — trains one model (a Run):
   - Starts a **parent** MLflow run
   - Reads POC feature data from Postgres (from `prompt.md`'s feature store)
   - Trains the specified model with the specified feature set / training data
   - Logs training params + serialized model + SHAP/feature-importance artifacts to MLflow
   - Mirrors run metadata into Postgres (`experiment_runs`, `run_parameters`, `run_artifacts`)
   - Returns a `run_id`
7. **Helper: `evaluate_run(run_id, scenario)`** — scores an existing trained model (an Evaluation):
   - Starts a **nested/child** MLflow run under the run's parent
   - Loads the trained model, scores it against the given scenario/subset/rule set
   - Computes metrics (including ground-truth uplift comparison)
   - Logs eval params, metrics, and eval artifacts to MLflow
   - Mirrors into Postgres (`evaluations`, `evaluation_metrics`, `evaluation_artifacts`, and `recommendation_rules` / `field_subsets` when applicable)
8. **Run several real experiments** — create a project, a couple of experiments, train a few models (RF, XGBoost, OLS causal, causal forest), and evaluate each under 2–3 scenarios, so the notebook produces genuine MLflow parent/child runs alongside the mock history.
9. **Comparison queries** — best evaluation per experiment; metric trends across evaluations; SQL against `v_evaluation_summary` and `v_run_summary` returned as DataFrames.
10. **Reproduce a run** — given a `run_id`, pull its training params from Postgres/MLflow, re-train, re-evaluate, and confirm metric reproducibility.
11. **Register best models** — promote best yield and uplift models to the MLflow registry (Production).
12. **Field-recommendation diff** — run two recommendation evaluations under different rule sets and show which fields flip.

Ensure the notebook is re-runnable (kernel restart + run all) and idempotent against Postgres.

---

## 7. Streamlit Dashboard Specification (`biox_experiments_dashboard.py`)

Build a Streamlit app reading from both MLflow (via `mlflow` client) and the custom Postgres schema. Pages (sidebar navigation), organized around the Project → Experiment → Run → Evaluation hierarchy:

1. **Project Browser** — list projects with status filter; select a project to see its experiments.
2. **Experiment Browser** — experiments within the selected project, with status filter and text search; click to view runs and their evaluations.
3. **Evaluation Comparison** — multiselect 2–5 evaluations (across runs/experiments); side-by-side metrics table + radar/bar chart (plotly); highlight the parent-run parameter diff.
4. **Metric Trends** — pick a metric; line chart across evaluations (ordered by time) to visualize improvement over history; filterable by project/experiment.
5. **Best Models Leaderboard** — top evaluations per metric (lowest RMSE, lowest uplift_bias, highest recommendation_precision) with links to detail.
6. **Field Recommendations Diff** — pick two recommendation evaluations; show fields that flip apply/do-not-apply, a summary count, and driver reasons.
7. **Run / Evaluation Detail** — drill into one run (training params, model artifacts) and its evaluations (metrics, eval artifacts — render SHAP/Qini images if present), MLflow parent/child links, and the narrative "AI agronomist" style summary.

Requirements:
- Cache Postgres/MLflow reads with `st.cache_data` / `st.cache_resource`.
- Use plotly for interactive charts.
- Keep all language hedged as synthetic-POC evidence, consistent with `prompt.md`.

---

## 8. Integration Points with the POC (`prompt.md`)

- **Shared Postgres**: The experiments layer reads the POC feature store / analytical tables and writes experiment metadata into the `biox_experiments` schema. No table-name collisions with the POC's `fields`, `treatments`, etc.
- **Feature reuse**: `run_experiment` consumes the same engineered features defined in `prompt.md` (pre/post NDRE, NDWI recovery, stress-window indicators, treatment-by-stress interactions, etc.).
- **Model registry → recommendation engine**: The recommendation engine from `prompt.md` loads the Production yield and uplift models from the MLflow registry rather than re-training inline.
- **Ground-truth loop**: Because the synthetic data embeds a known treatment effect, every uplift **evaluation** logs `uplift_bias` (estimated minus true) so the dashboard can show how faithfully each configuration recovers the truth.

---

## 9. Acceptance Criteria

The delivered layer is correct when:
1. `experiments_schema.sql` runs cleanly on PostgreSQL and creates all 12 tables plus `v_evaluation_summary` and `v_run_summary`.
2. Mock data populates the full hierarchy (projects → experiments → runs → evaluations → metrics) and the dashboard renders with no empty pages.
3. The notebook produces at least two genuine trained runs, each with multiple nested evaluations, mirrored into Postgres and MLflow (parent/child runs).
4. Best models are registered and reachable by the recommendation engine.
5. The Evaluation Comparison and Recommendations Diff pages work against real evaluation_ids.
6. Reproducing a logged run yields matching metrics across its evaluations (within floating-point tolerance).
7. Re-evaluating one trained model against a new scenario creates a new evaluation without retraining.
8. All narrative output stays framed as synthetic-POC evidence, never claiming proven efficacy.

Deliver the response as a practical, buildable blueprint: the DDL, the mock-data generator, the notebook cell outline with code, and the Streamlit app. Keep everything deterministic, explainable, and reproducible.
