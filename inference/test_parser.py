import unittest
from agent import Parser


class TestParser(unittest.TestCase):
    def setUp(self):
        self.parser = Parser()
        # Register tools with their tags
        self.parser.register_tool("search", "SEARCH")
        self.parser.register_tool("coq-prover", "SCRIPT")

    def test_extract_search_tool_call(self):
        text = "I think we should <SEARCH>mathematical induction principles</SEARCH> to solve this."
        result = self.parser.extract_next_tool_call(text)

        self.assertIsNotNone(result)
        self.assertEqual(result[0], "search")
        self.assertEqual(result[1], "mathematical induction principles")

    def test_extract_coq_tool_call(self):
        text = "Let's try this proof: <SCRIPT>intros n. induction n; auto.</SCRIPT>"
        result = self.parser.extract_next_tool_call(text)

        self.assertIsNotNone(result)
        self.assertEqual(result[0], "coq-prover")
        self.assertEqual(result[1], "intros n. induction n; auto.")

    def test_no_tool_calls(self):
        text = "This text doesn't contain any tool calls."
        result = self.parser.extract_next_tool_call(text)

        self.assertIsNone(result)

    def test_empty_tool_calls(self):
        text = "This has an empty search call: <SEARCH></SEARCH>"
        result = self.parser.extract_next_tool_call(text)

        self.assertIsNotNone(result)
        self.assertEqual(result[0], "search")
        self.assertEqual(result[1], "")  # Empty content

    def test_malformed_tags(self):
        text = "<SEARCH>incomplete tag"
        result = self.parser.extract_next_tool_call(text)

        self.assertIsNone(result)  # Should not match incomplete tags

    def test_text_with_angle_brackets(self):
        text = "<SEARCH>Use angle brackets like < and > in math</SEARCH>"
        result = self.parser.extract_next_tool_call(text)

        self.assertIsNotNone(result)
        self.assertEqual(result[0], "search")
        self.assertEqual(result[1], "Use angle brackets like < and > in math")


if __name__ == "__main__":
    unittest.main()
