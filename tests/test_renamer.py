import tempfile
import unittest
from pathlib import Path

from src.core.parser import InvoiceData, format_amount
from src.core.renamer import build_filename, is_valid_filename, resolve_target_dir, save_copy, unique_path


class BuildFilenameTests(unittest.TestCase):
    def test_full_data(self):
        data = InvoiceData(transfer_date="260306", summary="사무용품 구입", category="인건비",
                           amount="1,234,000", vendor="홍길동")
        self.assertEqual(build_filename(data), "(260306) 사무용품 구입_홍길동_(1,234,000).pdf")

    def test_missing_fields_left_blank_for_manual_edit(self):
        data = InvoiceData(transfer_date="260306", summary="사무용품 구입")
        self.assertEqual(build_filename(data), "(260306) 사무용품 구입__().pdf")
        self.assertEqual(data.missing_fields(), ["비목", "금회청구액", "거래처명(성명)"])

    def test_invalid_characters_are_removed(self):
        data = InvoiceData(transfer_date="260306", summary="A/B:C", category="인건비",
                           amount="1,000", vendor="주식회사 <가나>")
        self.assertEqual(build_filename(data), "(260306) A B C_주식회사 가나_(1,000).pdf")

    def test_format_amount(self):
        self.assertEqual(format_amount("1234000"), "1,234,000")
        self.assertEqual(format_amount("1,234,000원"), "1,234,000")
        self.assertEqual(format_amount(500), "500")
        self.assertIsNone(format_amount("원"))
        self.assertIsNone(format_amount(None))

    def test_is_valid_filename(self):
        self.assertTrue(is_valid_filename("(260306) 적요_홍길동_(1,000).pdf"))
        self.assertFalse(is_valid_filename("() __().pdf"))
        self.assertFalse(is_valid_filename("no-extension"))
        self.assertFalse(is_valid_filename("bad:name.pdf"))
        self.assertFalse(is_valid_filename(""))


class SaveCopyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "청구서정리"
        self.src = Path(self._tmp.name) / "원본.pdf"
        self.src.write_bytes(b"%PDF-1.4 dummy")

    def tearDown(self):
        self._tmp.cleanup()

    def test_target_dir_uses_numbered_folder(self):
        self.assertEqual(resolve_target_dir("인건비", self.root), self.root / "01. 인건비")
        self.assertEqual(resolve_target_dir("장학금", self.root), self.root / "02. 장학금")

    def test_copy_keeps_original_and_creates_numbered_folder(self):
        saved = save_copy(self.src, "장학금", "(260306) 적요_홍길동_(1,000).pdf", self.root)
        self.assertEqual(saved, self.root / "02. 장학금" / "(260306) 적요_홍길동_(1,000).pdf")
        self.assertTrue(saved.exists())
        self.assertTrue(self.src.exists())
        self.assertEqual(saved.read_bytes(), self.src.read_bytes())

    def test_duplicate_names_do_not_overwrite(self):
        first = save_copy(self.src, "인건비", "a.pdf", self.root)
        second = save_copy(self.src, "인건비", "a.pdf", self.root)
        self.assertEqual(first.name, "a.pdf")
        self.assertEqual(second.name, "a (2).pdf")
        self.assertEqual(unique_path(first.parent, "a.pdf").name, "a (3).pdf")

    def test_invalid_filename_rejected(self):
        with self.assertRaises(ValueError):
            save_copy(self.src, "인건비", "() __().pdf", self.root)


if __name__ == "__main__":
    unittest.main()
