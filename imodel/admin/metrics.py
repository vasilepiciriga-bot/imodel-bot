from __future__ import annotations

from typing import Any, Dict

from imodel.db import connection as db
from imodel.db.payments import revenue_summary


def admin_extra_metrics() -> Dict[str, Any]:
    out: Dict[str, Any] = {"revenue": revenue_summary()}
    if not db.is_ready():
        return out
    rows = db.fetchall(
        "SELECT style_key, event, COUNT(*) FROM imodel_style_events "
        "GROUP BY style_key, event ORDER BY COUNT(*) DESC LIMIT 20"
    )
    out["top_style_events"] = [{"style_key": r[0], "event": r[1], "count": int(r[2])} for r in rows]
    rows2 = db.fetchall(
        "SELECT style_key, COUNT(*) FROM imodel_generation_results WHERE deleted_at IS NULL "
        "GROUP BY style_key ORDER BY COUNT(*) DESC LIMIT 10"
    )
    out["top_styles_generated"] = [{"style_key": r[0], "count": int(r[1])} for r in rows2]
    return out
