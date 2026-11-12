"""Read official Uwajima HTML tables without discarding merged-cell scope."""

from html.parser import HTMLParser
from urllib.parse import urljoin
import re


def content(body):
    start = "<!-- main_bodyここから -->".encode()
    end = "<!-- main_bodyここまで -->".encode()
    if body.count(start) != 1 or body.count(end) != 1:
        raise ValueError("Official main body boundaries changed")
    return body.split(start, 1)[1].split(end, 1)[0].strip()


class Document(HTMLParser):
    def __init__(self, html, url=""):
        super().__init__()
        self.url = url
        self.links = []
        self.tables = []
        self.parts = []
        self.table = None
        self.row = None
        self.cell = None
        self.anchor = None
        self.ignored = 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style"}:
            self.ignored += 1
        if self.ignored:
            return
        if tag == "table":
            if self.table is not None:
                raise ValueError("Unexpected nested official table")
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in {"td", "th"} and self.row is not None:
            self.cell = dict(
                text="",
                links=[],
                rowspan=int(attrs.get("rowspan", 1)),
                colspan=int(attrs.get("colspan", 1)),
            )
        elif tag == "a" and attrs.get("href"):
            self.anchor = dict(url=urljoin(self.url, attrs["href"]), label="")
        elif tag == "br":
            self.handle_data("\n")
        if tag in {"p", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")

    def handle_data(self, text):
        if self.ignored:
            return
        self.parts.append(text)
        if self.cell is not None:
            self.cell["text"] += text
        if self.anchor is not None:
            self.anchor["label"] += text

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.ignored = max(0, self.ignored - 1)
            return
        if self.ignored:
            return
        if tag == "a" and self.anchor is not None:
            self.anchor["label"] = self.anchor["label"].strip()
            self.links.append(self.anchor)
            if self.cell is not None:
                self.cell["links"].append(self.anchor)
            self.anchor = None
        elif tag in {"td", "th"} and self.cell is not None:
            self.cell["text"] = re.sub(r"[ \t\r\f\v]+", " ", self.cell["text"]).strip()
            self.row.append(self.cell)
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None
        if tag in {"p", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")

    @property
    def text(self):
        return re.sub(r"\n\s*\n+", "\n", "".join(self.parts)).strip()


def expanded(table):
    """Repeat explicit HTML rowspan/colspan values, never infer blank cells."""
    result = []
    pending = {}
    for cells in table:
        row = []
        column = 0

        def consume():
            nonlocal column
            while column in pending:
                cell, remaining = pending[column]
                row.append(cell)
                if remaining == 1:
                    del pending[column]
                else:
                    pending[column] = (cell, remaining - 1)
                column += 1

        for cell in cells:
            consume()
            for _ in range(cell["colspan"]):
                row.append(cell)
                if cell["rowspan"] > 1:
                    pending[column] = (cell, cell["rowspan"] - 1)
                column += 1
        consume()
        result.append(row)
    if pending:
        raise ValueError("Unfinished HTML rowspan")
    return result
