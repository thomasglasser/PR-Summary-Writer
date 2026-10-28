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
            model_name="auto",
            thinking_budget=1024
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

    @patch("src.summarizer.time.sleep")
    def test_call_model_retries_on_network_disconnect(self, mock_sleep):
        mock_response = MagicMock()
        mock_response.text = "Generated summary markdown"

        # First call fails with disconnect, second succeeds
        self.summarizer.client.models.generate_content.side_effect = [
            Exception("Server disconnected without sending a response."),
            mock_response
        ]

        result = self.summarizer._call_model_with_retry("gemini-3.8-flash", "test prompt", max_retries=3)
        self.assertEqual(result, "Generated summary markdown")
        # Assert sleep was called with short 2.0s delay
        mock_sleep.assert_called_with(2.0)

    @patch("src.summarizer.time.sleep")
    def test_call_model_exponential_backoff_on_503(self, mock_sleep):
        mock_response = MagicMock()
        mock_response.text = "Generated summary markdown"

        # First call 503, second call succeeds
        self.summarizer.client.models.generate_content.side_effect = [
            Exception("503 UNAVAILABLE: This model is currently experiencing high demand."),
            mock_response
        ]

        result = self.summarizer._call_model_with_retry("gemini-3.7-flash", "test prompt", max_retries=3)
        self.assertEqual(result, "Generated summary markdown")
        # 5.0 * attempt (attempt=1) -> 5.0
        mock_sleep.assert_called_with(5.0)

    @patch("src.summarizer.resolve_candidate_models", return_value=["gemini-3.8-flash", "gemini-3.7-flash"])
    def test_generate_summary_fails_over_on_quota_exhaustion(self, mock_resolve_models):
        from src.summarizer import QuotaExceededException
        with patch.object(self.summarizer, "_call_model_with_retry") as mock_call:
            mock_call.side_effect = [
                QuotaExceededException("Model quota exceeded"),
                "Summary from 3.7"
            ]
            res = self.summarizer.generate_summary("Title", "main", "feat", "diff", ["file.txt"])
            self.assertEqual(res, "Summary from 3.7")
            self.assertEqual(mock_call.call_count, 2)
            self.assertEqual(mock_call.call_args_list[0][0][0], "gemini-3.8-flash")
            self.assertEqual(mock_call.call_args_list[1][0][0], "gemini-3.7-flash")

    @patch("src.summarizer.time.sleep")
    def test_call_model_raises_high_demand_exception_when_exhausted(self, mock_sleep):
        from src.summarizer import HighDemandException
        self.summarizer.client.models.generate_content.side_effect = Exception("503 UNAVAILABLE: high demand")
        with self.assertRaises(HighDemandException):
            self.summarizer._call_model_with_retry("gemini-3.7-flash", "test prompt", max_retries=2)

    @patch("src.summarizer.time.sleep")
    def test_call_model_raises_quota_exceeded_exception_when_exhausted(self, mock_sleep):
        from src.summarizer import QuotaExceededException
        self.summarizer.client.models.generate_content.side_effect = Exception("429 ResourceExhausted: rate limit")
        with self.assertRaises(QuotaExceededException):
            self.summarizer._call_model_with_retry("gemini-3.7-flash", "test prompt", max_retries=2)


if __name__ == "__main__":
    unittest.main()
