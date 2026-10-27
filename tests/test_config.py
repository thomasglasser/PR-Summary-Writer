import os
import unittest
from unittest.mock import patch
from src.config import SummaryConfig


class TestConfig(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "PR_SUMMARY_WRITER_API_KEY": "test-key-writer",
            "GITHUB_REPOSITORY": "owner/repo",
            "PR_NUMBER": "42",
            "GITHUB_TOKEN": "ghp_dummy",
        },
        clear=True,
    )
    def test_from_env_writer_key_priority(self):
        cfg = SummaryConfig.from_env()
        self.assertEqual(cfg.gemini_api_key, "test-key-writer")
        self.assertEqual(cfg.github_repository, "owner/repo")
        self.assertEqual(cfg.pr_number, 42)
        self.assertEqual(cfg.thinking_budget, 0)

    @patch.dict(
        os.environ,
        {
            "PR_SUMMARIZER_API_KEY": "test-key-summarizer",
            "GITHUB_REPOSITORY": "owner/repo",
            "PR_NUMBER": "100",
            "GITHUB_TOKEN": "ghp_dummy",
            "THINKING_BUDGET": "1024",
        },
        clear=True,
    )
    def test_from_env_summarizer_key_fallback(self):
        cfg = SummaryConfig.from_env()
        self.assertEqual(cfg.gemini_api_key, "test-key-summarizer")
        self.assertEqual(cfg.thinking_budget, 1024)

    @patch.dict(
        os.environ,
        {
            "GEMINI_API_KEY": "generic-key",
            "GITHUB_REPOSITORY": "owner/repo",
            "PR_NUMBER": "100",
            "GITHUB_TOKEN": "ghp_dummy",
        },
        clear=True,
    )
    def test_from_env_generic_fallback(self):
        cfg = SummaryConfig.from_env()
        self.assertEqual(cfg.gemini_api_key, "generic-key")


if __name__ == "__main__":
    unittest.main()
