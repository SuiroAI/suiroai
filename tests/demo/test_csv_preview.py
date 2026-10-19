"""Check that the demo preview renders only the delivered CSV table.

Cell comparisons cover escaping, formatting and row order without treating
the preview as a second analysis or allowing generated narrative content.

Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
import csv
from html.parser import HTMLParser
import io

import pytest

from suiroai.demo.csv_preview import render_csv_preview


class PreviewParser(HTMLParser):
    """Collect table cells and visible text from the generated document."""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.tags = []
        self.cell = None
        self.in_style = False
        self.outside_cells = []
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag == "tr":
            self.rows.append([])
        elif tag in {"td", "th"}:
            self.cell = ""
        elif tag == "style":
            self.in_style = True

    def handle_endtag(self, tag):
        if tag in {"td", "th"}:
            self.rows[-1].append(self.cell)
            self.cell = None
        elif tag == "style":
            self.in_style = False

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data
        elif not self.in_style and data.strip():
            self.outside_cells.append(data)


def test_preview_preserves_every_csv_cell_and_row_without_narrative():
    """Never normalize identifiers, decimals, Unicode, whitespace or quoted cells."""
    rows = [
        ["Product_ID", "Product_Name", "Store_ID", "OrderQty", "Notes"],
        ["0007", 'Tea, "green" & café', " S1 ", "0010", "first\r\nsecond"],
        ["P2", "東京", "S2", "0", ""],
        ["P2", "東京", "S2", "0", ""],
    ]
    buffer = io.StringIO(newline="")
    csv.writer(buffer).writerows(rows)
    source = buffer.getvalue().encode("utf-8")
    result = render_csv_preview(source)
    parsed = PreviewParser(result.decode("utf-8"))
    assert parsed.rows == rows
    assert parsed.tags.count("table") == 1
    assert parsed.outside_cells == ["Restocking list", "Restocking list"]
    assert render_csv_preview(source) == result
    assert source == buffer.getvalue().encode("utf-8")


def test_preview_escapes_supplied_html_in_headers_and_cells():
    """Untrusted strings remain literal text rather than markup or attributes."""
    source = b'"<script>bad()</script>",Product_Name\n"<img src=x onerror=bad()>","<a href=javascript:bad()>X</a> & test"\n'
    result = render_csv_preview(source).decode("utf-8")
    parsed = PreviewParser(result)
    assert parsed.rows == list(csv.reader(io.StringIO(source.decode())))
    assert not {"script", "img", "a", "iframe", "svg"}.intersection(parsed.tags)
    assert "&lt;script&gt;" in result
    assert "&amp; test" in result


def test_header_only_preview_has_no_invented_rows_or_summary():
    """An empty recommendation list remains a table with headers only."""
    parsed = PreviewParser(render_csv_preview(b"Product_ID,Store_ID,OrderQty\n").decode())
    assert parsed.rows == [["Product_ID", "Store_ID", "OrderQty"]]
    assert parsed.outside_cells == ["Restocking list", "Restocking list"]


def test_preview_accepts_utf8_bom_without_changing_header_text():
    """Treat the CSV encoding marker as metadata rather than a header cell."""
    parsed = PreviewParser(render_csv_preview(b"\xef\xbb\xbfProduct_ID,OrderQty\nP,1\n").decode())
    assert parsed.rows == [["Product_ID", "OrderQty"], ["P", "1"]]


@pytest.mark.parametrize("source", [b"", b"\n", b"\xff", b'Product_ID\n"unterminated'])
def test_preview_rejects_missing_headers_and_invalid_csv(source):
    """Fail explicitly instead of silently replacing invalid input bytes."""
    with pytest.raises(ValueError):
        render_csv_preview(source)
