"""Explicit per-game application identities, independent of transport code."""

GAME_BUNDLES = {
    "afk_journey": {
        "android_prefixes": ("com.farlightgames.igame.gp",),
        "ios": "com.farlightgames.igame.ios",
    }
}


def resolve_bundle(identifiers):
    """Resolve a supported game to its real Apple bundle identifier."""
    for entry in GAME_BUNDLES.values():
        if any(
            identifier == entry["ios"]
            or any(
                identifier.startswith(prefix) for prefix in entry["android_prefixes"]
            )
            for identifier in identifiers
        ):
            return entry["ios"]
    raise ValueError("This game has no iOS bundle mapping yet.")
