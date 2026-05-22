"""Identity lock baseline for all commercial photoshoots."""

BASE_IDENTITY_LOCK = (
    "Preserve the exact same facial identity from the input selfie: same person, same age range, "
    "same facial structure, same ethnicity, same skin tone, same natural eye color, same hairline and "
    "hair color, same face proportions. Do not de-age, do not reshape the face, do not change ethnicity, "
    "do not create a different person. Improve only lighting, clothing, background, camera quality and "
    "professional styling."
)

# Aligns with legacy IDENTITY_LOCK in app.py when integrating (Phase 7).
