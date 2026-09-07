"""청구서 PDF에서 파일명 생성에 필요한 정보를 추출한다.

- 1페이지 (지출요구 및 결의서): 이체일자, 적요, 비목, 금회청구액
- 3페이지 (지급명세서): 거래처명(성명)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import pdfplumber

from .categories import category_names, normalize

Table = Sequence[Sequence[str | None]]

_DATE_RE = re.compile(r"(\d{4})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})")
_AMOUNT_RE = re.compile(r"\d{1,3}(?:,\d{3})+|\d{4,}")

LABEL_DATE = "이체일자"
LABEL_SUMMARY = "적요"
LABEL_CATEGORY = "비목"
LABEL_AMOUNT = "금회청구액"
LABEL_VENDOR = "거래처명"


class ParseError(Exception):
    """필수 정보를 추출하지 못했을 때 발생."""


@dataclass
class InvoiceData:
    transfer_date: str | None = None  # YYMMDD
    summary: str | None = None        # 적요
    category: str | None = None       # 비목
    amount: str | None = None         # 금회청구액 (예: "1,234,000")
    vendor: str | None = None         # 거래처명(성명)

    FIELD_LABELS = {
        "transfer_date": "이체일자",
        "summary": "적요",
        "category": "비목",
        "amount": "금회청구액",
        "vendor": "거래처명(성명)",
    }

    def missing_fields(self) -> list[str]:
        return [label for attr, label in self.FIELD_LABELS.items() if not getattr(self, attr)]

    @property
    def is_complete(self) -> bool:
        return not self.missing_fields()


# ---------------------------------------------------------------------------
# 공통 헬퍼
# ---------------------------------------------------------------------------
def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _to_yymmdd(text: str | None) -> str | None:
    if not text:
        return None
    m = _DATE_RE.search(text)
    if not m:
        return None
    year, month, day = m.groups()
    return f"{year[2:]}{int(month):02d}{int(day):02d}"


def format_amount(value: int | str | None) -> str | None:
    """숫자/문자열 금액을 '1,234,000' 형식으로 통일한다."""
    if value is None:
        return None
    digits = re.sub(r"[^\d]", "", str(value))
    if not digits:
        return None
    return f"{int(digits):,}"


def _parse_amount(cell: str | None) -> int | None:
    if not cell:
        return None
    text = _clean(cell)
    if not re.search(r"\d", text):
        return None
    # "1,234,000원" / "1234000" 등 → 숫자만
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return None
    return int(digits)


def _cell_has_label(cell: str | None, label: str) -> bool:
    return normalize(label) in normalize(cell)


def _strip_label(cell: str, label: str) -> str:
    """'적요 : 물품구입' 같은 셀에서 라벨 부분을 떼어내 값만 남긴다."""
    text = _clean(cell)
    m = re.match(rf"^\s*{re.escape(label)}\s*[:：]?\s*(.*)$", text)
    if m:
        return m.group(1).strip()
    return ""


def _find_label_value(tables: Iterable[Table], label: str) -> str | None:
    """표 안에서 라벨 셀을 찾아 오른쪽(없으면 아래) 셀 값을 돌려준다."""
    for table in tables:
        rows = [list(r) for r in table if r]
        for ri, row in enumerate(rows):
            for ci, cell in enumerate(row):
                if not cell or not _cell_has_label(cell, label):
                    continue
                # 라벨 셀이 이미 '라벨 : 값' 형태인 경우
                inline = _strip_label(cell, label)
                if inline:
                    return inline
                # 오른쪽 셀
                for right in row[ci + 1:]:
                    if right and _clean(right) and not _cell_has_label(right, label):
                        return _clean(right)
                # 아래 셀
                if ri + 1 < len(rows) and ci < len(rows[ri + 1]):
                    below = rows[ri + 1][ci]
                    if below and _clean(below):
                        return _clean(below)
    return None


def _find_in_text(text: str, label: str) -> str | None:
    """텍스트에서 '라벨 : 값' 형태를 찾는다 (같은 줄 우선, 없으면 다음 줄)."""
    lines = [l for l in text.splitlines()]
    for i, line in enumerate(lines):
        if normalize(label) not in normalize(line):
            continue
        m = re.search(rf"{re.escape(label)}\s*[:：]?\s*(.+)$", line)
        if m and _clean(m.group(1)):
            return _clean(m.group(1))
        if i + 1 < len(lines) and _clean(lines[i + 1]):
            return _clean(lines[i + 1])
    return None


# ---------------------------------------------------------------------------
# 1페이지: 예산 표 (비목 / 금회청구액)
# ---------------------------------------------------------------------------
def _extract_budget_row(tables: Iterable[Table]) -> tuple[str | None, int | None]:
    """'비목'과 '금회청구액' 컬럼이 있는 표에서 청구액이 존재하는 행을 찾는다."""
    for table in tables:
        rows = [list(r) for r in table if r]
        for hi, row in enumerate(rows):
            amount_col = next(
                (ci for ci, c in enumerate(row) if c and _cell_has_label(c, LABEL_AMOUNT)), None
            )
            if amount_col is None:
                continue
            # 비목 컬럼은 같은 헤더 행 또는 바로 위 행(다단 헤더)에서 찾는다.
            cat_col = None
            for hr in (row, rows[hi - 1] if hi > 0 else []):
                cat_col = next(
                    (ci for ci, c in enumerate(hr) if c and _cell_has_label(c, LABEL_CATEGORY)),
                    None,
                )
                if cat_col is not None:
                    break
            if cat_col is None:
                continue

            last_category = None
            for body in rows[hi + 1:]:
                if cat_col < len(body) and body[cat_col] and _clean(body[cat_col]):
                    last_category = _clean(body[cat_col])
                if amount_col >= len(body):
                    continue
                amount = _parse_amount(body[amount_col])
                if amount and last_category:
                    return last_category, amount
    return None, None


def _extract_budget_from_text(text: str) -> tuple[str | None, int | None]:
    """표 인식에 실패했을 때: 등록된 비목명이 들어 있고 금액이 하나뿐인 줄을 찾는다."""
    names = sorted(category_names(), key=len, reverse=True)
    for line in text.splitlines():
        norm_line = normalize(line)
        for name in names:
            if normalize(name) in norm_line:
                amounts = [int(a.replace(",", "")) for a in _AMOUNT_RE.findall(line)]
                amounts = [a for a in amounts if a > 0]
                if len(amounts) == 1:
                    return name, amounts[0]
                return name, None
    return None, None


# ---------------------------------------------------------------------------
# 3페이지: 지급명세서 (거래처명(성명))
# ---------------------------------------------------------------------------
def _extract_vendor(tables: Iterable[Table]) -> str | None:
    for table in tables:
        rows = [list(r) for r in table if r]
        for hi, row in enumerate(rows):
            for ci, cell in enumerate(row):
                if not cell or not _cell_has_label(cell, LABEL_VENDOR):
                    continue
                inline = _strip_label(cell, "거래처명(성명)") or _strip_label(cell, LABEL_VENDOR)
                if inline and inline not in ("(성명)", "성명"):
                    return inline
                for body in rows[hi + 1:]:
                    if ci < len(body) and body[ci] and _clean(body[ci]):
                        return _clean(body[ci])
    return None


def _extract_vendor_from_text(text: str) -> str | None:
    m = re.search(r"거래처명\s*\(?\s*성명\s*\)?\s*[:：]?\s*([^\s:：]+)", text)
    if m:
        return _clean(m.group(1))
    return None


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------
def _page_tables(page) -> list[Table]:
    try:
        return page.extract_tables() or []
    except Exception:
        return []


def parse_invoice(pdf_path: str | Path) -> InvoiceData:
    """PDF에서 InvoiceData를 추출한다. 누락 항목은 None으로 남긴다."""
    data = InvoiceData()
    with pdfplumber.open(str(pdf_path)) as pdf:
        if not pdf.pages:
            raise ParseError("페이지가 없는 PDF입니다.")

        # ---- 1페이지 ----
        first = pdf.pages[0]
        tables = _page_tables(first)
        text = first.extract_text() or ""

        date_raw = _find_label_value(tables, LABEL_DATE) or _find_in_text(text, LABEL_DATE)
        data.transfer_date = _to_yymmdd(date_raw)
        if not data.transfer_date:
            data.transfer_date = _to_yymmdd(text)

        data.summary = _find_label_value(tables, LABEL_SUMMARY) or _find_in_text(text, LABEL_SUMMARY)

        category, amount = _extract_budget_row(tables)
        if not category or amount is None:
            t_category, t_amount = _extract_budget_from_text(text)
            category = category or t_category
            amount = amount if amount is not None else t_amount
        data.category = category
        data.amount = format_amount(amount)

        # ---- 3페이지 (없으면 나머지 페이지에서 탐색) ----
        candidate_pages = []
        if len(pdf.pages) >= 3:
            candidate_pages.append(pdf.pages[2])
        candidate_pages += [p for p in pdf.pages if p not in candidate_pages]
        for page in candidate_pages:
            vendor = _extract_vendor(_page_tables(page))
            if not vendor:
                vendor = _extract_vendor_from_text(page.extract_text() or "")
            if vendor:
                data.vendor = vendor
                break

    return data
