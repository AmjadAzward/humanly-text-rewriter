import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import ai  # noqa: E402


class HelperTests(unittest.TestCase):
    def test_clean_strips_preamble_quotes_and_tags(self):
        self.assertEqual(ai._clean('Here is the rewritten text:\n"Hello there."'), "Hello there.")
        self.assertEqual(ai._clean("<text>Hi</text>"), "Hi")

    def test_facts_finds_numbers_urls_and_names(self):
        facts = ai._facts("Pay $85,000 in 2024. Then Sarah met Acme at https://x.io/a.")
        for expected in ("85,000", "2024", "Acme", "https://x.io/a"):
            self.assertIn(expected, facts)

    def test_chunks_rejoin_to_original_words(self):
        text = " ".join(f"Sentence number {i} has some words in it." for i in range(120)) + "\n\nShort second paragraph."
        chunks = ai._split_chunks(text)
        self.assertGreater(len(chunks), 1)
        self.assertEqual("".join(chunks).split(), text.split())


class ReviewAndVoiceTests(unittest.TestCase):
    def test_review_flags_stiff_phrases_and_counts_repeats(self):
        from app.review import review_text
        found = review_text("It is important to note this. Moreover, we utilize tools. Moreover, we leverage them.")
        phrases = [f["phrase"].lower() for f in found]
        self.assertIn("moreover", phrases)
        self.assertTrue(any(f["phrase"].lower() == "moreover" and f["count"] == 2 for f in found))
        self.assertTrue(any("utiliz" in p for p in phrases))

    def test_review_clean_text_has_no_findings(self):
        from app.review import review_text
        self.assertEqual(review_text("I fixed the bug and shipped it on Friday."), [])

    def test_voice_sample_reaches_the_prompt(self):
        from app.prompt import build_user_prompt
        prompt = build_user_prompt("Hello.", "Natural", "Polish", "", "I write short. Like this.")
        self.assertIn("<voice>", prompt)
        self.assertIn("I write short.", prompt)
        self.assertNotIn("<voice>", build_user_prompt("Hello.", "Natural", "Polish", "", ""))

    def test_polish_strength_has_guide(self):
        from app.prompt import STRENGTH_GUIDE
        self.assertIn("Polish", STRENGTH_GUIDE)


class NumberWordTests(unittest.TestCase):
    def test_spelled_out_numbers_count_as_kept(self):
        self.assertEqual(ai._missing({"12", "45"}, "a team of twelve and forty-five staff"), set())
        self.assertEqual(ai._missing({"12"}, "a team of some engineers"), {"12"})


class RewriteTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(ai, "keep_model_warm")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_retries_when_facts_are_lost_then_accepts(self):
        replies = iter(["Costs went up.", "The price rose to $4,500 in 2024."])
        with mock.patch.object(ai, "_chat", side_effect=lambda *a, **k: next(replies)):
            text, warnings = ai.rewrite_text("The price is $4,500 in 2024.", "Natural", "Medium")
        self.assertIn("$4,500", text)
        self.assertEqual(warnings, [])

    def test_warns_when_facts_never_recovered(self):
        with mock.patch.object(ai, "_chat", return_value="Costs went up."):
            text, warnings = ai.rewrite_text("The price is $4,500 in 2024.", "Natural", "Medium")
        self.assertEqual(len(warnings), 1)
        self.assertIn("4,500", warnings[0])

    def test_warns_when_sentences_are_dropped(self):
        original = "The cat sat down. The dog barked loudly. A bird flew past. The sun was bright. Rain came later."
        with mock.patch.object(ai, "_chat", return_value="Animals were around and the weather changed."):
            _, warnings = ai.rewrite_text(original, "Natural", "Strong")
        self.assertEqual(len(warnings), 1)
        self.assertIn("dropped or merged", warnings[0])

    def test_keeps_paragraph_breaks_between_chunks(self):
        para = " ".join(["word"] * 230) + "."
        with mock.patch.object(ai, "_chat", side_effect=lambda *a, **k: "Rewritten."):
            text, _ = ai.rewrite_text(f"{para}\n\n{para}", "Natural", "Light")
        self.assertEqual(text, "Rewritten.\n\nRewritten.")


if __name__ == "__main__":
    unittest.main()
