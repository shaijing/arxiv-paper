import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# 参数
max_results = 30
keyword = "llm"
keyword = '"' + keyword + '"'
op = "AND"

# 构造URL
arxiv_url = f"https://export.arxiv.org/api/query?search_query=ti:{keyword}+{op}+abs:{keyword}&max_results={max_results}&sortBy=lastUpdatedDate"
arxiv_url = urllib.parse.quote(arxiv_url, safe="%/:=&?~#+!$,;'@()*[]")

# 请求
response = urllib.request.urlopen(arxiv_url).read().decode("utf-8")

# 解析XML
root = ET.fromstring(response)

# Atom feed namespace
ns = {"atom": "http://www.w3.org/2005/Atom"}


# 遍历每个<entry>
for entry in root.findall("atom:entry", ns):
    title = entry.find("atom:title", ns).text.strip()
    summary = entry.find("atom:summary", ns).text.strip()
    published = entry.find("atom:published", ns).text.strip()
    updated = entry.find("atom:updated", ns).text.strip()

    authors = [
        author.find("atom:name", ns).text.strip()
        for author in entry.findall("atom:author", ns)
    ]
    link = None
    pdf_link = None
    for lnk in entry.findall("atom:link", ns):
        if lnk.attrib.get("type") == "application/pdf":
            pdf_link = lnk.attrib["href"]
        if lnk.attrib.get("type") == "text/html":
            link = lnk.attrib["href"]

    print(f"Title: {title}")
    print(f"Authors: {', '.join(authors)}")
    print(f"Published: {published}")
    print(f"Updated: {updated}")
    print(f"Link: {link}")
    print(f"PDF Link: {pdf_link}")
    print(f"Summary: {summary}")
    print("-" * 80)
