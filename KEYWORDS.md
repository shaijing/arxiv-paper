# Managing paper keywords

The daily workflow uses open GitHub Issues to choose search keywords.

1. Create a repository label named `keyword` (one-time setup).
2. Open one Issue per keyword. Put only the search term in the Issue title, such as `llm` or `graph neural network`, and apply the `keyword` label.
3. Edit the title to change the keyword, or close the Issue to stop tracking it.

The workflow reads all open Issues with that label each day. It ignores pull requests and duplicate titles, then creates one README section per keyword. If there are no keywords or no matching papers, it leaves the existing README unchanged. A keyword with no matching papers is skipped for that run.

For a local run, set `GITHUB_REPOSITORY` to `owner/repository` and `GITHUB_TOKEN` to a token with Issues read permission, then run `uv run main.py`.
