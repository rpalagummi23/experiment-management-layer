-- ============================================================================
-- BioX-A POC : Experiments management views (dashboard convenience)
-- Target: PostgreSQL, schema `biox_experiments`
-- Metrics are pivoted from the long evaluation_metrics table (aggregate rows have fold IS NULL).
-- Executed by biox_e2e_poc.ipynb section 7. Run AFTER 02_experiments_schema.sql.
-- ============================================================================

CREATE OR REPLACE VIEW biox_experiments.v_evaluation_summary AS
SELECT
    p.project_id, p.name AS project_name,
    e.experiment_id, e.name AS experiment_name, e.model_family,
    r.run_id, r.model_type, r.mlflow_run_id AS run_mlflow_id, r.session_tag,
    ev.evaluation_id, ev.eval_scenario, ev.cv_strategy, ev.created_at,
    MAX(CASE WHEN m.metric_name = 'rmse' AND m.fold IS NULL THEN m.metric_value END) AS rmse,
    MAX(CASE WHEN m.metric_name = 'mae' AND m.fold IS NULL THEN m.metric_value END) AS mae,
    MAX(CASE WHEN m.metric_name = 'r2' AND m.fold IS NULL THEN m.metric_value END) AS r2,
    MAX(CASE WHEN m.metric_name = 'uplift_bias' THEN m.metric_value END) AS uplift_bias,
    MAX(CASE WHEN m.metric_name = 'est_uplift_moderate' THEN m.metric_value END) AS est_uplift_moderate,
    MAX(CASE WHEN m.metric_name = 'treatment_effect_error_mae' THEN m.metric_value END) AS treatment_effect_error,
    MAX(CASE WHEN m.metric_name = 'recommendation_precision' THEN m.metric_value END) AS recommendation_precision,
    MAX(CASE WHEN m.metric_name = 'recommendation_recall' THEN m.metric_value END) AS recommendation_recall,
    MAX(CASE WHEN m.metric_name = 'roi_accuracy' THEN m.metric_value END) AS roi_accuracy
FROM biox_experiments.evaluations ev
JOIN biox_experiments.experiment_runs r ON r.run_id = ev.run_id
JOIN biox_experiments.experiments e ON e.experiment_id = r.experiment_id
JOIN biox_experiments.projects p ON p.project_id = e.project_id
LEFT JOIN biox_experiments.evaluation_metrics m ON m.evaluation_id = ev.evaluation_id
GROUP BY p.project_id, p.name, e.experiment_id, e.name, e.model_family,
         r.run_id, r.model_type, r.mlflow_run_id, r.session_tag,
         ev.evaluation_id, ev.eval_scenario, ev.cv_strategy, ev.created_at;

CREATE OR REPLACE VIEW biox_experiments.v_run_summary AS
SELECT
    p.name AS project_name, e.name AS experiment_name,
    r.run_id, r.model_type, r.mlflow_run_id,
    COUNT(DISTINCT ev.evaluation_id) AS n_evaluations,
    MIN(vs.rmse) AS best_rmse,
    MAX(vs.r2) AS best_r2,
    MIN(ABS(vs.uplift_bias)) AS best_abs_uplift_bias
FROM biox_experiments.experiment_runs r
JOIN biox_experiments.experiments e ON e.experiment_id = r.experiment_id
JOIN biox_experiments.projects p ON p.project_id = e.project_id
LEFT JOIN biox_experiments.evaluations ev ON ev.run_id = r.run_id
LEFT JOIN biox_experiments.v_evaluation_summary vs ON vs.evaluation_id = ev.evaluation_id
GROUP BY p.name, e.name, r.run_id, r.model_type, r.mlflow_run_id;
