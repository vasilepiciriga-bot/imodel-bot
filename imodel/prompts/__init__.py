"""Prompt engine package — import submodules directly to avoid circular imports."""

__all__ = ["build_prompt", "score_prompt", "is_catalog_ready"]


def __getattr__(name: str):
    if name == "build_prompt":
        from imodel.prompts.prompt_builder import build_prompt

        return build_prompt
    if name in ("score_prompt", "is_catalog_ready"):
        from imodel.prompts import prompt_quality as pq

        return getattr(pq, name)
    raise AttributeError(name)
