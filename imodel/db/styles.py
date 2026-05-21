from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from imodel.db import connection as db
from imodel.prompts import prompt_builder


def _row_to_public(row: tuple) -> Dict[str, Any]:
    key, name, category, config_json, price_credits, is_premium, is_trending, is_active, sort_order, quality_grade = row[:10]
    try:
        cfg = json.loads(config_json or "{}")
    except Exception:
        cfg = {}
    pub = prompt_builder.public_style(cfg) if cfg else {}
    pub.update({
        "key": key,
        "name": name,
        "category": category,
        "price_credits": price_credits,
        "is_premium": is_premium,
        "is_trending": is_trending,
        "is_active": is_active,
        "sort_order": sort_order,
        "quality_grade": quality_grade,
    })
    return pub


def list_from_db(trending_only: bool = False, category: Optional[str] = None) -> List[Dict[str, Any]]:
    if not db.is_ready():
        styles = prompt_builder.list_styles()
        if trending_only:
            styles = [s for s in styles if s.get("is_trending")]
        if category:
            styles = [s for s in styles if s.get("category") == category]
        return styles
    sql = "SELECT style_key, name, category, config_json, price_credits, is_premium, is_trending, is_active, sort_order, quality_grade FROM imodel_styles WHERE is_active = TRUE"
    params: list = []
    if trending_only:
        sql += " AND is_trending = TRUE"
    if category:
        sql += " AND category = %s"
        params.append(category)
    sql += " ORDER BY is_trending DESC, sort_order ASC"
    rows = db.fetchall(sql, tuple(params))
    return [_row_to_public(r) for r in rows]


def get_from_db(style_key: str) -> Optional[Dict[str, Any]]:
    if not db.is_ready():
        s = prompt_builder.get_style(style_key)
        return prompt_builder.public_style(s) if s else None
    rows = db.fetchall(
        "SELECT style_key, name, category, config_json, price_credits, is_premium, is_trending, is_active, sort_order, quality_grade "
        "FROM imodel_styles WHERE style_key = %s LIMIT 1",
        (style_key,),
    )
    if not rows:
        full = prompt_builder.get_style(style_key)
        return prompt_builder.public_style(full) if full else None
    return _row_to_public(rows[0])


def get_full_config(style_key: str) -> Optional[Dict[str, Any]]:
    if db.is_ready():
        rows = db.fetchall("SELECT config_json FROM imodel_styles WHERE style_key = %s LIMIT 1", (style_key,))
        if rows:
            try:
                return json.loads(rows[0][0] or "{}")
            except Exception:
                pass
    return prompt_builder.get_style(style_key)
