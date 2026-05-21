import os

os.environ["BOT_TOKEN"] = "123456:ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"
os.environ.setdefault("REPLICATE_API_TOKEN", "dummy")

from imodel.prompts.prompt_builder import build_prompt, get_style, list_styles


def test_list_styles_has_commercial_keys():
    styles = list_styles(active_only=True)
    keys = {s["key"] for s in styles}
    assert "linkedin_premium" in keys
    assert "old_money_portrait" in keys
    assert len(styles) >= 30


def test_build_prompt_includes_identity():
    built = build_prompt("ceo_portrait")
    assert built is not None
    assert "prompt" in built
    assert "Keep the SAME person" in built["prompt"] or "Preserve facial identity" in built["prompt"]
    assert built["price_credits"] >= 1


def test_copy_any_style_higher_price():
    style = get_style("copy_any_style")
    assert style is not None
    assert int(style.get("price_credits", 0)) >= 5
