#!/usr/bin/env python3
"""Append a fresh JobLeads scrape into a provider tracking XLSX.

Deduplication key: URL.
The workbook is append-only at the row level: existing URLs are preserved
unchanged, and only new URLs from the fresh scrape are appended.
Uses only Python standard library modules.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List
from xml.etree import ElementTree as ET


COLUMNS = [
    "provider",
    "company",
    "title",
    "url",
    "description",
    "apply url",
    "location",
    "country",
    "status",
    "comment",
    "date of job posting",
    "first seen",
    "last seen",
]

ALIASES = {
    "applyUrl": "apply url",
    "apply_url": "apply url",
    "postingDate": "date of job posting",
    "posting_date": "date of job posting",
}


def normalize_row(row: dict, today: str) -> dict:
    normalized = {col: "" for col in COLUMNS}
    for key, value in row.items():
        target = ALIASES.get(key, key)
        if target in normalized:
            normalized[target] = "" if value is None else str(value)
    normalized["provider"] = normalized["provider"] or "jobleads"
    normalized["first seen"] = normalized["first seen"] or today
    normalized["last seen"] = today
    return normalized


def col_to_index(cell_ref: str) -> int:
    letters = re.match(r"([A-Z]+)", cell_ref).group(1)
    idx = 0
    for char in letters:
        idx = idx * 26 + (ord(char) - ord("A") + 1)
    return idx - 1


def read_xlsx(path: Path) -> List[dict]:
    if not path.exists():
        return []

    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as zf:
        shared_strings: List[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall("a:si", ns):
                texts = [t.text or "" for t in si.findall(".//a:t", ns)]
                shared_strings.append("".join(texts))

        sheet_name = "xl/worksheets/sheet1.xml"
        root = ET.fromstring(zf.read(sheet_name))
        rows = []
        for row in root.findall(".//a:sheetData/a:row", ns):
            values: Dict[int, str] = {}
            for cell in row.findall("a:c", ns):
                ref = cell.attrib.get("r", "A1")
                idx = col_to_index(ref)
                cell_type = cell.attrib.get("t")
                value_node = cell.find("a:v", ns)
                inline_node = cell.find("a:is/a:t", ns)
                if cell_type == "s" and value_node is not None:
                    value = shared_strings[int(value_node.text or "0")]
                elif inline_node is not None:
                    value = inline_node.text or ""
                elif value_node is not None:
                    value = value_node.text or ""
                else:
                    value = ""
                values[idx] = value
            if values:
                max_idx = max(values)
                rows.append([values.get(i, "") for i in range(max_idx + 1)])

    if not rows:
        return []
    headers = [h.strip() for h in rows[0]]
    return [
        {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
        for row in rows[1:]
        if any(cell for cell in row)
    ]


def xml_text(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def cell_ref(row: int, col: int) -> str:
    letters = ""
    col += 1
    while col:
        col, rem = divmod(col - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return f"{letters}{row}"


def write_xlsx(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [COLUMNS] + [[row.get(col, "") for col in COLUMNS] for row in rows]

    sheet_rows = []
    for r_idx, row in enumerate(data, start=1):
        cells = []
        for c_idx, value in enumerate(row):
            ref = cell_ref(r_idx, c_idx)
            value = xml_text(str(value))
            cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>')
        sheet_rows.append(f'<row r="{r_idx}">{"".join(cells)}</row>')

    sheet_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
 <sheetData>{"".join(sheet_rows)}</sheetData>
</worksheet>'''
    workbook_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
 <sheets><sheet name="Jobs" sheetId="1" r:id="rId1"/></sheets>
</workbook>'''
    rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''
    workbook_rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>'''
    content_types_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="xml" ContentType="application/xml"/>
 <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
 <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>'''

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def merge(existing: Iterable[dict], fresh: Iterable[dict], today: str) -> List[dict]:
    by_url: Dict[str, dict] = {}
    order: List[str] = []

    for row in existing:
        normalized = {col: str(row.get(col, "") or "") for col in COLUMNS}
        normalized["provider"] = normalized["provider"] or "jobleads"
        url = normalized.get("url", "").strip()
        if not url:
            continue
        by_url[url] = normalized
        order.append(url)

    for row in fresh:
        normalized = normalize_row(row, today)
        url = normalized.get("url", "").strip()
        if not url or url in by_url:
            continue
        by_url[url] = normalized
        order.append(url)

    return [by_url[url] for url in order if url in by_url]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fresh-json", required=True, type=Path)
    parser.add_argument("--xlsx", required=True, type=Path)
    parser.add_argument("--state-json", type=Path)
    parser.add_argument("--today", default=dt.date.today().isoformat())
    args = parser.parse_args()

    fresh = json.loads(args.fresh_json.read_text())
    if not isinstance(fresh, list):
        print("--fresh-json must contain a JSON array", file=sys.stderr)
        return 2

    existing = read_xlsx(args.xlsx)
    if not existing and args.state_json and args.state_json.exists():
        existing = json.loads(args.state_json.read_text())

    existing_urls = {str(row.get("url", "")).strip() for row in existing if row.get("url")}
    fresh_urls = {str(row.get("url", "")).strip() for row in fresh if row.get("url")}
    merged = merge(existing, fresh, args.today)
    write_xlsx(args.xlsx, merged)

    if args.state_json:
        args.state_json.parent.mkdir(parents=True, exist_ok=True)
        args.state_json.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n")

    print(
        json.dumps(
            {
                "total": len(merged),
                "fresh_unique_urls": len(fresh_urls),
                "appended": len(fresh_urls - existing_urls),
                "skipped_existing": len(fresh_urls & existing_urls),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
