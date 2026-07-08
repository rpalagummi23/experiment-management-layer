-- ============================================================================
-- BioX-A POC : Experiments management schema
-- Target: PostgreSQL, schema `biox_experiments`
-- Hierarchy: projects -> experiments -> experiment_runs -> evaluations -> evaluation_metrics
-- Idempotent: drops and recreates all tables. Executed by biox_e2e_poc.ipynb section 7.
-- NOTE: schema name is hardcoded as biox_experiments; keep in sync with EXP_SCHEMA in the notebook.
-- NOTE: if you provisioned an earlier version, re-run sql/00_run_all.sql to pick up the
--       session_tag column added to experiment_runs.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS biox_experiments;

DROP TABLE IF EXISTS biox_experiments.experiment_comparisons CASCADE;
DROP TABLE IF EXISTS biox_experiments.field_subsets CASCADE;
DROP TABLE IF EXISTS biox_experiments.recommendation_rules CASCADE;
DROP TABLE IF EXISTS biox_experiments.evaluation_artifacts CASCADE;
DROP TABLE IF EXISTS biox_experiments.evaluation_metrics CASCADE;
DROP TABLE IF EXISTS biox_experiments.evaluations CASCADE;
DROP TABLE IF EXISTS biox_experiments.run_artifacts CASCADE;
DROP TABLE IF EXISTS biox_experiments.run_parameters CASCADE;
DROP TABLE IF EXISTS biox_experiments.experiment_runs CASCADE;
DROP TABLE IF EXISTS biox_experiments.experiments CASCADE;
DROP TABLE IF EXISTS biox_experiments.treatment_configs CASCADE;
DROP TABLE IF EXISTS biox_experiments.projects CASCADE;

CREATE TABLE biox_experiments.projects (
    project_id   BIGSERIAL PRIMARY KEY,
    name         TEXT NOT NULL,
    description  TEXT,
    crop         TEXT,
    product      TEXT,
    region       TEXT,
    created_by   TEXT,
    created_at   TIMESTAMPTZ DEFAULT now(),
    status       TEXT DEFAULT 'active'
);

CREATE TABLE biox_experiments.treatment_configs (
    config_id          BIGSERIAL PRIMARY KEY,
    product            TEXT,
    dose_ml_ha         NUMERIC(8,2),
    application_method TEXT,
    crop_stage         TEXT,
    stress_scenario    TEXT,
    description        TEXT
);

CREATE TABLE biox_experiments.experiments (
    experiment_id BIGSERIAL PRIMARY KEY,
    project_id    BIGINT NOT NULL REFERENCES biox_experiments.projects(project_id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    description   TEXT,
    hypothesis    TEXT,
    model_family  TEXT,
    created_by    TEXT,
    created_at    TIMESTAMPTZ DEFAULT now(),
    status        TEXT DEFAULT 'draft'
);

CREATE TABLE biox_experiments.experiment_runs (
    run_id                 BIGSERIAL PRIMARY KEY,
    experiment_id          BIGINT NOT NULL REFERENCES biox_experiments.experiments(experiment_id) ON DELETE CASCADE,
    mlflow_run_id          TEXT,
    mlflow_experiment_name TEXT,
    model_type             TEXT,
    session_tag            TEXT,                   -- execution/session stamp for grouping runs over time
    start_time             TIMESTAMPTZ,
    end_time               TIMESTAMPTZ,
    status                 TEXT DEFAULT 'completed',
    git_commit             TEXT,
    notes                  TEXT
);

CREATE TABLE biox_experiments.run_parameters (
    param_id    BIGSERIAL PRIMARY KEY,
    run_id      BIGINT NOT NULL REFERENCES biox_experiments.experiment_runs(run_id) ON DELETE CASCADE,
    param_name  TEXT NOT NULL,
    param_value TEXT,
    param_type  TEXT
);

CREATE TABLE biox_experiments.run_artifacts (
    artifact_id   BIGSERIAL PRIMARY KEY,
    run_id        BIGINT NOT NULL REFERENCES biox_experiments.experiment_runs(run_id) ON DELETE CASCADE,
    artifact_name TEXT,
    artifact_path TEXT,
    artifact_type TEXT
);

CREATE TABLE biox_experiments.evaluations (
    evaluation_id       BIGSERIAL PRIMARY KEY,
    run_id              BIGINT NOT NULL REFERENCES biox_experiments.experiment_runs(run_id) ON DELETE CASCADE,
    mlflow_run_id       TEXT,
    eval_scenario       TEXT NOT NULL,
    cv_strategy         TEXT,
    treatment_config_id BIGINT REFERENCES biox_experiments.treatment_configs(config_id),
    status              TEXT DEFAULT 'completed',
    created_at          TIMESTAMPTZ DEFAULT now(),
    notes               TEXT
);

CREATE TABLE biox_experiments.evaluation_metrics (
    metric_id     BIGSERIAL PRIMARY KEY,
    evaluation_id BIGINT NOT NULL REFERENCES biox_experiments.evaluations(evaluation_id) ON DELETE CASCADE,
    metric_name   TEXT NOT NULL,
    metric_value  DOUBLE PRECISION,
    fold          INTEGER,
    recorded_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE biox_experiments.evaluation_artifacts (
    artifact_id   BIGSERIAL PRIMARY KEY,
    evaluation_id BIGINT NOT NULL REFERENCES biox_experiments.evaluations(evaluation_id) ON DELETE CASCADE,
    artifact_name TEXT,
    artifact_path TEXT,
    artifact_type TEXT
);

CREATE TABLE biox_experiments.recommendation_rules (
    rule_id                BIGSERIAL PRIMARY KEY,
    evaluation_id          BIGINT REFERENCES biox_experiments.evaluations(evaluation_id) ON DELETE CASCADE,
    uplift_threshold       DOUBLE PRECISION,
    roi_threshold          DOUBLE PRECISION,
    confidence_lower_bound DOUBLE PRECISION,
    allowed_crop_stages    JSONB,
    max_soil_ec            DOUBLE PRECISION,
    description            TEXT
);

CREATE TABLE biox_experiments.field_subsets (
    subset_id           BIGSERIAL PRIMARY KEY,
    evaluation_id       BIGINT REFERENCES biox_experiments.evaluations(evaluation_id) ON DELETE CASCADE,
    site_ids            JSONB,
    stress_level_filter TEXT,
    crop_stage_filter   TEXT,
    n_fields            INTEGER
);

CREATE TABLE biox_experiments.experiment_comparisons (
    comparison_id  BIGSERIAL PRIMARY KEY,
    name           TEXT,
    scope          TEXT,            -- 'run' | 'evaluation'
    evaluation_ids JSONB,
    run_ids        JSONB,
    created_by     TEXT,
    notes          TEXT,
    created_at     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_exp_project ON biox_experiments.experiments(project_id);
CREATE INDEX IF NOT EXISTS idx_run_exp ON biox_experiments.experiment_runs(experiment_id);
CREATE INDEX IF NOT EXISTS idx_eval_run ON biox_experiments.evaluations(run_id);
CREATE INDEX IF NOT EXISTS idx_metric_eval ON biox_experiments.evaluation_metrics(evaluation_id);
CREATE INDEX IF NOT EXISTS idx_param_run ON biox_experiments.run_parameters(run_id);
