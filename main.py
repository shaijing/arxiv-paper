import datetime
import sys
import time
from typing import Dict, List
import urllib
import feedparser
from easydict import EasyDict
from zoneinfo import ZoneInfo


def remove_duplicated_spaces(text: str) -> str:
    return " ".join(text.split())


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
    papers: List[Dict[str, str]], target_fileds: List[str] = ["cs", "stat"]
) -> List[Dict[str, str]]:
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
    keyword: str, column_names: List[str], max_result: int, link: str = "OR"
) -> List[Dict[str, str]]:
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
    column_names: List[str],
    max_result: int,
    link: str = "OR",
    retries: int = 6,
) -> List[Dict[str, str]]:
    for _ in range(retries):
        papers = get_daily_papers_by_keyword(keyword, column_names, max_result, link)
        if len(papers) > 0:
            return papers
        else:
            print("Unexpected empty list, retrying...")
            time.sleep(60 * 30)  # wait for 30 minutes
    # failed
    return None


def generate_table(papers: List[Dict[str, str]], ignore_keys: List[str] = []) -> str:
    formatted_papers = []
    keys = papers[0].keys()
    for paper in papers:
        # process fixed columns
        formatted_paper = EasyDict()
        ## Title and Link
        formatted_paper.Title = (
            "**" + "[{0}]({1})".format(paper["Title"], paper["Link"]) + "**"
        )
        ## Process Date (format: 2021-08-01T00:00:00Z -> 2021-08-01)
        formatted_paper.Date = paper["Date"].split("T")[0]

        # process other columns
        for key in keys:
            if key in ["Title", "Link", "Date"] or key in ignore_keys:
                continue
            elif key == "Abstract":
                # add show/hide button for abstract
                formatted_paper[key] = (
                    "<details><summary>Show</summary><p>{0}</p></details>".format(
                        paper[key]
                    )
                )
            elif key == "Authors":
                # NOTE only use the first author
                formatted_paper[key] = paper[key][0] + " et al."
            elif key == "Tags":
                tags = ", ".join(paper[key])
                if len(tags) > 10:
                    formatted_paper[key] = (
                        "<details><summary>{0}...</summary><p>{1}</p></details>".format(
                            tags[:5], tags
                        )
                    )
                else:
                    formatted_paper[key] = tags
            elif key == "Comment":
                if paper[key] == "":
                    formatted_paper[key] = ""
                elif len(paper[key]) > 20:
                    formatted_paper[key] = (
                        "<details><summary>{0}...</summary><p>{1}</p></details>".format(
                            paper[key][:5], paper[key]
                        )
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


if __name__ == "__main__":
    beijing_timezone = ZoneInfo("Asia/Shanghai")
    current_date = datetime.datetime.now(beijing_timezone).strftime("%Y-%m-%d")
    # get last update date from README.md
    with open("README.md", "r") as f:
        while True:
            line = f.readline()
            if "Last update:" in line:
                break
        last_update_date = line.split(": ")[1].strip()
        # if last_update_date == current_date:
        # sys.exit("Already updated today!")
    keyword = "llm"
    max_result = 100  # maximum query results from arXiv API for each keyword
    issues_result = 15  # maximum papers to be included in the issue

    # all columns: Title, Authors, Abstract, Link, Tags, Comment, Date
    # fixed_columns = ["Title", "Link", "Date"]

    column_names = ["Title", "Link", "Abstract", "Date", "Comment"]

    f_rm = open("README.md", "w")  # file for README.md
    f_rm.write("# Daily Papers\n")
    f_rm.write(
        f"The project automatically fetches the latest papers from arXiv based on keywords.\n\nThe subheadings in the README file represent the search keywords.\n\nOnly the most recent articles for each keyword are retained, up to a maximum of 100 papers.\n\nYou can click the 'Watch' button to receive daily email notifications.\n\nLast update: {current_date}\n\n"
    )
    f_rm.write(f"## {keyword}\n")
    if len(keyword.split()) == 1:
        link = "AND"  # for keyword with only one word, We search for papers containing this keyword in both the title and abstract.
    else:
        link = "OR"
    papers = get_daily_papers_by_keyword_with_retries(
        keyword, column_names, max_result, link
    )
    if papers is None:  # failed to get papers
        print("Failed to get papers!")
        f_rm.close()
        sys.exit("Failed to get papers!")
    rm_table = generate_table(papers)
    is_table = generate_table(papers[:issues_result], ignore_keys=["Abstract"])
    f_rm.write(rm_table)
    f_rm.write("\n\n")
    time.sleep(5)  # avoid being blocked by arXiv API

f_rm.close()
