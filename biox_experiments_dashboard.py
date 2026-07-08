"""
BioX-A Experiments Management Dashboard
=======================================
Read-only Streamlit viewer over the `biox_experiments` Postgres schema and MLflow.

Prerequisites:
  1. Postgres running and reachable (same config as the notebook).
  2. `biox_e2e_poc.ipynb` has been run at least once (creates + populates the schema).

Run:
  streamlit run biox_experiments_dashboard.py

All language is framed as synthetic-POC evidence -- never claims proven product efficacy.
"""
import os
import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import create_engine, text

# ----------------------------------------------------------------------------
# Config -- mirror the notebook. Override via environment variables if needed.
# ----------------------------------------------------------------------------
PG_CONFIG = {
    "host": os.environ.get("BIOX_PG_HOST", "localhost"),
    "port": os.environ.get("BIOX_PG_PORT", "5432"),
    "dbname": os.environ.get("BIOX_PG_DB", "biox_poc"),
    "user": os.environ.get("BIOX_PG_USER", "postgres"),
    "password": os.environ.get("BIOX_PG_PASSWORD", "postgres"),
}
PG_URL = (
    f"postgresql+psycopg2://{PG_CONFIG['user']}:{PG_CONFIG['password']}"
    f"@{PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['dbname']}"
)
EXP_SCHEMA = "biox_experiments"
TRUE_EFFECT_MODERATE = 0.45  # known synthetic ground truth (t/ha)

st.set_page_config(page_title="BioX-A Experiments", layout="wide")


# ----------------------------------------------------------------------------
# Data access (cached)
# ----------------------------------------------------------------------------
@st.cache_resource
def get_engine():
    return create_engine(PG_URL, pool_pre_ping=True)


@st.cache_data(ttl=60)
def q(sql: str) -> pd.DataFrame:
    try:
        return pd.read_sql(text(sql), get_engine())
    except Exception as e:
        st.session_state["_db_error"] = str(e)
        return pd.DataFrame()


def db_ready() -> bool:
    df = q(f"SELECT COUNT(*) AS n FROM {EXP_SCHEMA}.projects")
    return (not df.empty) and int(df["n"].iloc[0]) > 0


def empty_state():
    st.warning(
        "No experiment data found. Make sure:\n\n"
        "1. Postgres is running and reachable.\n"
        "2. You have run `biox_e2e_poc.ipynb` at least once to create and "
        "populate the `biox_experiments` schema.\n\n"
        f"DB error (if any): `{st.session_state.get('_db_error', 'none')}`"
    )


# ----------------------------------------------------------------------------
# Sidebar navigation
# ----------------------------------------------------------------------------
st.sidebar.title("BioX-A Experiments")
st.sidebar.caption("Synthetic POC evidence only. Not proof of product efficacy.")
PAGE = st.sidebar.radio(
    "Page",
    ["Project Browser", "Experiment Browser", "Evaluation Comparison",
     "Metric Trends", "Best Models Leaderboard", "Field Recommendations Diff",
     "Run / Evaluation Detail"],
)

if not db_ready():
    empty_state()
    st.stop()


# ============================================================================
# 1. Project Browser
# ============================================================================
if PAGE == "Project Browser":
    st.header("Project Browser")
    projects = q(f"SELECT * FROM {EXP_SCHEMA}.projects ORDER BY project_id")
    status_filter = st.multiselect("Status", sorted(projects["status"].unique()),
                                   default=list(projects["status"].unique()))
    view = projects[projects["status"].isin(status_filter)]

    # counts per project
    counts = q(f"""
        SELECT p.project_id,
               COUNT(DISTINCT e.experiment_id) AS n_experiments,
               COUNT(DISTINCT r.run_id) AS n_runs,
               COUNT(DISTINCT ev.evaluation_id) AS n_evaluations
        FROM {EXP_SCHEMA}.projects p
        LEFT JOIN {EXP_SCHEMA}.experiments e ON e.project_id = p.project_id
        LEFT JOIN {EXP_SCHEMA}.experiment_runs r ON r.experiment_id = e.experiment_id
        LEFT JOIN {EXP_SCHEMA}.evaluations ev ON ev.run_id = r.run_id
        GROUP BY p.project_id
    """)
    view = view.merge(counts, on="project_id", how="left")
    st.dataframe(
        view[["project_id", "name", "crop", "product", "region", "status",
              "n_experiments", "n_runs", "n_evaluations"]],
        use_container_width=True, hide_index=True,
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Projects", len(projects))
    c2.metric("Experiments", int(counts["n_experiments"].sum()))
    c3.metric("Evaluations", int(counts["n_evaluations"].sum()))


# ============================================================================
# 2. Experiment Browser
# ============================================================================
elif PAGE == "Experiment Browser":
    st.header("Experiment Browser")
    projects = q(f"SELECT project_id, name FROM {EXP_SCHEMA}.projects ORDER BY name")
    proj = st.selectbox("Project", projects["name"])
    pid = int(projects.loc[projects["name"] == proj, "project_id"].iloc[0])

    exps = q(f"""
        SELECT e.experiment_id, e.name, e.model_family, e.status, e.hypothesis,
               COUNT(DISTINCT r.run_id) AS n_runs,
               COUNT(DISTINCT ev.evaluation_id) AS n_evaluations
        FROM {EXP_SCHEMA}.experiments e
        LEFT JOIN {EXP_SCHEMA}.experiment_runs r ON r.experiment_id = e.experiment_id
        LEFT JOIN {EXP_SCHEMA}.evaluations ev ON ev.run_id = r.run_id
        WHERE e.project_id = {pid}
        GROUP BY e.experiment_id, e.name, e.model_family, e.status, e.hypothesis
        ORDER BY e.experiment_id
    """)
    search = st.text_input("Search experiment name")
    if search:
        exps = exps[exps["name"].str.contains(search, case=False, na=False)]
    st.dataframe(exps, use_container_width=True, hide_index=True)

    if len(exps):
        ename = st.selectbox("Inspect experiment", exps["name"])
        eid = int(exps.loc[exps["name"] == ename, "experiment_id"].iloc[0])
        st.subheader("Runs & evaluations")
        runs = q(f"""
            SELECT r.run_id, r.model_type, ev.evaluation_id, ev.eval_scenario,
                   ROUND(vs.rmse::numeric,3) AS rmse, ROUND(vs.r2::numeric,3) AS r2,
                   ROUND(vs.uplift_bias::numeric,3) AS uplift_bias,
                   ROUND(vs.recommendation_precision::numeric,3) AS rec_precision
            FROM {EXP_SCHEMA}.experiment_runs r
            LEFT JOIN {EXP_SCHEMA}.evaluations ev ON ev.run_id = r.run_id
            LEFT JOIN {EXP_SCHEMA}.v_evaluation_summary vs ON vs.evaluation_id = ev.evaluation_id
            WHERE r.experiment_id = {eid}
            ORDER BY r.run_id, ev.evaluation_id
        """)
        st.dataframe(runs, use_container_width=True, hide_index=True)


# ============================================================================
# 3. Evaluation Comparison
# ============================================================================
elif PAGE == "Evaluation Comparison":
    st.header("Evaluation Comparison")
    evals = q(f"""
        SELECT evaluation_id, project_name, experiment_name, model_type, eval_scenario
        FROM {EXP_SCHEMA}.v_evaluation_summary
        ORDER BY evaluation_id
    """)
    evals["label"] = (evals["evaluation_id"].astype(str) + " | " + evals["experiment_name"]
                      + " | " + evals["model_type"] + " | " + evals["eval_scenario"])
    picks = st.multiselect("Select 2-5 evaluations", evals["label"],
                           default=list(evals["label"].head(3)))
    if len(picks) >= 2:
        ids = [int(p.split(" | ")[0]) for p in picks]
        id_list = ",".join(map(str, ids))
        detail = q(f"""
            SELECT evaluation_id, experiment_name, model_type, eval_scenario,
                   rmse, mae, r2, uplift_bias, est_uplift_moderate,
                   treatment_effect_error, recommendation_precision, recommendation_recall
            FROM {EXP_SCHEMA}.v_evaluation_summary
            WHERE evaluation_id IN ({id_list})
        """)
        st.subheader("Side-by-side metrics")
        st.dataframe(detail.set_index("evaluation_id").T, use_container_width=True)

        metric_opts = [m for m in ["rmse", "mae", "r2", "uplift_bias",
                                    "recommendation_precision", "recommendation_recall"]
                       if detail[m].notna().any()]
        chosen = st.multiselect("Metrics to chart", metric_opts,
                                default=metric_opts[:3])
        if chosen:
            melt = detail.melt(id_vars=["evaluation_id", "model_type"],
                               value_vars=chosen, var_name="metric", value_name="value")
            melt["evaluation"] = melt["evaluation_id"].astype(str) + " (" + melt["model_type"] + ")"
            fig = px.bar(melt, x="metric", y="value", color="evaluation",
                         barmode="group", title="Evaluation metric comparison")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Select at least two evaluations to compare.")


# ============================================================================
# 4. Metric Trends
# ============================================================================
elif PAGE == "Metric Trends":
    st.header("Metric Trends")
    metric = st.selectbox("Metric", ["rmse", "r2", "uplift_bias",
                                     "recommendation_precision", "recommendation_recall"])
    scope = q(f"""
        SELECT evaluation_id, project_name, experiment_name, model_type,
               eval_scenario, created_at, {metric} AS value
        FROM {EXP_SCHEMA}.v_evaluation_summary
        WHERE {metric} IS NOT NULL
        ORDER BY created_at, evaluation_id
    """)
    if scope.empty:
        st.info(f"No evaluations have `{metric}` recorded.")
    else:
        proj = st.selectbox("Project filter", ["(all)"] + sorted(scope["project_name"].unique()))
        view = scope if proj == "(all)" else scope[scope["project_name"] == proj]
        view = view.reset_index(drop=True)
        view["seq"] = view.index + 1
        fig = px.line(view, x="seq", y="value", color="experiment_name", markers=True,
                      hover_data=["model_type", "eval_scenario", "evaluation_id"],
                      title=f"{metric} across evaluations (chronological)")
        if metric == "uplift_bias":
            fig.add_hline(y=0.0, line_dash="dash",
                          annotation_text="zero bias (perfect recovery)")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(view[["evaluation_id", "experiment_name", "model_type",
                           "eval_scenario", "value"]], use_container_width=True, hide_index=True)


# ============================================================================
# 5. Best Models Leaderboard
# ============================================================================
elif PAGE == "Best Models Leaderboard":
    st.header("Best Models Leaderboard")
    st.caption(f"Known synthetic moderate-stress uplift = +{TRUE_EFFECT_MODERATE:.2f} t/ha")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Yield: lowest RMSE")
        top_rmse = q(f"""
            SELECT evaluation_id, experiment_name, model_type, eval_scenario,
                   ROUND(rmse::numeric,3) AS rmse, ROUND(r2::numeric,3) AS r2
            FROM {EXP_SCHEMA}.v_evaluation_summary
            WHERE rmse IS NOT NULL ORDER BY rmse ASC LIMIT 10
        """)
        st.dataframe(top_rmse, use_container_width=True, hide_index=True)
    with c2:
        st.subheader("Uplift: smallest |bias|")
        top_bias = q(f"""
            SELECT evaluation_id, experiment_name, model_type, eval_scenario,
                   ROUND(uplift_bias::numeric,3) AS uplift_bias,
                   ROUND(est_uplift_moderate::numeric,3) AS est_uplift_moderate
            FROM {EXP_SCHEMA}.v_evaluation_summary
            WHERE uplift_bias IS NOT NULL ORDER BY ABS(uplift_bias) ASC LIMIT 10
        """)
        st.dataframe(top_bias, use_container_width=True, hide_index=True)

    st.subheader("Recommendation: highest precision")
    top_prec = q(f"""
        SELECT evaluation_id, experiment_name, model_type, eval_scenario,
               ROUND(recommendation_precision::numeric,3) AS precision,
               ROUND(recommendation_recall::numeric,3) AS recall
        FROM {EXP_SCHEMA}.v_evaluation_summary
        WHERE recommendation_precision IS NOT NULL
        ORDER BY recommendation_precision DESC LIMIT 10
    """)
    st.dataframe(top_prec, use_container_width=True, hide_index=True)


# ============================================================================
# 6. Field Recommendations Diff
# ============================================================================
elif PAGE == "Field Recommendations Diff":
    st.header("Field Recommendations Diff")
    recs = q("SELECT * FROM field_recommendations")
    if recs.empty:
        st.info("`field_recommendations` table not found. Run the notebook's section 12.")
    else:
        st.caption("Current recommendation set (from the notebook's best uplift model + default rules).")
        c1, c2, c3 = st.columns(3)
        c1.metric("Fields", len(recs))
        c2.metric("Recommended", int(recs["recommend"].sum()))
        c3.metric("Recommended %", f"{100*recs['recommend'].mean():.0f}%")

        st.subheader("Recommended-by stress regime")
        by_seg = recs.groupby(["stress_regime", "recommend"]).size().reset_index(name="n")
        fig = px.bar(by_seg, x="stress_regime", y="n", color="recommend",
                     barmode="group", title="Recommendation outcome by stress regime")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("What-if: ROI threshold slider")
        roi_thr = st.slider("ROI threshold", 1.0, 3.5, 1.5, 0.1)
        # recompute recommendation flag using stored roi (deterministic subset of the full rule)
        whatif = recs.copy()
        whatif["recommend_whatif"] = (
            (whatif["pred_uplift_t_ha"] > 0)
            & (whatif["roi"] >= roi_thr)
            & (whatif["uplift_ci_low"] >= -0.05)
            & (whatif["crop_stage"].isin(["flowering", "fruit_set"]))
        )
        flipped = whatif[whatif["recommend"] != whatif["recommend_whatif"]]
        st.write(f"At ROI >= {roi_thr}x, **{int(whatif['recommend_whatif'].sum())}** fields "
                 f"recommended ({len(flipped)} flip vs the stored default).")
        st.dataframe(
            flipped[["field_id", "site_id", "stress_regime", "roi",
                     "recommend", "recommend_whatif"]].head(50),
            use_container_width=True, hide_index=True,
        )


# ============================================================================
# 7. Run / Evaluation Detail
# ============================================================================
elif PAGE == "Run / Evaluation Detail":
    st.header("Run / Evaluation Detail")
    runs = q(f"""
        SELECT r.run_id, e.name AS experiment_name, r.model_type, r.mlflow_run_id, r.notes
        FROM {EXP_SCHEMA}.experiment_runs r
        JOIN {EXP_SCHEMA}.experiments e ON e.experiment_id = r.experiment_id
        ORDER BY r.run_id
    """)
    runs["label"] = runs["run_id"].astype(str) + " | " + runs["experiment_name"] + " | " + runs["model_type"]
    pick = st.selectbox("Run", runs["label"])
    rid = int(pick.split(" | ")[0])

    st.subheader("Training parameters")
    params = q(f"SELECT param_name, param_value, param_type FROM {EXP_SCHEMA}.run_parameters WHERE run_id={rid}")
    st.dataframe(params, use_container_width=True, hide_index=True)

    run_meta = runs[runs["run_id"] == rid].iloc[0]
    st.caption(f"MLflow run: `{run_meta['mlflow_run_id']}`  |  notes: {run_meta['notes'] or '-'}")

    st.subheader("Run artifacts")
    r_art = q(f"SELECT artifact_name, artifact_path, artifact_type FROM {EXP_SCHEMA}.run_artifacts WHERE run_id={rid}")
    for _, a in r_art.iterrows():
        st.write(f"- **{a['artifact_name']}** ({a['artifact_type']})")
        if a["artifact_type"] == "figure" and os.path.exists(a["artifact_path"]):
            st.image(a["artifact_path"], width=520)

    st.subheader("Evaluations of this run")
    evs = q(f"""
        SELECT ev.evaluation_id, ev.eval_scenario, ev.cv_strategy,
               ROUND(vs.rmse::numeric,3) AS rmse, ROUND(vs.r2::numeric,3) AS r2,
               ROUND(vs.uplift_bias::numeric,3) AS uplift_bias,
               ROUND(vs.recommendation_precision::numeric,3) AS rec_precision
        FROM {EXP_SCHEMA}.evaluations ev
        LEFT JOIN {EXP_SCHEMA}.v_evaluation_summary vs ON vs.evaluation_id = ev.evaluation_id
        WHERE ev.run_id = {rid} ORDER BY ev.evaluation_id
    """)
    st.dataframe(evs, use_container_width=True, hide_index=True)

    if len(evs):
        eid = st.selectbox("Evaluation artifacts for", evs["evaluation_id"])
        e_art = q(f"SELECT artifact_name, artifact_path, artifact_type FROM {EXP_SCHEMA}.evaluation_artifacts WHERE evaluation_id={eid}")
        for _, a in e_art.iterrows():
            st.write(f"- **{a['artifact_name']}** ({a['artifact_type']})")
            if a["artifact_type"] == "figure" and os.path.exists(a["artifact_path"]):
                st.image(a["artifact_path"], width=520)

    st.info("All figures reflect model behavior on synthetic POC data. "
            "This demonstrates platform readiness, not proven BioX-A efficacy.")
