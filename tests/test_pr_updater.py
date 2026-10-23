import unittest
from src.pr_updater import update_pr_description_text, START_TAG, END_TAG


class TestPRUpdater(unittest.TestCase):
    def test_empty_body_inserts_template(self):
        summary = "## Summary\nThis is a cool PR."
        res = update_pr_description_text("", summary)
        self.assertIn("## Developer Notes & Rationale", res)
        self.assertIn(START_TAG, res)
        self.assertIn(summary, res)
        self.assertIn(END_TAG, res)

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
