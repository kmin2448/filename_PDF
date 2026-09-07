"""파일명 조합, 출력 폴더 결정, 파일 복사."""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

from .categories import folder_name_for
from .parser import InvoiceData

OUTPUT_ROOT_NAME = "청구서정리"

_INVALID_NAME_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]')


def sanitize_part(text: str | None) -> str:
    """파일명 구성 요소에서 Windows 금지 문자를 제거한다."""
    cleaned = _INVALID_NAME_CHARS.sub(" ", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def build_filename(data: InvoiceData) -> str:
    """'(YYMMDD) 적요_거래처명(성명)_(금회청구액).pdf' 형식 파일명을 만든다.

    누락 항목은 빈 문자열로 두어 사용자가 수동으로 채울 수 있게 한다.
    """
    date = sanitize_part(data.transfer_date)
    summary = sanitize_part(data.summary)
    vendor = sanitize_part(data.vendor)
    amount = sanitize_part(data.amount)
    return f"({date}) {summary}_{vendor}_({amount}).pdf"


def is_valid_filename(name: str) -> bool:
    name = (name or "").strip()
    if not name or not name.lower().endswith(".pdf"):
        return False
    if _INVALID_NAME_CHARS.search(name):
        return False
    stem = name[:-4]
    # '() __()' 처럼 값이 하나도 채워지지 않은 템플릿은 무효
    return re.search(r"[0-9A-Za-z가-힣]", stem) is not None


def get_desktop_dir() -> Path:
    """OS별 바탕화면 경로 (Windows는 OneDrive/한글 경로도 정확히 인식)."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", wintypes.DWORD),
                    ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD),
                    ("Data4", wintypes.BYTE * 8),
                ]

            # FOLDERID_Desktop = {B4BFCC3A-DB2C-424C-B029-7FE99A87C641}
            desktop_id = GUID(
                0xB4BFCC3A, 0xDB2C, 0x424C,
                (wintypes.BYTE * 8)(0xB0, 0x29, 0x7F, 0xE9, 0x9A, 0x87, 0xC6, 0x41),
            )
            path_ptr = ctypes.c_wchar_p()
            shell32 = ctypes.windll.shell32
            if shell32.SHGetKnownFolderPath(ctypes.byref(desktop_id), 0, None, ctypes.byref(path_ptr)) == 0:
                path = Path(path_ptr.value)
                ctypes.windll.ole32.CoTaskMemFree(path_ptr)
                if path.exists():
                    return path
        except Exception:
            pass
    home = Path.home()
    for candidate in ("Desktop", "바탕 화면", "바탕화면"):
        p = home / candidate
        if p.exists():
            return p
    return home / "Desktop"


def get_output_root() -> Path:
    return get_desktop_dir() / OUTPUT_ROOT_NAME


def resolve_target_dir(category: str | None, output_root: Path | None = None) -> Path:
    """비목에 해당하는 출력 폴더 경로. 예) 바탕화면/청구서정리/01. 인건비"""
    root = output_root or get_output_root()
    return root / folder_name_for(category)


def unique_path(directory: Path, filename: str) -> Path:
    """같은 이름의 파일이 있으면 ' (2)', ' (3)'... 을 붙여 덮어쓰기를 방지한다."""
    target = directory / filename
    if not target.exists():
        return target
    stem, suffix = os.path.splitext(filename)
    n = 2
    while True:
        candidate = directory / f"{stem} ({n}){suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def save_copy(src: str | Path, category: str | None, filename: str, output_root: Path | None = None) -> Path:
    """원본은 그대로 두고 비목 폴더에 새 파일명으로 복사한다. 저장된 경로를 반환."""
    if not is_valid_filename(filename):
        raise ValueError(f"올바르지 않은 파일명입니다: {filename!r}")
    target_dir = resolve_target_dir(category, output_root)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = unique_path(target_dir, filename.strip())
    shutil.copy2(str(src), str(target))
    return target
