import logging
import re
import time
from typing import Any, List, Optional
from google import genai
from google.genai import types
from google.genai.errors import APIError

from src.config import SummaryConfig
from src.models_resolver import resolve_candidate_models
from src.prompt import SUMMARY_SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger("pr_summary.synthesizer")


def extract_retry_delay(error: Exception) -> Optional[float]:
    """
    Extracts recommended retryDelay (in seconds) from a Google GenAI / API error if present.
    Checks structured error details and regex matches in string representation.
    """
    try:
        for attr in ("details", "error", "args"):
            val = getattr(error, attr, None)
            candidates_to_check = [val] if not isinstance(val, (list, tuple)) else list(val)
            for item in candidates_to_check:
                if isinstance(item, dict):
                    details = item.get("details", [])
                    if isinstance(details, list):
                        for d in details:
                            if isinstance(d, dict) and "retryDelay" in d:
                                delay_str = str(d["retryDelay"]).rstrip("s")
                                return float(delay_str)
                    if "retryDelay" in item:
                        delay_str = str(item["retryDelay"]).rstrip("s")
                        return float(delay_str)
    except Exception:
        pass

    err_text = str(error)
    m = re.search(r"['\"]?retryDelay['\"]?\s*:\s*['\"]?([\d\.]+)s?['\"]?", err_text, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass

    m2 = re.search(r"retry (?:in|after) ([\d\.]+)\s*s", err_text, re.IGNORECASE)
    if m2:
        try:
            return float(m2.group(1))
        except ValueError:
            pass

    return None


class PRSummarizer:
    def __init__(self, config: SummaryConfig):
        self.config = config
        self.client = genai.Client(api_key=config.gemini_api_key)

    def generate_summary(
        self,
        pr_title: str,
        pr_base: str,
        pr_head: str,
        diff_text: str,
        file_list: List[str],
    ) -> str:
        """
        Generates a conceptual summary and domain-grouped changelog for the given PR diff.
        Employs dynamic model failover and exponential backoff on rate limits.
        """
        candidate_models = resolve_candidate_models(self.client, self.config.model_name)
        user_prompt = build_user_prompt(pr_title, pr_base, pr_head, diff_text, file_list)

        last_error: Optional[Exception] = None

        for model_name in candidate_models:
            logger.info(f"Running Gemini summary synthesis with model '{model_name}'...")
            try:
                summary_text = self._call_model_with_retry(model_name, user_prompt)
                if summary_text and summary_text.strip():
                    return summary_text.strip()
            except Exception as e:
                logger.warning(f"Model '{model_name}' failed to generate summary: {e}")
                last_error = e

        raise RuntimeError(f"All candidate models failed to generate summary. Last error: {last_error}")

    def _call_model_with_retry(self, model_name: str, user_prompt: str, max_retries: int = 2) -> str:
        attempt = 0
        current_thinking_budget = self.config.thinking_budget

        while attempt < max_retries:
            attempt += 1
            try:
                config_kwargs = {
                    "system_instruction": SUMMARY_SYSTEM_PROMPT,
                    "temperature": 0.2,
                }
                if current_thinking_budget > 0:
                    config_kwargs["thinking_config"] = types.ThinkingConfig(
                        thinking_budget=current_thinking_budget
                    )

                gen_config = types.GenerateContentConfig(**config_kwargs)

                response = self.client.models.generate_content(
                    model=model_name,
                    contents=user_prompt,
                    config=gen_config,
                )

                if response and response.text:
                    return response.text

                raise ValueError("Model returned an empty response.")

            except Exception as e:
                err_str = str(e).lower()

                # Check if thinking_config is unsupported by this model
                if "thinking_config" in err_str or "unsupported field" in err_str:
                    logger.info(f"Model '{model_name}' does not support thinking_config. Retrying without thinking_config...")
                    current_thinking_budget = 0
                    continue

                is_503 = "503" in err_str or "high demand" in err_str or "unavailable" in err_str or "overloaded" in err_str
                is_429 = "429" in err_str or "quota" in err_str or "exhausted" in err_str or "resourceexhausted" in err_str or "rate limit" in err_str or "too many requests" in err_str

                if is_503 or is_429:
                    reason = "high demand (503)" if is_503 else "rate limit (429)"
                    retry_delay = extract_retry_delay(e)

                    if retry_delay is not None and retry_delay <= 15:
                        backoff_sec = retry_delay + 1
                        if attempt < max_retries:
                            logger.warning(
                                f"Model '{model_name}' encountered {reason}: {e}. "
                                f"Backing off for {backoff_sec:.1f}s before retrying..."
                            )
                            time.sleep(backoff_sec)
                            continue
                        else:
                            logger.warning(f"Model '{model_name}' exhausted retries on {reason}: {e}")
                            break
                    elif retry_delay is not None and retry_delay > 15:
                        logger.warning(
                            f"Model '{model_name}' encountered {reason}: {e}. "
                            f"Recommended retryDelay of {retry_delay:.1f}s exceeds short backoff. Failing over to next model immediately..."
                        )
                        break
                    else:
                        if attempt < max_retries:
                            backoff_sec = 5.0
                            logger.warning(
                                f"Model '{model_name}' encountered {reason}: {e}. "
                                f"Backing off for {backoff_sec}s before retrying..."
                            )
                            time.sleep(backoff_sec)
                            continue
                        else:
                            logger.warning(f"Model '{model_name}' exhausted retries on {reason}: {e}")
                            break

                raise

        raise RuntimeError(f"Model '{model_name}' failed to generate summary (exhausted retries or quota).")
