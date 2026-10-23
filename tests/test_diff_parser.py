import unittest
from src.diff_parser import is_summarizable_file, filter_diff_for_summary


class TestDiffParser(unittest.TestCase):
    def test_is_summarizable_file(self):
        # Code and configs should be included
        self.assertTrue(is_summarizable_file("src/main/java/com/example/MyClass.java"))
        self.assertTrue(is_summarizable_file("src/main/resources/data/mod/recipe.json"))
        self.assertTrue(is_summarizable_file("build.gradle"))
        self.assertTrue(is_summarizable_file("src/script.py"))

        # Assets, models, locks, and binaries should be excluded
        self.assertFalse(is_summarizable_file("assets/mod/textures/item.png"))
        self.assertFalse(is_summarizable_file("assets/mod/geo/item.geo.json"))
        self.assertFalse(is_summarizable_file("gradle.lockfile"))
        self.assertFalse(is_summarizable_file("package-lock.json"))
        self.assertFalse(is_summarizable_file("build/classes/MyClass.class"))
        self.assertFalse(is_summarizable_file(".gradle/cache.bin"))

    def test_filter_diff_for_summary(self):
        sample_diff = (
            "diff --git a/src/MyClass.java b/src/MyClass.java\n"
            "index 123..456 100644\n"
            "--- a/src/MyClass.java\n"
            "+++ b/src/MyClass.java\n"
            "@@ -1,3 +1,4 @@\n"
            "+// new code\n"
            "diff --git a/assets/texture.png b/assets/texture.png\n"
            "index 000..111 100644\n"
            "Binary files differ\n"
            "diff --git a/gradle.lockfile b/gradle.lockfile\n"
            "index 222..333 100644\n"
            "--- a/gradle.lockfile\n"
            "+++ b/gradle.lockfile\n"
            "+locked\n"
        )
        filtered_diff, included, ignored = filter_diff_for_summary(sample_diff)
        self.assertIn("src/MyClass.java", included)
        self.assertIn("assets/texture.png", ignored)
        self.assertIn("gradle.lockfile", ignored)
        self.assertIn("+// new code", filtered_diff)
        self.assertNotIn("Binary files differ", filtered_diff)


if __name__ == "__main__":
    unittest.main()
