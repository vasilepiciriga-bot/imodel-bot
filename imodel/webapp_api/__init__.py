from imodel.webapp_api.handlers import (
    handle_gallery,
    handle_gallery_delete,
    handle_list_packages,
    handle_list_packs,
    handle_list_styles,
    handle_record_style_event,
    handle_regenerate,
    handle_style_detail,
    handle_trends,
    handle_weekly_trends,
    resolve_prompt_for_request,
)

__all__ = [
    "handle_list_styles",
    "handle_style_detail",
    "handle_list_packs",
    "handle_list_packages",
    "handle_trends",
    "handle_weekly_trends",
    "handle_gallery",
    "handle_gallery_delete",
    "handle_regenerate",
    "handle_record_style_event",
    "resolve_prompt_for_request",
]
