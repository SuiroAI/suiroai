"""Render the delivered restocking CSV as a deterministic demo table.

The preview displays the CSV's headers and cells without interpreting values,
adding findings or asking Data to author a separate narrative. The app response
owns the explanation; this HTML exists only to show the same operational list.

Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from __future__ import annotations

import csv
from html import escape
import io


def render_csv_preview(data: bytes) -> bytes:
    """Return passive UTF-8 HTML preserving CSV cell strings and their order."""
    try:
        records = list(csv.reader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True))
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("Restocking preview requires valid UTF-8 CSV") from exc
    if not records or not records[0]:
        raise ValueError("Restocking preview requires a CSV header")

    def row(cells: list[str], tag: str) -> str:
        return "<tr>" + "".join(f"<{tag}>{escape(cell)}</{tag}>" for cell in cells) + "</tr>"

    header = row(records[0], "th")
    body = "\n".join(row(cells, "td") for cells in records[1:])
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>Restocking list</title>\n"
        "<style>\n"
        "body{margin:0;padding:32px;color:#172033;background:#f5f7fb;"
        "font-family:system-ui,sans-serif;}\n"
        "main{max-width:1600px;margin:auto;}\n"
        "h1{margin:0 0 24px;font-size:28px;}\n"
        ".table-scroll{overflow:auto;background:white;border:1px solid #d7dfeb;"
        "border-radius:8px;max-height:calc(100vh - 130px);}\n"
        "table{border-collapse:separate;border-spacing:0;width:100%;font-size:14px;}\n"
        "th,td{padding:12px 16px;text-align:left;vertical-align:top;"
        "border-bottom:1px solid #e2e8f0;white-space:pre-wrap;}\n"
        "th{position:sticky;top:0;background:#e9eff8;font-weight:650;}\n"
        "tbody tr:nth-child(even){background:#f8fafc;}\n"
        "@media print{body{padding:0;background:white;}"
        ".table-scroll{overflow:visible;max-height:none;}th{position:static;}}\n"
        "</style>\n</head>\n<body>\n<main>\n<h1>Restocking list</h1>\n"
        "<div class=\"table-scroll\"><table>\n<thead>" + header + "</thead>\n"
        "<tbody>\n" + body + "\n</tbody>\n</table></div>\n"
        "</main>\n</body>\n</html>\n"
    ).encode("utf-8")
