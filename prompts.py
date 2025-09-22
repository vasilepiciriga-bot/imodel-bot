PROMPT_INTERIOR_PRO = (
    "Ultra-realistic professional interior photography of the exact same apartment without any changes to furniture, "
    "objects, or interior details. The goal is to transform the uploaded photo into a premium, world-class hotel and "
    "architectural photography result while preserving every single design element exactly as in the original image. "
    "Enhance photo quality so it looks like it was taken by the best interior and hotel photographer in the world, for luxury real estate magazines. "
    "Perspective may be slightly adjusted to improve composition, keeping vertical lines straight (no distortion), with a professional wide-angle effect. "
    "Perfectly balanced natural and artificial lighting, soft shadows, clean highlights, accurate color, true-to-life textures, crystal clear sharpness, high dynamic range, cinematic but natural tones. "
    "Emphasize depth, space, atmosphere. Preserve 100% of the original design, layout, and décor."
)

NEGATIVE_PROMPT = (
    "Do not add, remove, or change any main furniture or décor. No furniture changes. No décor invention. "
    "No replacements of design elements. No paintings, no new lights, no pillows. No people. No text. No logos. "
    "No surreal or cartoon style. No unrealistic effects. Do not remove designed clutter. Must remain absolutely authentic to the original photo. "
    "Only allow removal of small accidental clutter (e.g., cloth, cable, plastic bag, disposable cup) when explicitly requested."
)

# Internal hint for auto-cleanup provider
AUTO_CLEAN_HINT = (
    "Remove only small accidental items (cloth/cable/bag/cup/bottle/paper/box) detected by object detector; "
    "do not touch furniture, lamps, wall décor, or any design elements."
)

