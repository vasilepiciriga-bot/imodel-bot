from imodel.prompts.prompt_quality import is_catalog_ready, score_prompt
from imodel.styles.commercial_styles import get_style


def test_linkedin_premium_grade():
    s = get_style("linkedin_premium")
    r = score_prompt(s)
    assert r["grade"] in ("A+", "A")
    assert is_catalog_ready(s)
