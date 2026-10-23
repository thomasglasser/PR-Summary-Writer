import logging
import re
import time
from typing import List, Optional
from google import genai
from google.genai import types
from google.genai.errors import APIError

from src.config import SummaryConfig
from src.models_resolver import resolve_candidate_models
from src.prompt import SUMMARY_SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger("pr_summary.synthesizer")


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

    def _call_model_with_retry(self, model_name: str, user_prompt: str, max_retries: int = 3) -> str:
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

            except APIError as api_err:
                err_str = str(api_err)

                # Check if thinking_config is unsupported by this model
                if "thinking_config" in err_str.lower() or "unsupported field" in err_str.lower():
                    logger.info(f"Model '{model_name}' does not support thinking_config. Retrying without thinking_config...")
                    current_thinking_budget = 0
                    continue

                # Rate limiting or temporary high demand
                if api_err.code in (429, 503) or "resourceexhausted" in err_str.lower():
                    delay = self._extract_retry_delay(err_str, default=5.0 * attempt)
                    reason = "rate limit (429)" if api_err.code == 429 or "resourceexhausted" in err_str.lower() else "high demand (503)"
                    logger.warning(f"Model '{model_name}' encountered {reason}. Backing off for {delay:.1f}s before retrying (attempt {attempt}/{max_retries})...")
                    time.sleep(delay)
                    continue

                raise

            except Exception as e:
                err_str = str(e)
                if "thinking_config" in err_str.lower():
                    logger.info(f"Model '{model_name}' does not support thinking_config. Retrying without thinking_config...")
                    current_thinking_budget = 0
                    continue

                if "429" in err_str or "503" in err_str:
                    delay = 5.0 * attempt
                    logger.warning(f"Transient error on '{model_name}'. Backing off for {delay:.1f}s before retrying...")
                    time.sleep(delay)
                    continue

                raise

        raise RuntimeError(f"Model '{model_name}' exhausted {max_retries} retries.")

    @staticmethod
    def _extract_retry_delay(error_message: str, default: float = 5.0) -> float:
        match = re.search(r"retryDelay\':\s*\'(\d+(?:\.\d+)?)s\'", error_message)
        if match:
            try:
                return float(match.group(1)) + 0.5
            except ValueError:
                pass
        return default
