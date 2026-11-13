import unittest
from unittest.mock import MagicMock
from src.pr_updater import (
    update_pr_description_text,
    extract_existing_summary,
    PRUpdater,
    START_TAG,
    END_TAG,
)


class TestPRUpdater(unittest.TestCase):
    def test_extract_existing_summary_empty(self):
        self.assertIsNone(extract_existing_summary(""))
        self.assertIsNone(extract_existing_summary(None))
        self.assertIsNone(extract_existing_summary("Just some manual notes without markers."))

    def test_extract_existing_summary_valid(self):
        body = (
            f"Some header\n\n{START_TAG}\n## Summary\nExisting summary content.\n{END_TAG}\n\nFooter"
        )
        extracted = extract_existing_summary(body)
        self.assertEqual(extracted, "## Summary\nExisting summary content.")

    def test_extract_existing_summary_legacy_marker(self):
        body = "<!-- PR-SUMMARIZER:START -->\nLegacy summary text\n<!-- PR-SUMMARIZER:END -->"
        extracted = extract_existing_summary(body)
        self.assertEqual(extracted, "Legacy summary text")

    def test_prupdater_get_existing_summary(self):
        mock_pr = MagicMock()
        mock_pr.body = f"{START_TAG}\n## Summary\nPrior content.\n{END_TAG}"
        updater = PRUpdater(mock_pr)
        self.assertEqual(updater.get_existing_summary(), "## Summary\nPrior content.")

    def test_empty_body_starts_directly_with_markers(self):
        summary = "## Summary\nThis is a cool PR."
        res = update_pr_description_text("", summary)
        self.assertNotIn("## Developer Notes & Rationale", res)
        self.assertEqual(res, f"{START_TAG}\n{summary}\n{END_TAG}")

    def test_existing_body_appends_block(self):
        original = "### My Notes\nFixed a critical issue with entity tracking."
        summary = "## Summary\nThis PR fixes tracking."
        res = update_pr_description_text(original, summary)
        self.assertTrue(res.startswith(original))
        self.assertIn(START_TAG, res)
        self.assertIn(summary, res)
        self.assertIn(END_TAG, res)

    def test_existing_markers_replaced_in_place(self):
        developer_intro = "### Architecture Notes\nDecoupled bond storage."
        old_summary = "Old automated text that should disappear."
        developer_outro = "### Testing Checklist\n- [x] Verified in dev environment."

        body_with_markers = (
            f"{developer_intro}\n\n"
            f"{START_TAG}\n{old_summary}\n{END_TAG}\n\n"
            f"{developer_outro}"
        )

        new_summary = "## Summary\nBrand new updated summary."
        updated = update_pr_description_text(body_with_markers, new_summary)

        # Developer notes must remain intact
        self.assertIn(developer_intro, updated)
        self.assertIn(developer_outro, updated)

        # Old summary replaced by new summary
        self.assertNotIn(old_summary, updated)
        self.assertIn(new_summary, updated)

    def test_case_insensitive_legacy_markers_replaced(self):
        body = (
            "Human text\n\n"
            "<!-- PR-SUMMARIZER:START -->\nOld text\n<!-- PR-SUMMARIZER:END -->\n\n"
            "Footer note"
        )
        new_summary = "Fresh summary"
        updated = update_pr_description_text(body, new_summary)
        self.assertIn("Human text", updated)
        self.assertIn("Footer note", updated)
        self.assertNotIn("Old text", updated)
        self.assertIn(new_summary, updated)


if __name__ == "__main__":
    unittest.main()
