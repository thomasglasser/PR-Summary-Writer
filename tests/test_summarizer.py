import unittest
from unittest.mock import MagicMock, patch
from src.summarizer import PRSummarizer, extract_retry_delay
from src.config import SummaryConfig


class TestSummarizerDelayAndQuota(unittest.TestCase):
    def setUp(self):
        self.config = SummaryConfig(
            github_token="fake-token",
            gemini_api_key="fake-key",
            github_repository="owner/repo",
            pr_number=1,
            model_name="auto"
        )
        with patch("src.summarizer.genai.Client"):
            self.summarizer = PRSummarizer(self.config)

    def test_extract_retry_delay_from_regex(self):
        err_msg = Exception("ResourceExhausted: 429 Resource has been exhausted (e.g. check quota). {'retryDelay': '4.5s'}")
        delay = extract_retry_delay(err_msg)
        self.assertEqual(delay, 4.5)

    def test_extract_retry_delay_from_seconds(self):
        err_msg = Exception("Please retry in 12.0s.")
        delay = extract_retry_delay(err_msg)
        self.assertEqual(delay, 12.0)

    def test_extract_retry_delay_large_daily_quota(self):
        err_msg = Exception("429 Quota exceeded. {'retryDelay': '50908.5s'}")
        delay = extract_retry_delay(err_msg)
        self.assertEqual(delay, 50908.5)
        self.assertTrue(delay > 15.0)

    def test_extract_retry_delay_none_when_absent(self):
        err_msg = Exception("500 Internal Server Error")
        delay = extract_retry_delay(err_msg)
        self.assertIsNone(delay)

    @patch("src.summarizer.time.sleep")
    def test_call_model_with_retry_fails_over_immediately_on_large_retry_delay(self, mock_sleep):
        # Setup generate_content to raise 429 with 50908s retryDelay
        self.summarizer.client.models.generate_content.side_effect = Exception(
            "429 Resource has been exhausted: {'retryDelay': '50908.5s'}"
        )

        with self.assertRaises(RuntimeError) as ctx:
            self.summarizer._call_model_with_retry("gemini-3.8-flash", "test prompt", max_retries=2)

        # Assert time.sleep was NEVER called for the 50908s delay
        mock_sleep.assert_not_called()
        self.assertIn("exhausted retries or quota", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

