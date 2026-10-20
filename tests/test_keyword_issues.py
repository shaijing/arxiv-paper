import io
import json
import os
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest.mock import patch

import main


class KeywordIssueTests(unittest.TestCase):
    def test_load_keywords_paginates_and_ignores_pull_requests_and_duplicates(self):
        first_page = [{"title": "LLM"}] + [
            {"title": f"PR {index}", "pull_request": {}} for index in range(99)
        ]
        second_page = [
            {"title": " llm "},
            {"title": "graph   neural network"},
            {"title": "   "},
        ]
        pages = [first_page, second_page]
        requested_pages = []

        def fake_urlopen(request, timeout):
            self.assertEqual(timeout, 30)
            self.assertEqual(request.get_header("Authorization"), "Bearer test-token")
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)
            requested_pages.append(query["page"][0])
            self.assertEqual(query["labels"], ["keyword"])
            return io.BytesIO(json.dumps(pages.pop(0)).encode())

        with patch.object(main.urllib.request, "urlopen", side_effect=fake_urlopen):
            keywords = main.load_keywords_from_issues("owner/repo", "test-token")

        self.assertEqual(keywords, ["LLM", "graph neural network"])
        self.assertEqual(requested_pages, ["1", "2"])

    def test_main_writes_one_section_per_keyword_and_skips_empty_results(self):
        paper = {
            "Title": "Sample paper",
            "Link": "https://arxiv.org/abs/1234.5678",
            "Abstract": "Sample abstract",
            "Date": "2026-10-20T00:00:00Z",
            "Comment": "",
        }
        with tempfile.TemporaryDirectory() as directory:
            readme = Path(directory) / "README.md"
            readme.write_text("old content\n")
            previous_directory = Path.cwd()
            try:
                os.chdir(directory)
                with (
                    patch.dict(
                        os.environ,
                        {"GITHUB_REPOSITORY": "owner/repo", "GITHUB_TOKEN": "token"},
                    ),
                    patch.object(
                        main,
                        "load_keywords_from_issues",
                        return_value=["LLM", "no result", "graph neural network"],
                    ),
                    patch.object(
                        main,
                        "get_daily_papers_by_keyword_with_retries",
                        side_effect=[[paper], None, [paper]],
                    ) as fetch_papers,
                    patch.object(main.time, "sleep"),
                ):
                    main.main()
            finally:
                os.chdir(previous_directory)

            result = readme.read_text()
            self.assertIn("[Manage search keywords](KEYWORDS.md)", result)
            self.assertIn("## LLM\n", result)
            self.assertIn("## graph neural network\n", result)
            self.assertNotIn("## no result\n", result)
            self.assertEqual(result.count("Sample paper"), 2)
            self.assertEqual(
                [call.args[3] for call in fetch_papers.call_args_list],
                ["AND", "OR", "OR"],
            )

    def test_main_preserves_readme_when_no_keywords_or_papers(self):
        with tempfile.TemporaryDirectory() as directory:
            readme = Path(directory) / "README.md"
            readme.write_text("old content\n")
            previous_directory = Path.cwd()
            try:
                os.chdir(directory)
                with (
                    patch.dict(
                        os.environ,
                        {"GITHUB_REPOSITORY": "owner/repo", "GITHUB_TOKEN": "token"},
                    ),
                    patch.object(
                        main, "load_keywords_from_issues", side_effect=[[], ["LLM"]]
                    ),
                    patch.object(
                        main,
                        "get_daily_papers_by_keyword_with_retries",
                        return_value=None,
                    ),
                ):
                    main.main()
                    self.assertEqual(readme.read_text(), "old content\n")
                    main.main()
                    self.assertEqual(readme.read_text(), "old content\n")
            finally:
                os.chdir(previous_directory)


if __name__ == "__main__":
    unittest.main()
