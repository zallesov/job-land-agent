#!/usr/bin/env python3
"""Append provider jobs into jobs_all.xlsx without overwriting existing rows.

Deduplication key: URL.
Existing rows are preserved. New provider rows whose URL is not already present
are appended. Existing status/comment/current-interview columns are never
overwritten.

Uses only Python standard library modules.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List
from xml.etree import ElementTree as ET


NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
ET.register_namespace("", NS)
ET.register_namespace("r", "http://schemas.openxmlformats.org/officeDocument/2006/relationships")

STANDARD_COLUMNS = [
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
    "current interview status",
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


def qname(name: str) -> str:
    return f"{{{NS}}}{name}"


def col_to_index(cell_ref: str) -> int:
    match = re.match(r"([A-Z]+)", cell_ref)
    if not match:
        return 0
    idx = 0
    for char in match.group(1):
        idx = idx * 26 + (ord(char) - ord("A") + 1)
    return idx - 1


def cell_ref(row: int, col: int) -> str:
    letters = ""
    col += 1
    while col:
        col, rem = divmod(col - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return f"{letters}{row}"


def read_xlsx(path: Path) -> List[dict]:
    if not path.exists():
        return []

    with zipfile.ZipFile(path) as zf:
        shared_strings: List[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall(f"{qname('si')}"):
                texts = [t.text or "" for t in si.findall(f".//{qname('t')}")]
                shared_strings.append("".join(texts))

        root = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
        rows = []
        for row in root.findall(f".//{qname('sheetData')}/{qname('row')}"):
            values: Dict[int, str] = {}
            for cell in row.findall(qname("c")):
                idx = col_to_index(cell.attrib.get("r", "A1"))
                cell_type = cell.attrib.get("t")
                value_node = cell.find(qname("v"))
                inline_node = cell.find(f"{qname('is')}/{qname('t')}")
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
                rows.append([values.get(i, "") for i in range(max(values) + 1)])

    if not rows:
        return []
    headers = [header.strip() for header in rows[0]]
    return [
        {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
        for row in rows[1:]
        if any(cell for cell in row)
    ]


def read_headers(path: Path) -> List[str]:
    if not path.exists():
        return []
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
        first_row = root.find(f".//{qname('sheetData')}/{qname('row')}")
        if first_row is None:
            return []
    rows = read_xlsx(path)
    if rows:
        with zipfile.ZipFile(path) as zf:
            sheet = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
            header_row = sheet.find(f".//{qname('sheetData')}/{qname('row')}")
            if header_row is not None:
                max_col = -1
                values: Dict[int, str] = {}
                shared_strings = []
                if "xl/sharedStrings.xml" in zf.namelist():
                    ss_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
                    for si in ss_root.findall(qname("si")):
                        shared_strings.append("".join(t.text or "" for t in si.findall(f".//{qname('t')}")))
                for cell in header_row.findall(qname("c")):
                    idx = col_to_index(cell.attrib.get("r", "A1"))
                    max_col = max(max_col, idx)
                    value_node = cell.find(qname("v"))
                    inline_node = cell.find(f"{qname('is')}/{qname('t')}")
                    if cell.attrib.get("t") == "s" and value_node is not None:
                        values[idx] = shared_strings[int(value_node.text or "0")]
                    elif inline_node is not None:
                        values[idx] = inline_node.text or ""
                    elif value_node is not None:
                        values[idx] = value_node.text or ""
                    else:
                        values[idx] = ""
                return [values.get(i, "").strip() for i in range(max_col + 1)]
    return []


def normalize_row(row: dict, today: str) -> dict:
    normalized = {col: "" for col in STANDARD_COLUMNS}
    for key, value in row.items():
        target = ALIASES.get(key, key)
        if target in normalized:
            normalized[target] = "" if value is None else str(value)
    normalized["first seen"] = normalized["first seen"] or today
    normalized["last seen"] = normalized["last seen"] or today
    return normalized


def provider_rows(provider_paths: Iterable[Path], today: str) -> List[dict]:
    rows = []
    seen = set()
    for provider_path in provider_paths:
        for row in read_xlsx(provider_path):
            normalized = normalize_row(row, today)
            url = normalized.get("url", "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            rows.append(normalized)
    return rows


def inline_cell(row_idx: int, col_idx: int, value: str) -> ET.Element:
    cell = ET.Element(qname("c"), {"r": cell_ref(row_idx, col_idx), "t": "inlineStr"})
    is_node = ET.SubElement(cell, qname("is"))
    text = ET.SubElement(is_node, qname("t"))
    text.text = "" if value is None else str(value)
    return cell


def write_minimal_xlsx(path: Path, headers: List[str], rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet_rows = []
    all_rows = [headers] + [[row.get(header, "") for header in headers] for row in rows]
    for r_idx, row in enumerate(all_rows, start=1):
        row_node = ET.Element(qname("row"), {"r": str(r_idx)})
        for c_idx, value in enumerate(row):
            row_node.append(inline_cell(r_idx, c_idx, value))
        sheet_rows.append(ET.tostring(row_node, encoding="unicode"))

    sheet_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="{NS}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
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


def edit_existing_xlsx(path: Path, headers: List[str], new_rows: List[dict]) -> None:
    with zipfile.ZipFile(path) as zin:
        sheet = ET.fromstring(zin.read("xl/worksheets/sheet1.xml"))
        sheet_data = sheet.find(qname("sheetData"))
        if sheet_data is None:
            sheet_data = ET.SubElement(sheet, qname("sheetData"))

        row_nodes = sheet_data.findall(qname("row"))
        if not row_nodes:
            header_node = ET.SubElement(sheet_data, qname("row"), {"r": "1"})
            row_nodes = [header_node]
        else:
            header_node = row_nodes[0]

        existing_header_count = len(read_headers(path))
        for col_idx, header in enumerate(headers[existing_header_count:], start=existing_header_count):
            header_node.append(inline_cell(1, col_idx, header))

        max_row = 1
        for row_node in row_nodes:
            max_row = max(max_row, int(row_node.attrib.get("r", "1")))

        for offset, row in enumerate(new_rows, start=1):
            row_idx = max_row + offset
            row_node = ET.Element(qname("row"), {"r": str(row_idx)})
            for col_idx, header in enumerate(headers):
                row_node.append(inline_cell(row_idx, col_idx, row.get(header, "")))
            sheet_data.append(row_node)

        dimension = sheet.find(qname("dimension"))
        if dimension is not None:
            dimension.set("ref", f"A1:{cell_ref(max_row + len(new_rows), len(headers) - 1)}")

        sheet_xml = ET.tostring(sheet, encoding="utf-8", xml_declaration=True)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            tmp_path = Path(tmp.name)

        with zipfile.ZipFile(path) as zin2, zipfile.ZipFile(
            tmp_path, "w", compression=zipfile.ZIP_DEFLATED
        ) as zout:
            for item in zin2.infolist():
                if item.filename == "xl/worksheets/sheet1.xml":
                    zout.writestr(item, sheet_xml)
                else:
                    zout.writestr(item, zin2.read(item.filename))

    shutil.move(str(tmp_path), path)


def consolidate(provider_paths: List[Path], output: Path, today: str, backup: bool) -> dict:
    existing_rows = read_xlsx(output)
    existing_urls = {str(row.get("url", "")).strip() for row in existing_rows if row.get("url")}
    incoming_rows = provider_rows(provider_paths, today)
    new_rows = [row for row in incoming_rows if row.get("url", "").strip() not in existing_urls]

    existing_headers = read_headers(output)
    headers = existing_headers[:] if existing_headers else STANDARD_COLUMNS[:]
    for header in STANDARD_COLUMNS:
        if header not in headers:
            headers.append(header)

    if output.exists():
        if backup:
            backup_path = output.with_suffix(f".backup-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx")
            shutil.copy2(output, backup_path)
        edit_existing_xlsx(output, headers, new_rows)
    else:
        write_minimal_xlsx(output, headers, new_rows)

    final_rows = read_xlsx(output)
    return {
        "output": str(output),
        "providers": [str(path) for path in provider_paths],
        "existing_rows": len(existing_rows),
        "incoming_unique_urls": len({row.get("url", "") for row in incoming_rows if row.get("url")}),
        "appended": len(new_rows),
        "skipped_existing": len(incoming_rows) - len(new_rows),
        "final_rows": len(final_rows),
        "final_unique_urls": len({row.get("url", "") for row in final_rows if row.get("url")}),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--provider-xlsx",
        action="append",
        type=Path,
        default=[],
        help="Provider jobs workbook. Can be passed multiple times.",
    )
    parser.add_argument("--output", type=Path, default=Path("jobs_all.xlsx"))
    parser.add_argument("--today", default=dt.date.today().isoformat())
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()

    provider_paths = args.provider_xlsx or [
        Path("outputs/jobleads/jobs.xlsx"),
        Path("outputs/greenhouse/jobs.xlsx"),
    ]
    missing = [str(path) for path in provider_paths if not path.exists()]
    if missing:
        print(json.dumps({"error": "missing provider workbooks", "missing": missing}, indent=2), file=sys.stderr)
        return 2

    result = consolidate(provider_paths, args.output, args.today, backup=not args.no_backup)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
