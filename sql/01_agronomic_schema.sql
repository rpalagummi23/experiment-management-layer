-- ============================================================================
-- BioX-A POC : Agronomic schema (raw synthetic data model)
-- Target: PostgreSQL, public schema
-- Idempotent: drops and recreates the POC tables so the notebook is reproducible.
-- Executed by biox_e2e_poc.ipynb section 2 (via run_sql_file).
-- ============================================================================

DROP TABLE IF EXISTS outcomes CASCADE;
DROP TABLE IF EXISTS satellite_indices CASCADE;
DROP TABLE IF EXISTS weather CASCADE;
DROP TABLE IF EXISTS soil CASCADE;
DROP TABLE IF EXISTS treatments CASCADE;
DROP TABLE IF EXISTS formulations CASCADE;
DROP TABLE IF EXISTS fields CASCADE;
DROP TABLE IF EXISTS feature_store CASCADE;

CREATE TABLE formulations (
    product_id        TEXT PRIMARY KEY,
    product_name      TEXT NOT NULL,
    active_ingredient TEXT NOT NULL,
    concentration_pct NUMERIC(5,2) NOT NULL,
    description       TEXT
);

CREATE TABLE fields (
    field_id             TEXT PRIMARY KEY,
    site_id              TEXT NOT NULL,
    crop                 TEXT NOT NULL,
    variety              TEXT,
    lat                  NUMERIC(8,5),
    lon                  NUMERIC(8,5),
    area_ha              NUMERIC(6,2),
    irrigation_type      TEXT,
    historical_yield_avg NUMERIC(6,2)
);

CREATE TABLE soil (
    field_id           TEXT PRIMARY KEY REFERENCES fields(field_id) ON DELETE CASCADE,
    ph                 NUMERIC(4,2),
    ec_ds_m            NUMERIC(5,2),
    organic_matter_pct NUMERIC(5,2),
    texture_class      TEXT,
    cec                NUMERIC(6,2)
);

CREATE TABLE treatments (
    field_id           TEXT PRIMARY KEY REFERENCES fields(field_id) ON DELETE CASCADE,
    treatment_flag     INTEGER NOT NULL,          -- 1 = BioX-A, 0 = control
    product_id         TEXT REFERENCES formulations(product_id),
    dose_ml_ha         NUMERIC(8,2),
    application_method TEXT,                       -- foliar / soil_drench / fertigation
    crop_stage         TEXT,                       -- vegetative / flowering / fruit_set / ripening
    application_date   DATE
);

CREATE TABLE weather (
    weather_id    BIGSERIAL PRIMARY KEY,
    field_id      TEXT NOT NULL REFERENCES fields(field_id) ON DELETE CASCADE,
    period        TEXT NOT NULL,                   -- pre / post
    rainfall_mm   NUMERIC(7,2),
    temp_avg_c    NUMERIC(5,2),
    temp_max_c    NUMERIC(5,2),
    vpd_kpa       NUMERIC(5,2),
    drought_index NUMERIC(5,3)                     -- 0 (wet) .. 1 (severe drought)
);

CREATE TABLE satellite_indices (
    sat_id             BIGSERIAL PRIMARY KEY,
    field_id           TEXT NOT NULL REFERENCES fields(field_id) ON DELETE CASCADE,
    period             TEXT NOT NULL,              -- pre / post
    ndvi               NUMERIC(5,3),
    ndre               NUMERIC(5,3),
    ndwi               NUMERIC(5,3),
    savi               NUMERIC(5,3),
    sentinel1_vv       NUMERIC(7,3),
    sentinel1_vh       NUMERIC(7,3),
    sentinel1_vv_vh    NUMERIC(7,3),
    sentinel3_lst      NUMERIC(6,2)                -- land surface temp (C)
);

CREATE TABLE outcomes (
    field_id             TEXT PRIMARY KEY REFERENCES fields(field_id) ON DELETE CASCADE,
    yield_t_ha           NUMERIC(6,3),
    marketable_yield_t_ha NUMERIC(6,3),
    quality_score        NUMERIC(5,2),
    product_cost_usd     NUMERIC(8,2),
    application_cost_usd NUMERIC(8,2),
    crop_price_usd_t     NUMERIC(8,2)
);

CREATE INDEX IF NOT EXISTS idx_sat_field ON satellite_indices(field_id);
CREATE INDEX IF NOT EXISTS idx_weather_field ON weather(field_id);
