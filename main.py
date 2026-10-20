import datetime
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

import feedparser

from easydict import EasyDict


def remove_duplicated_spaces(text: str) -> str:
    return " ".join(text.split())


def load_keywords_from_issues(repository: str, token: str) -> list[str]:
    keywords = []
    seen = set()
    page = 1
    while True:
        query = urllib.parse.urlencode(
            {"state": "open", "labels": "keyword", "per_page": 100, "page": page}
        )
        url = f"https://api.github.com/repos/{repository}/issues?{query}"
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            issues = json.load(response)
        for issue in issues:
            if "pull_request" in issue:
                continue
            keyword = remove_duplicated_spaces(issue["title"])
            if keyword and keyword.casefold() not in seen:
                seen.add(keyword.casefold())
                keywords.append(keyword)
        if len(issues) < 100:
            return keywords
        page += 1


class QueryWay:
    ti = "ti"  # Title
    au = "au"  # Author
    abs = "abs"  # Abstract
    co = "co"  # Comment
    jr = "jr"  # Journal Reference
    cat = "cat"  # Subject Category
    rn = "rn"  # Report Number
    id = "id"  # Id (use id_list instead)
    all = "all"  # All of the above


class QueryOpertor:
    AND = "AND"
    OR = "OR"
    ANDNOT = "ANDNOT"


def request_paper_with_arXiv_api(keyword: str, max_results: int = 30, op: str = "OR"):
    # max_results = 30
    # keyword = "llm"
    # op = "AND"
    keyword = '"' + keyword + '"'
    arxiv_url = f"https://export.arxiv.org/api/query?search_query={QueryWay.ti}:{keyword}+{op}+{QueryWay.abs}:{keyword}&max_results={max_results}&sortBy=lastUpdatedDate"
    arxiv_url = urllib.parse.quote(arxiv_url, safe="%/:=&?~#+!$,;'@()*[]")
    response = urllib.request.urlopen(arxiv_url).read().decode("utf-8")
    feed = feedparser.parse(response)
    papers = []
    for item in feed.entries:
        entry = EasyDict(item)
        paper = EasyDict()
        # title
        paper.Title = remove_duplicated_spaces(entry.title.replace("\n", " "))
        # abstract
        paper.Abstract = remove_duplicated_spaces(entry.summary.replace("\n", " "))
        # authors
        paper.Authors = [
            remove_duplicated_spaces(_["name"].replace("\n", " "))
            for _ in entry.authors
        ]
        # link
        paper.Link = remove_duplicated_spaces(entry.link.replace("\n", " "))
        # tags
        paper.Tags = [
            remove_duplicated_spaces(_["term"].replace("\n", " ")) for _ in entry.tags
        ]
        # comment
        paper.Comment = remove_duplicated_spaces(
            entry.get("arxiv_comment", "").replace("\n", " ")
        )
        # date
        paper.Date = entry.updated

        papers.append(paper)
    return papers


def filter_tags(
    papers: list[dict[str, str]], target_fileds: list[str] | None = None
) -> list[dict[str, str]]:
    if target_fileds is None:
        target_fileds = ["cs", "stat"]
    # filtering tags: only keep the papers in target_fileds
    results = []
    for paper in papers:
        tags = paper.Tags
        for tag in tags:
            if tag.split(".")[0] in target_fileds:
                results.append(paper)
                break
    return results


def get_daily_papers_by_keyword(
    keyword: str, column_names: list[str], max_result: int, link: str = "OR"
) -> list[dict[str, str]]:
    # get papers
    papers = request_paper_with_arXiv_api(
        keyword, max_result, link
    )  # NOTE default columns: Title, Authors, Abstract, Link, Tags, Comment, Date
    # NOTE filtering tags: only keep the papers in cs field
    # TODO filtering more
    papers = filter_tags(papers)
    # select columns for display
    papers = [
        {column_name: paper[column_name] for column_name in column_names}
        for paper in papers
    ]
    return papers


def get_daily_papers_by_keyword_with_retries(
    keyword: str,
    column_names: list[str],
    max_result: int,
    link: str = "OR",
    retries: int = 3,
) -> list[dict[str, str]] | None:
    for attempt in range(retries):
        papers = get_daily_papers_by_keyword(keyword, column_names, max_result, link)
        if papers:
            return papers
        if attempt < retries - 1:
            print("Unexpected empty list, retrying...")
            time.sleep(5)
    return None


def generate_table(
    papers: list[dict[str, str]], ignore_keys: list[str] | None = None
) -> str:
    if ignore_keys is None:
        ignore_keys = []
    formatted_papers = []
    keys = papers[0].keys()
    for paper in papers:
        # process fixed columns
        formatted_paper = EasyDict()
        ## Title and Link
        formatted_paper.Title = f"**[{paper['Title']}]({paper['Link']})**"
        ## Process Date (format: 2021-08-01T00:00:00Z -> 2021-08-01)
        formatted_paper.Date = paper["Date"].split("T")[0]

        # process other columns
        for key in keys:
            if key in ["Title", "Link", "Date"] or key in ignore_keys:
                continue
            elif key == "Abstract":
                # add show/hide button for abstract
                formatted_paper[key] = (
                    f"<details><summary>Show</summary><p>{paper[key]}</p></details>"
                )
            elif key == "Authors":
                # NOTE only use the first author
                formatted_paper[key] = paper[key][0] + " et al."
            elif key == "Tags":
                tags = ", ".join(paper[key])
                if len(tags) > 10:
                    formatted_paper[key] = (
                        f"<details><summary>{tags[:5]}...</summary><p>{tags}</p></details>"
                    )
                else:
                    formatted_paper[key] = tags
            elif key == "Comment":
                if paper[key] == "":
                    formatted_paper[key] = ""
                elif len(paper[key]) > 20:
                    formatted_paper[key] = (
                        f"<details><summary>{paper[key][:5]}...</summary><p>{paper[key]}</p></details>"
                    )
                else:
                    formatted_paper[key] = paper[key]
        formatted_papers.append(formatted_paper)

    # generate header
    columns = formatted_papers[0].keys()
    # highlight headers
    columns = ["**" + column + "**" for column in columns]
    header = "| " + " | ".join(columns) + " |"
    header = (
        header
        + "\n"
        + "| "
        + " | ".join(["---"] * len(formatted_papers[0].keys()))
        + " |"
    )
    # generate the body
    body = ""
    for paper in formatted_papers:
        body += "\n| " + " | ".join(paper.values()) + " |"
    return header + body


def get_daily_date():
    # get beijing time in the format of "March 1, 2021"
    beijing_timezone = ZoneInfo("Asia/Shanghai")
    today = datetime.datetime.now(beijing_timezone)
    return today.strftime("%B %d, %Y")


def main() -> None:
    repository = os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GITHUB_TOKEN")
    if not repository or not token:
        sys.exit("GITHUB_REPOSITORY and GITHUB_TOKEN are required")
    keywords = load_keywords_from_issues(repository, token)
    if not keywords:
        print("No open issues labeled 'keyword'; README.md was not changed.")
        return

    beijing_timezone = ZoneInfo("Asia/Shanghai")
    current_date = datetime.datetime.now(beijing_timezone).strftime("%Y-%m-%d")
    max_result = 100  # maximum query results from arXiv API for each keyword
    column_names = ["Title", "Link", "Abstract", "Date", "Comment"]
    sections = []
    for index, keyword in enumerate(keywords):
        if index:
            time.sleep(5)  # avoid being blocked by arXiv API
        link = "AND" if len(keyword.split()) == 1 else "OR"
        papers = get_daily_papers_by_keyword_with_retries(
            keyword, column_names, max_result, link
        )
        if papers:
            sections.append(f"## {keyword}\n{generate_table(papers)}")
        else:
            print(f"No papers found for {keyword!r}; skipping it.")
    if not sections:
        print("No papers found for any keyword; README.md was not changed.")
        return

    with open("README.md", "w") as f_rm:
        f_rm.write("# Daily Papers\n")
        f_rm.write(
            f"The project automatically fetches the latest papers from arXiv based on keywords.\n\n[Manage search keywords](KEYWORDS.md) through GitHub Issues.\n\nThe subheadings in the README file represent the search keywords.\n\nOnly the most recent articles for each keyword are retained, up to a maximum of 100 papers.\n\nYou can click the 'Watch' button to receive daily email notifications.\n\nLast update: {current_date}\n\n"
        )
        f_rm.write("\n\n".join(sections))
        f_rm.write("\n")


if __name__ == "__main__":
    main()
