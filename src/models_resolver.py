import logging
import re
from typing import Optional, List
from google import genai

logger = logging.getLogger("pr_summary.models")

_CACHED_RESOLVED_MODELS: Optional[List[str]] = None

FLASH_MODEL_PATTERN = re.compile(r"^gemini-(\d+(?:\.\d+)*)-flash$")
DEFAULT_FLASH_MODELS = ["gemini-2.0-flash", "gemini-1.5-flash"]
DEPRECATED_MODELS = {"gemini-2.5-flash"}


def clear_model_cache() -> None:
    """Clears the cached list of resolved candidate models."""
    global _CACHED_RESOLVED_MODELS
    _CACHED_RESOLVED_MODELS = None


def _parse_flash_version(model_name: str) -> Optional[tuple]:
    """Extract numeric version tuple from 'gemini-X.X-flash' model name, or None if not matching."""
    match = FLASH_MODEL_PATTERN.match(model_name)
    if match:
        try:
            return tuple(int(x) for x in match.group(1).split("."))
        except ValueError:
            return None
    return None


def resolve_candidate_models(client: genai.Client, configured_model: Optional[str] = "auto") -> List[str]:
    """
    Resolves a prioritized list of Gemini models to try.
    If a specific model name is provided, returns [configured_model].
    If 'auto' (or empty) is provided, queries the Gemini API for the newest standard
    Flash models, always including stable production models (gemini-2.0-flash, gemini-1.5-flash).
    """
    global _CACHED_RESOLVED_MODELS

    if configured_model and configured_model.strip().lower() != "auto":
        return [configured_model.strip()]

    if _CACHED_RESOLVED_MODELS:
        return _CACHED_RESOLVED_MODELS

    logger.info("Discovering available Gemini Flash models via API...")
    flash_candidates: List[tuple[tuple, str]] = []

    try:
        models_pager = client.models.list(config={"page_size": 100})
        for model in models_pager:
            name = getattr(model, "name", "")
            if name.startswith("models/"):
                name = name[7:]

            if name in DEPRECATED_MODELS:
                continue

            ver = _parse_flash_version(name)
            if ver is not None:
                flash_candidates.append((ver, name))

            if len(flash_candidates) >= 10:
                break
    except Exception as e:
        logger.warning(
            f"Error or timeout discovering Gemini models via API: {e}. Falling back to default Flash models: {DEFAULT_FLASH_MODELS}"
        )

    if not flash_candidates:
        _CACHED_RESOLVED_MODELS = list(DEFAULT_FLASH_MODELS)
        return _CACHED_RESOLVED_MODELS

    unique_candidates = {name: ver for ver, name in flash_candidates if name not in DEPRECATED_MODELS}
    sorted_models = sorted(unique_candidates.keys(), key=lambda m: unique_candidates[m], reverse=True)

    # Take up to 2 newest preview models (e.g. 3.8, 3.7)
    newest_models = [m for m in sorted_models if m not in DEFAULT_FLASH_MODELS][:2]

    # Always ensure the stable production Flash models are included as reliable fallbacks
    top_candidates = list(newest_models)
    for fallback in DEFAULT_FLASH_MODELS:
        if fallback not in top_candidates:
            top_candidates.append(fallback)

    logger.info(f"Discovered standard Flash model(s) via API; selected candidates: {top_candidates}")
    _CACHED_RESOLVED_MODELS = top_candidates
    return _CACHED_RESOLVED_MODELS


def resolve_model_name(client: genai.Client, configured_model: Optional[str] = "auto") -> str:
    candidates = resolve_candidate_models(client, configured_model)
    return candidates[0]
