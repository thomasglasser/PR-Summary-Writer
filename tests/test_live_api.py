import os
import unittest
from google import genai
from google.genai import types

from src.models_resolver import resolve_candidate_models, clear_model_cache


class TestLiveGeminiAPI(unittest.TestCase):
    """
    Live dynamic integration test against the real Gemini API.
    Executes on CI when GEMINI_API_KEY is available in secrets or local environment.
    """

    def setUp(self):
        clear_model_cache()
        self.api_key = os.environ.get("PR_SUMMARY_WRITER_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            self.skipTest("No GEMINI_API_KEY or PR_SUMMARY_WRITER_API_KEY found in environment.")

    def test_live_model_discovery(self):
        client = genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(timeout=30_000)
        )
        candidates = resolve_candidate_models(client, configured_model="auto")
        self.assertIsInstance(candidates, list)
        self.assertGreater(len(candidates), 0)
        for model in candidates:
            self.assertTrue("flash" in model.lower())

    def test_live_generate_content(self):
        client = genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(timeout=30_000)
        )
        candidates = resolve_candidate_models(client, configured_model="auto")
        top_model = candidates[0]

        response = client.models.generate_content(
            model=top_model,
            contents="Reply with the single word: PONG",
            config=types.GenerateContentConfig(
                temperature=0.1,
                http_options=types.HttpOptions(timeout=30_000)
            )
        )
        self.assertIsNotNone(response)
        self.assertIsNotNone(response.text)
        self.assertIn("PONG", response.text.upper())


if __name__ == "__main__":
    unittest.main()
