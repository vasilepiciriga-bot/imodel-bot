import pytest

from imodel.prompts.prompt_builder import build_prompt
from imodel.prompts.prompt_quality import score_prompt
from imodel.styles.commercial_styles import COMMERCIAL_STYLES, list_trending


@pytest.mark.parametrize("style_key", list(COMMERCIAL_STYLES.keys()))
def test_build_prompt_all_catalog_keys(style_key: str):
    out = build_prompt(style_key, intensity="premium")
    assert out["style_key"] == style_key
    assert len(out["final_prompt"]) > 80
    assert "Preserve the exact same facial identity" in out["final_prompt"]
    assert "different person" in out["negative_prompt"]
    assert out["price_credits"] >= 1


def test_build_prompt_unknown_raises():
    with pytest.raises(KeyError):
        build_prompt("nonexistent_style_xyz")


def test_trending_styles_score_well():
    for style in list_trending():
        result = score_prompt(style)
        assert result["grade"] in ("A+", "A"), f"{style['key']} grade {result['grade']}"
