#!/usr/bin/env python3
"""Apply researched job assessments to jobs_all.xlsx by URL.

Only assessment columns are written. User-maintained workflow columns such as
status, comment, and current interview status are never modified.
Uses only Python standard library modules.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List
from xml.etree import ElementTree as ET
import re


NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
ET.register_namespace("", NS)
ET.register_namespace("r", "http://schemas.openxmlformats.org/officeDocument/2006/relationships")

PROTECTED_COLUMNS = {
    "status",
    "comment",
    "current interview status",
}

ASSESSMENT_COLUMNS = [
    "assessment date",
    "assessment status",
    "legitimacy check",
    "hiring entity type",
    "hiring entity mismatch",
    "founded year",
    "hq location",
    "remote policy",
    "linkedin employee count",
    "headcount trend",
    "funding summary",
    "funding stage",
    "company risk news",
    "glassdoor summary",
    "red flag scan",
    "seniority fit",
    "tech stack fit",
    "ic or management",
    "salary assessment",
    "remote eligibility",
    "visa contract structure",
    "ai native assessment",
    "one line summary",
    "apply verdict",
    "relevance score",
    "company trustworthiness score",
    "assessment research notes",
    "assessment source urls",
]


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


def read_shared_strings(zf: zipfile.ZipFile) -> List[str]:
    shared_strings: List[str] = []
    if "xl/sharedStrings.xml" not in zf.namelist():
        return shared_strings
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    for si in root.findall(qname("si")):
        shared_strings.append("".join(t.text or "" for t in si.findall(f".//{qname('t')}")))
    return shared_strings


def cell_text(cell: ET.Element, shared_strings: List[str]) -> str:
    value_node = cell.find(qname("v"))
    inline_node = cell.find(f"{qname('is')}/{qname('t')}")
    if cell.attrib.get("t") == "s" and value_node is not None:
        return shared_strings[int(value_node.text or "0")]
    if inline_node is not None:
        return inline_node.text or ""
    if value_node is not None:
        return value_node.text or ""
    return ""


def inline_cell(row_idx: int, col_idx: int, value: str) -> ET.Element:
    cell = ET.Element(qname("c"), {"r": cell_ref(row_idx, col_idx), "t": "inlineStr"})
    is_node = ET.SubElement(cell, qname("is"))
    text = ET.SubElement(is_node, qname("t"))
    text.text = "" if value is None else str(value)
    return cell


def set_cell_value(row_node: ET.Element, row_idx: int, col_idx: int, value: str) -> None:
    target_ref = cell_ref(row_idx, col_idx)
    for cell in row_node.findall(qname("c")):
        if cell.attrib.get("r") == target_ref:
            cell.clear()
            cell.attrib.update({"r": target_ref, "t": "inlineStr"})
            is_node = ET.SubElement(cell, qname("is"))
            text = ET.SubElement(is_node, qname("t"))
            text.text = "" if value is None else str(value)
            return
    row_node.append(inline_cell(row_idx, col_idx, value))


def sheet_headers(sheet: ET.Element, shared_strings: List[str]) -> List[str]:
    header_row = sheet.find(f".//{qname('sheetData')}/{qname('row')}")
    if header_row is None:
        return []
    values: Dict[int, str] = {}
    max_col = -1
    for cell in header_row.findall(qname("c")):
        idx = col_to_index(cell.attrib.get("r", "A1"))
        max_col = max(max_col, idx)
        values[idx] = cell_text(cell, shared_strings).strip()
    return [values.get(i, "") for i in range(max_col + 1)]


def normalize_assessment(item: dict, today: str) -> dict:
    if "url" not in item:
        raise ValueError("Each assessment must include url")
    normalized = {col: "" for col in ASSESSMENT_COLUMNS}
    for key, value in item.items():
        if key in PROTECTED_COLUMNS:
            continue
        if key in normalized:
            normalized[key] = "" if value is None else str(value)
    normalized["assessment date"] = normalized["assessment date"] or today
    normalized["assessment status"] = normalized["assessment status"] or "researched"
    return normalized


def apply_assessments(path: Path, assessments_path: Path, today: str, backup: bool) -> dict:
    assessments_raw = json.loads(assessments_path.read_text())
    if not isinstance(assessments_raw, list):
        raise ValueError("--assessments-json must contain a JSON array")

    by_url = {
        str(item.get("url", "")).strip(): normalize_assessment(item, today)
        for item in assessments_raw
        if str(item.get("url", "")).strip()
    }

    if not path.exists():
        raise FileNotFoundError(path)

    if backup:
        backup_path = path.with_suffix(f".backup-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx")
        shutil.copy2(path, backup_path)

    with zipfile.ZipFile(path) as zin:
        shared_strings = read_shared_strings(zin)
        sheet = ET.fromstring(zin.read("xl/worksheets/sheet1.xml"))

    sheet_data = sheet.find(qname("sheetData"))
    if sheet_data is None:
        raise ValueError("Workbook has no sheetData")

    headers = sheet_headers(sheet, shared_strings)
    if "url" not in headers:
        raise ValueError("Workbook must contain a url column")

    header_row = sheet_data.find(qname("row"))
    if header_row is None:
        raise ValueError("Workbook must contain a header row")

    for col in ASSESSMENT_COLUMNS:
        if col not in headers:
            headers.append(col)
            set_cell_value(header_row, 1, len(headers) - 1, col)

    header_index = {header: idx for idx, header in enumerate(headers)}
    url_idx = header_index["url"]
    updated = 0
    skipped_missing_url = 0

    for row_node in sheet_data.findall(qname("row"))[1:]:
        row_idx = int(row_node.attrib.get("r", "1"))
        values: Dict[int, str] = {}
        for cell in row_node.findall(qname("c")):
            values[col_to_index(cell.attrib.get("r", "A1"))] = cell_text(cell, shared_strings)
        url = values.get(url_idx, "").strip()
        if not url:
            skipped_missing_url += 1
            continue
        assessment = by_url.get(url)
        if not assessment:
            continue
        for key, value in assessment.items():
            if key in PROTECTED_COLUMNS:
                continue
            set_cell_value(row_node, row_idx, header_index[key], value)
        updated += 1

    dimension = sheet.find(qname("dimension"))
    row_nodes = sheet_data.findall(qname("row"))
    if dimension is not None and row_nodes:
        max_row = max(int(row.attrib.get("r", "1")) for row in row_nodes)
        dimension.set("ref", f"A1:{cell_ref(max_row, len(headers) - 1)}")

    sheet_xml = ET.tostring(sheet, encoding="utf-8", xml_declaration=True)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp_path = Path(tmp.name)

    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(
        tmp_path, "w", compression=zipfile.ZIP_DEFLATED
    ) as zout:
        for item in zin.infolist():
            if item.filename == "xl/worksheets/sheet1.xml":
                zout.writestr(item, sheet_xml)
            else:
                zout.writestr(item, zin.read(item.filename))

    shutil.move(str(tmp_path), path)
    return {
        "workbook": str(path),
        "assessment_items": len(by_url),
        "updated_rows": updated,
        "skipped_missing_url_rows": skipped_missing_url,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xlsx", type=Path, default=Path("jobs_all.xlsx"))
    parser.add_argument("--assessments-json", type=Path, required=True)
    parser.add_argument("--today", default=dt.date.today().isoformat())
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()

    result = apply_assessments(
        args.xlsx, args.assessments_json, args.today, backup=not args.no_backup
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
