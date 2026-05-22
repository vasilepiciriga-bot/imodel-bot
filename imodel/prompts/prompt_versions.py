"""Prompt version registry."""

DEFAULT_VERSION = "v1.0"

_VERSIONS: dict[str, list[str]] = {
    "linkedin_premium": ["v1.0"],
    "old_money_portrait": ["v1.0"],
    "golden_hour_dating": ["v1.0"],
}


def get_active_version(style_key: str, prompt_version: str | None = None) -> str:
    if prompt_version and prompt_version in _VERSIONS.get(style_key, []):
        return prompt_version
    versions = _VERSIONS.get(style_key)
    if versions:
        return versions[-1]
    return prompt_version or DEFAULT_VERSION
