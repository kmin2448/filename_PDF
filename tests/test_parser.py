"""reportlab으로 청구서 양식과 비슷한 PDF를 만들어 파서를 검증한다.

reportlab이 설치되어 있지 않으면 건너뛴다 (실행 파일에는 필요 없는 테스트 전용 의존성).
"""
import tempfile
import unittest
from pathlib import Path

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfgen import canvas
    HAS_REPORTLAB = True
except ImportError:  # pragma: no cover
    HAS_REPORTLAB = False

from src.core.parser import parse_invoice
from src.core.renamer import build_filename

FONT = "HYSMyeongJo-Medium"


def _grid(c, x, y, col_widths, row_h, rows, font_size=9):
    """간단한 표 그리기 (선 + 텍스트) → pdfplumber가 표로 인식한다."""
    total_w = sum(col_widths)
    n_rows = len(rows)
    for i in range(n_rows + 1):
        c.line(x, y - i * row_h, x + total_w, y - i * row_h)
    cx = x
    for w in col_widths + [0]:
        c.line(cx, y, cx, y - n_rows * row_h)
        cx += w
    c.setFont(FONT, font_size)
    for ri, row in enumerate(rows):
        cx = x
        for ci, text in enumerate(row):
            c.drawString(cx + 4, y - (ri + 1) * row_h + 5, text)
            cx += col_widths[ci]


def make_sample_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    pdfmetrics.registerFont(UnicodeCIDFont(FONT))
    width, height = A4

    # ---- 1페이지: 지출요구 및 결의서 ----
    c.setFont(FONT, 14)
    c.drawString(200, height - 60, "지출요구 및 결의서")
    _grid(c, 50, height - 100, [80, 200, 80, 135], 22, [
        ["이체일자", "2026-03-06", "결의번호", "2026-000123"],
        ["적요", "실험 소모품 구입", "지급방법", "계좌이체"],
    ])
    _grid(c, 50, height - 200, [150, 90, 90, 90, 75], 22, [
        ["비목", "예산액", "기집행액", "금회청구액", "잔액"],
        ["인건비", "10,000,000", "2,000,000", "", "8,000,000"],
        ["실험실습장비및기자재구입운영비", "5,000,000", "1,000,000", "1,234,000", "2,766,000"],
        ["장학금", "3,000,000", "0", "", "3,000,000"],
    ])
    c.showPage()

    # ---- 2페이지 ----
    c.setFont(FONT, 12)
    c.drawString(100, height - 100, "첨부 서류")
    c.showPage()

    # ---- 3페이지: 지급명세서 ----
    c.setFont(FONT, 14)
    c.drawString(220, height - 60, "지급명세서")
    _grid(c, 50, height - 100, [40, 150, 120, 120, 65], 22, [
        ["번호", "거래처명(성명)", "은행", "계좌번호", "금액"],
        ["1", "(주)과학상사", "국민은행", "000-00-0000", "1,234,000"],
    ])
    c.showPage()
    c.save()


@unittest.skipUnless(HAS_REPORTLAB, "reportlab이 설치되어 있지 않습니다")
class ParserTests(unittest.TestCase):
    def test_parse_sample_invoice(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "sample.pdf"
            make_sample_pdf(pdf)
            data = parse_invoice(pdf)

        self.assertEqual(data.transfer_date, "260306")
        self.assertEqual(data.summary, "실험 소모품 구입")
        self.assertEqual(data.category, "실험실습장비및기자재구입운영비")
        self.assertEqual(data.amount, "1,234,000")
        self.assertEqual(data.vendor, "(주)과학상사")
        self.assertTrue(data.is_complete)
        self.assertEqual(build_filename(data), "(260306) 실험 소모품 구입_(주)과학상사_(1,234,000).pdf")


if __name__ == "__main__":
    unittest.main()
