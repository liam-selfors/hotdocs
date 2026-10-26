"""graph-query-engine — bootstrap implementation.

HAND-AUTHORED BOOTSTRAP, same honest exception spec-linter's own
gen/spec-linter/spec_linter.py already documents: no generator/
criterion-compiler exists yet to have produced this the normal way.
See verification/graph-query-engine/BOOTSTRAP.md.

Implements R-GQE-007 (load_views) over the six views' SQL
(R-GQE-001..006), generated verbatim into views.sql alongside this
file — that file is the asset; this module is just the thin loader
that substitutes {repo_root} and executes it.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

_VIEWS_SQL_PATH = Path(__file__).parent / "views.sql"

# R-GQE-005: read_json raises on a glob matching zero files, unlike
# read_text. "No component has ever been cold-regenerated through a
# real pipeline yet" is this corpus's own actual, expected state today,
# not a fixture artifact — so component_provenance must degrade to an
# explicitly-typed empty view, not propagate that error.
_EMPTY_COMPONENT_PROVENANCE = """
CREATE OR REPLACE VIEW component_provenance AS
SELECT
  CAST(NULL AS VARCHAR) AS component_id,
  CAST(NULL AS VARCHAR) AS spec_bundle_hash,
  CAST(NULL AS VARCHAR) AS model_pin,
  CAST(NULL AS VARCHAR) AS prompt_version,
  CAST(NULL AS JSON) AS retry_feedback,
  CAST(NULL AS VARCHAR) AS pipeline_version,
  CAST(NULL AS JSON) AS gate_versions,
  CAST(NULL AS BOOLEAN) AS provenance_hit,
  CAST(NULL AS VARCHAR) AS generated_at,
  CAST(NULL AS VARCHAR) AS verification_run_id,
  CAST(NULL AS JSON) AS verification_report,
  CAST(NULL AS JSON) AS license_scan,
  CAST(NULL AS JSON) AS secret_scan
WHERE false;
"""


def load_views(con: duckdb.DuckDBPyConnection, repo_root: Path) -> None:
    """R-GQE-007. Creates (or replaces) all six views on `con`, scoped
    to the corpus under `repo_root`. Idempotent — safe to call more
    than once on the same connection. Raises on the first statement
    that fails, rather than swallowing it — except component_provenance
    degrading to an explicitly empty view when no .provenance.json
    files exist yet (R-GQE-005), which is expected state, not an error."""
    repo_root = repo_root.resolve()
    sql = _VIEWS_SQL_PATH.read_text(encoding="utf-8").format(repo_root=str(repo_root))
    has_provenance = any(repo_root.glob("verification/*/.provenance.json"))
    for statement in sql.split(";\n\n---\n\n"):
        # Strip leading full-line comments (-- ...) before checking for
        # an empty statement — a comment block followed by real SQL is
        # not itself empty, only a statement with nothing else is.
        lines = statement.strip().splitlines()
        while lines and lines[0].strip().startswith("--"):
            lines.pop(0)
        statement = "\n".join(lines).strip()
        if not statement:
            continue
        if "component_provenance" in statement and not has_provenance:
            con.execute(_EMPTY_COMPONENT_PROVENANCE)
            continue
        con.execute(statement)
