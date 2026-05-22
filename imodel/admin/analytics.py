"""Studio business analytics HTML fragment (Phase 10)."""

from __future__ import annotations

import html as html_lib
from typing import Callable, List


def studio_analytics_html(fetchall: Callable) -> str:
    payments = fetchall(
        "SELECT package_key, COUNT(*), COALESCE(SUM(stars_amount),0), COALESCE(SUM(credits_added),0) "
        "FROM imodel_payments GROUP BY package_key ORDER BY COUNT(*) DESC LIMIT 12",
        (),
    ) or []
    styles = fetchall(
        "SELECT style_key, event, COUNT(*) FROM imodel_style_events "
        "GROUP BY style_key, event ORDER BY COUNT(*) DESC LIMIT 20",
        (),
    ) or []
    gallery = fetchall(
        "SELECT COUNT(*) FROM imodel_generation_results WHERE deleted_at IS NULL",
        (),
    ) or [(0,)]
    rows_p = "".join(
        f"<tr><td>{html_lib.escape(str(r[0]))}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td></tr>"
        for r in payments
    ) or "<tr><td colspan=4>no payments yet</td></tr>"
    rows_s = "".join(
        f"<tr><td>{html_lib.escape(str(r[0]))}</td><td>{html_lib.escape(str(r[1]))}</td><td>{r[2]}</td></tr>"
        for r in styles
    ) or "<tr><td colspan=3>no style events yet</td></tr>"
    return f"""
      <div class="section"><h2>iModel Studio analytics</h2>
        <div class="grid">
          <div class="card"><div class="muted">Gallery rows</div><div class="v">{gallery[0][0]}</div></div>
        </div>
        <div class="card"><div class="muted">Payments by package</div>
          <table><tr><th>Package</th><th>Count</th><th>Stars</th><th>Credits</th></tr>{rows_p}</table>
        </div>
        <div class="card"><div class="muted">Style events</div>
          <table><tr><th>Style</th><th>Event</th><th>Count</th></tr>{rows_s}</table>
        </div>
      </div>"""
