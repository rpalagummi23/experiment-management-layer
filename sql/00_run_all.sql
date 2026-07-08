-- ============================================================================
-- BioX-A POC : Provision ALL schemas (DBA convenience)
-- ----------------------------------------------------------------------------
-- Runs the three DDL files in dependency order:
--   1. Agronomic tables  (public schema)
--   2. Experiments tables (biox_experiments schema)
--   3. Experiments views  (depends on the tables above)
--
-- USAGE (from the project root, so the relative \i paths resolve):
--   psql "postgresql://postgres:postgres@localhost:5432/biox_poc" -f sql/00_run_all.sql
--
-- or from inside psql:
--   \cd /path/to/project
--   \i sql/00_run_all.sql
--
-- NOTES:
--   * The target database (default: biox_poc) must already exist:
--       createdb biox_poc
--   * These files are IDEMPOTENT -- they DROP and recreate objects, so re-running
--     resets the schema. Do NOT run against a database holding data you want to keep.
--   * `\i` paths are relative to the current working directory of psql, which is why
--     you should invoke from the project root. `ON_ERROR_STOP` aborts on the first error.
--   * Runtime-only tables NOT created here: `feature_store`, `ground_truth`, and
--     `field_recommendations` are created by the notebook (via pandas to_sql) when it runs.
--     Provisioning creates the structural DDL; the notebook populates data and derived tables.
-- ============================================================================

\set ON_ERROR_STOP on
\echo 'BioX-A schema provisioning -- starting'

\echo '  [1/3] Agronomic schema (public)...'
\i sql/01_agronomic_schema.sql

\echo '  [2/3] Experiments schema (biox_experiments)...'
\i sql/02_experiments_schema.sql

\echo '  [3/3] Experiments views...'
\i sql/03_experiments_views.sql

\echo 'BioX-A schema provisioning -- complete.'

-- Quick verification: object counts
\echo ''
\echo 'Verification -- agronomic tables in public:'
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('fields','soil','treatments','weather',
                     'satellite_indices','formulations','outcomes')
ORDER BY table_name;

\echo ''
\echo 'Verification -- tables in biox_experiments:'
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'biox_experiments'
ORDER BY table_name;

\echo ''
\echo 'Verification -- views in biox_experiments:'
SELECT table_name
FROM information_schema.views
WHERE table_schema = 'biox_experiments'
ORDER BY table_name;
