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

    def test_writing_level_reaches_the_prompt(self):
        from app.prompt import build_user_prompt
        prompt = build_user_prompt("Hello.", "Natural", "Medium", "", writing_level="Simpler")
        self.assertIn("Writing level: Simpler.", prompt)
        self.assertIn("common words", prompt)

    def test_natural_prompt_avoids_forced_style_changes(self):
        from app.prompt import SYSTEM_PROMPT, STRENGTH_GUIDE
        self.assertIn("instead of forcing variation", SYSTEM_PROMPT)
        self.assertIn("sentence-by-sentence paraphraser", SYSTEM_PROMPT)
        self.assertIn("don't swap in synonyms just to make the text different", STRENGTH_GUIDE["Medium"])
        self.assertIn("level of formality", SYSTEM_PROMPT)

    def test_polish_strength_has_guide(self):
        from app.prompt import STRENGTH_GUIDE
        self.assertIn("Polish", STRENGTH_GUIDE)


class MeaningTests(unittest.TestCase):
    def test_flags_sentence_whose_claim_disappeared(self):
        from app.meaning import check_meaning
        original = "Managers compare candidates across several countries. Applicants expect flexible schedules and remote options."
        rewritten = "Applicants expect flexible schedules and remote options."
        flagged = check_meaning(original, rewritten)
        self.assertEqual(len(flagged), 1)
        self.assertIn("Managers", flagged[0]["sentence"])

    def test_reworded_but_covered_sentence_is_not_flagged(self):
        from app.meaning import check_meaning
        original = "The company launched the Orion platform in 2023 with twelve engineers."
        rewritten = "In 2023 the Orion platform was launched by the company, using twelve engineers."
        self.assertEqual(check_meaning(original, rewritten), [])


class NumberWordTests(unittest.TestCase):
    def test_spelled_out_numbers_count_as_kept(self):
        self.assertEqual(ai._missing({"12", "45"}, "a team of twelve and forty-five staff"), set())
        self.assertEqual(ai._missing({"12"}, "a team of some engineers"), {"12"})

    def test_name_is_not_missing_only_because_case_changed(self):
        needed = ai._facts("Information Technology improves communication.")
        self.assertIn("Technology", needed)
        self.assertEqual(ai._missing(needed, "Information technology improves communication."), set())


class RewriteTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(ai, "keep_model_warm")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_retries_when_facts_are_lost_then_accepts(self):
        replies = iter(["Costs went up.", "The price rose to $4,500 in 2024."])
        with (mock.patch.object(ai, "_chat", side_effect=lambda *a, **k: next(replies)),
              mock.patch.object(ai, "_semantic_issues", return_value=[])):
            text, warnings = ai.rewrite_text("The price is $4,500 in 2024.", "Natural", "Medium")
        self.assertIn("$4,500", text)
        self.assertEqual(warnings, [])

    def test_retry_tells_model_what_was_lost(self):
        original = (
            "On June 1, the team sold 200 tickets for $4,500. "
            "Buyers can cancel until June 10. Only 30 seats remain. "
            "The event starts at 7 p.m."
        )
        replies = iter([
            "The team sold tickets.",
            "The team sold 200 tickets for $4,500 on June 1. Buyers have until June 10 to cancel. "
            "Just 30 seats are still available. The event begins at 7 p.m.",
        ])
        calls = []

        def fake_chat(messages, *args, **kwargs):
            calls.append(messages)
            return next(replies)

        with (mock.patch.object(ai, "_chat", side_effect=fake_chat),
              mock.patch.object(ai, "_semantic_issues", return_value=[])):
            text, warnings = ai.rewrite_text(original, "Natural", "Medium")

        self.assertEqual(len(calls), 2)
        self.assertIn("Restore these exact details", calls[1][-1]["content"])
        self.assertEqual(warnings, [])
        self.assertIn("$4,500", text)
        self.assertIn("30 seats", text)

    def test_retries_an_unchanged_medium_rewrite(self):
        original = (
            "Information Technology (IT) is the use of computers, software, and the internet to store, process, and share information. "
            "It plays an important role in our daily lives. IT helps people communicate easily, learn new things, and complete their work "
            "more efficiently. Today, IT is widely used in education, healthcare, business, and many other fields. Students can attend "
            "online classes, doctors can maintain digital medical records, and businesses can communicate with customers around the world. "
            "It also provides many job opportunities for young people."
        )
        revised = (
            "Information Technology (IT) refers to the computers, software, and internet people use to store, process, and share information. "
            "It's now part of everyday life. With IT, people can stay in touch, learn new skills, and get their work done more efficiently. "
            "Today, people rely on IT in education, healthcare, business, and many other areas. Students take classes online, doctors keep "
            "digital medical records, and companies stay in touch with customers worldwide. The field also offers young people plenty of "
            "job opportunities."
        )
        replies = iter([original, revised])
        calls = []

        def fake_chat(messages, *args, **kwargs):
            calls.append(messages)
            return next(replies)

        with (mock.patch.object(ai, "_chat", side_effect=fake_chat),
              mock.patch.object(ai, "_semantic_issues", return_value=[])):
            text, warnings = ai.rewrite_text(original, "Natural", "Medium")

        self.assertEqual(len(calls), 2)
        self.assertIn("stayed too close", calls[1][-1]["content"])
        self.assertNotEqual(text, original)
        self.assertEqual(warnings, [])

    def test_warns_when_model_cannot_rephrase_text(self):
        original = "Clear wording can still be rewritten in a fresh way without losing the point."
        with mock.patch.object(ai, "_chat", return_value=original):
            text, warnings = ai.rewrite_text(original, "Natural", "Medium")
        self.assertEqual(text, original)
        self.assertIn("stayed too close", warnings[0])

    def test_retries_when_semantic_review_finds_a_changed_claim(self):
        original = "The change reduced monthly costs by 20 percent."
        replies = iter([
            "The change increased monthly costs by 20 percent.",
            "The change lowered monthly costs by 20 percent.",
        ])
        calls = []

        def fake_chat(messages, *args, **kwargs):
            calls.append(messages)
            return next(replies)

        with (mock.patch.object(ai, "_chat", side_effect=fake_chat),
              mock.patch.object(ai, "_semantic_issues", side_effect=[["It reverses reduced to increased."], []])):
            text, warnings = ai.rewrite_text(original, "Natural", "Medium")

        self.assertIn("lowered monthly costs", text)
        self.assertIn("It reverses reduced to increased", calls[1][-1]["content"])
        self.assertEqual(warnings, [])

    def test_warns_when_semantic_issue_remains_after_retry(self):
        original = "The change reduced monthly costs by 20 percent."
        with (mock.patch.object(ai, "_chat", return_value="The change increased monthly costs by 20 percent."),
              mock.patch.object(ai, "_semantic_issues", return_value=["It reverses reduced to increased."])):
            text, warnings = ai.rewrite_text(original, "Natural", "Medium")

        self.assertIn("increased monthly costs", text)
        self.assertIn("meaning review", warnings[0])
        self.assertIn("reverses", warnings[0])

    def test_rejects_truncated_model_response(self):
        response = mock.Mock(status_code=200)
        response.json.return_value = {
            "choices": [{"finish_reason": "length", "message": {"content": "Incomplete"}}]
        }
        with mock.patch.object(ai.requests, "post", return_value=response):
            with self.assertRaisesRegex(ai.AIRequestError, "stopped before finishing"):
                ai._chat([{"role": "user", "content": "Rewrite this."}])

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
