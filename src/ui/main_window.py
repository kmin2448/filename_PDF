"""PDF Auto-Renamer 메인 창 (다크 모드 전용)."""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.categories import folder_name_for, folder_names
from src.core.parser import InvoiceData, parse_invoice
from src.core.renamer import build_filename, get_output_root, is_valid_filename, save_copy

MAX_FILES = 50

STATUS_WAITING = "대기"
STATUS_DONE = "완료"
STATUS_ERROR = "에러"

COL_SOURCE, COL_TARGET, COL_CATEGORY, COL_STATUS, COL_OPEN = range(5)

DARK_STYLESHEET = """
QMainWindow, QWidget { background-color: #2b2b2b; color: #e6e6e6; }
QLabel { color: #e6e6e6; }
QLabel#hint { color: #a0a0a0; }
QLabel#dropArea {
    border: 2px dashed #5a5a5a; border-radius: 8px;
    padding: 28px; color: #bdbdbd; background-color: #333333;
}
QLabel#dropArea[active="true"] { border-color: #bdbdbd; background-color: #3a3a3a; }
QPushButton {
    background-color: #3d3d3d; color: #e6e6e6; border: 1px solid #555555;
    border-radius: 4px; padding: 6px 14px;
}
QPushButton:hover { background-color: #4a4a4a; }
QPushButton:pressed { background-color: #2f2f2f; }
QPushButton:disabled { color: #777777; border-color: #444444; }
QPushButton#primary { background-color: #5a5a5a; font-weight: bold; }
QPushButton#primary:hover { background-color: #6a6a6a; }
QTableWidget {
    background-color: #313131; alternate-background-color: #363636;
    gridline-color: #444444; border: 1px solid #444444; selection-background-color: #555555;
    selection-color: #ffffff;
}
QHeaderView::section {
    background-color: #3a3a3a; color: #e6e6e6; border: 1px solid #444444; padding: 4px;
}
QTableCornerButton::section { background-color: #3a3a3a; border: 1px solid #444444; }
QProgressBar {
    border: 1px solid #555555; border-radius: 4px; background-color: #333333;
    text-align: center; color: #e6e6e6;
}
QProgressBar::chunk { background-color: #8a8a8a; }
QLineEdit { background-color: #3d3d3d; color: #ffffff; border: 1px solid #666666; }
QMessageBox { background-color: #2b2b2b; }
QScrollBar:vertical { background: #2b2b2b; width: 12px; }
QScrollBar::handle:vertical { background: #555555; border-radius: 4px; min-height: 20px; }
"""


@dataclass
class Job:
    row: int
    source: Path
    manual_filename: str | None = None
    manual_category: str | None = None


@dataclass
class JobResult:
    row: int
    status: str
    filename: str
    category: str | None
    saved_path: Path | None = None
    message: str = ""


@dataclass
class RowState:
    source: Path
    status: str = STATUS_WAITING
    parsed: bool = False
    manual: bool = False
    saved_path: Path | None = None
    data: InvoiceData | None = None


class Worker(QObject):
    """백그라운드에서 파싱 및 복사를 수행한다."""

    progress = pyqtSignal(int, int)          # done, total
    result = pyqtSignal(object)              # JobResult
    finished = pyqtSignal()

    def __init__(self, jobs: list[Job], output_root: Path):
        super().__init__()
        self._jobs = jobs
        self._output_root = output_root

    def run(self) -> None:
        total = len(self._jobs)
        for i, job in enumerate(self._jobs, start=1):
            self.result.emit(self._process(job))
            self.progress.emit(i, total)
        self.finished.emit()

    def _process(self, job: Job) -> JobResult:
        filename = job.manual_filename
        category = job.manual_category
        try:
            if filename is None or category is None:
                data = parse_invoice(job.source)
                if filename is None:
                    filename = build_filename(data)
                if category is None:
                    category = data.category
                missing = data.missing_fields()
                if job.manual_filename is None and missing:
                    return JobResult(
                        job.row, STATUS_ERROR, filename, category,
                        message="추출 실패: " + ", ".join(missing) + " (파일명을 직접 수정한 뒤 다시 실행하세요)",
                    )
            if not is_valid_filename(filename):
                return JobResult(job.row, STATUS_ERROR, filename, category, message="파일명이 올바르지 않습니다.")
            if not (category or "").strip():
                return JobResult(job.row, STATUS_ERROR, filename, category, message="비목(저장 폴더)이 비어 있습니다.")
            saved = save_copy(job.source, category, filename, self._output_root)
            return JobResult(job.row, STATUS_DONE, saved.name, category, saved_path=saved,
                             message=f"{saved.parent.name} 폴더에 저장되었습니다.")
        except Exception as exc:  # noqa: BLE001 - UI에 그대로 보여준다
            return JobResult(job.row, STATUS_ERROR, filename or "", category, message=f"오류: {exc}")


class DropArea(QLabel):
    files_dropped = pyqtSignal(list)

    def __init__(self, parent: QWidget | None = None):
        super().__init__("PDF 파일을 이곳에 끌어다 놓거나 [파일 추가] 버튼을 누르세요", parent)
        self.setObjectName("dropArea")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAcceptDrops(True)
        self.setMinimumHeight(90)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            self.setProperty("active", "true")
            self.style().unpolish(self)
            self.style().polish(self)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self.setProperty("active", "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        self.setProperty("active", "false")
        self.style().unpolish(self)
        self.style().polish(self)
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        self.files_dropped.emit(paths)
        event.acceptProposedAction()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PDF Auto-Renamer")
        self.resize(1000, 620)
        self.setWindowOpacity(0.97)
        self.setStyleSheet(DARK_STYLESHEET)

        self._rows: list[RowState] = []
        self._thread: QThread | None = None
        self._worker: Worker | None = None
        self._updating = False

        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # 상단: 드래그 앤 드롭 + 파일 추가
        self.drop_area = DropArea()
        self.drop_area.files_dropped.connect(self.add_files)
        layout.addWidget(self.drop_area)

        top_buttons = QHBoxLayout()
        self.btn_add = QPushButton("파일 추가")
        self.btn_add.clicked.connect(self._choose_files)
        top_buttons.addWidget(self.btn_add)
        top_buttons.addStretch()
        self.lbl_output = QLabel(f"저장 위치: {get_output_root()}")
        self.lbl_output.setObjectName("hint")
        top_buttons.addWidget(self.lbl_output)
        layout.addLayout(top_buttons)

        # 중단: 목록
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["원본 파일명", "변경될 파일명", "비목 (저장 폴더)", "상태", "폴더 열기"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_SOURCE, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_TARGET, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_CATEGORY, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_OPEN, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, stretch=1)

        edit_hint = QLabel(
            "변경될 파일명 / 비목 칸을 더블클릭하면 직접 수정할 수 있습니다. "
            "비목 폴더: " + ", ".join(folder_names())
        )
        edit_hint.setObjectName("hint")
        edit_hint.setWordWrap(True)
        layout.addWidget(edit_hint)

        # 하단: 제어부
        controls = QHBoxLayout()
        self.btn_start = QPushButton("작업 시작")
        self.btn_start.setObjectName("primary")
        self.btn_start.clicked.connect(self.start_processing)
        self.btn_clear = QPushButton("목록 초기화")
        self.btn_clear.clicked.connect(self.clear_list)
        controls.addWidget(self.btn_start)
        controls.addWidget(self.btn_clear)
        controls.addStretch()
        layout.addLayout(controls)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #444444;")
        layout.addWidget(line)

        notice = QLabel("원본 파일은 그대로 유지되며, 새 파일명으로 복사본이 저장됩니다.")
        notice.setObjectName("hint")
        layout.addWidget(notice)

        self.setAcceptDrops(True)

    # 창 전체에서도 드롭 허용
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        self.add_files(paths)

    # ------------------------------------------------------------- 파일 추가
    def _choose_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "PDF 파일 선택", "", "PDF 파일 (*.pdf)")
        if paths:
            self.add_files(paths)

    def add_files(self, paths: list[str]) -> None:
        existing = {r.source.resolve() for r in self._rows}
        skipped_non_pdf = 0
        added = 0
        for raw in paths:
            p = Path(raw)
            if p.suffix.lower() != ".pdf" or not p.is_file():
                skipped_non_pdf += 1
                continue
            if p.resolve() in existing:
                continue
            if len(self._rows) >= MAX_FILES:
                QMessageBox.warning(self, "업로드 제한", f"한 번에 최대 {MAX_FILES}개의 PDF만 추가할 수 있습니다.")
                break
            self._append_row(p)
            existing.add(p.resolve())
            added += 1
        if skipped_non_pdf and not added:
            QMessageBox.information(self, "알림", "PDF 파일만 추가할 수 있습니다.")

    def _append_row(self, path: Path) -> None:
        self._updating = True
        try:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._rows.append(RowState(source=path))

            src_item = QTableWidgetItem(path.name)
            src_item.setFlags(src_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            src_item.setToolTip(str(path))
            self.table.setItem(row, COL_SOURCE, src_item)

            self.table.setItem(row, COL_TARGET, QTableWidgetItem(""))
            self.table.setItem(row, COL_CATEGORY, QTableWidgetItem(""))

            status_item = QTableWidgetItem(STATUS_WAITING)
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, COL_STATUS, status_item)

            btn = QPushButton("폴더 열기")
            btn.setEnabled(False)
            btn.clicked.connect(lambda _=False, r=row: self._open_folder(r))
            self.table.setCellWidget(row, COL_OPEN, btn)
        finally:
            self._updating = False

    def clear_list(self) -> None:
        if self._thread is not None:
            return
        self.table.setRowCount(0)
        self._rows.clear()
        self.progress.setValue(0)

    # ------------------------------------------------------------ 수동 수정
    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating:
            return
        row = item.row()
        if row >= len(self._rows):
            return
        state = self._rows[row]
        if item.column() in (COL_TARGET, COL_CATEGORY):
            state.manual = True
            if state.status == STATUS_DONE:
                # 완료된 항목을 수정하면 다시 처리할 수 있게 대기 상태로 돌린다.
                state.status = STATUS_WAITING
                state.saved_path = None
                self._set_status(row, STATUS_WAITING, "")
                self._set_open_enabled(row, False)
            if item.column() == COL_CATEGORY:
                # 입력한 비목을 폴더명(예: 01. 인건비)으로 정규화해서 보여준다.
                try:
                    folder = folder_name_for(item.text())
                except ValueError:
                    folder = ""
                if folder and folder != item.text():
                    self._updating = True
                    try:
                        item.setText(folder)
                    finally:
                        self._updating = False

    # -------------------------------------------------------------- 작업
    def start_processing(self) -> None:
        if self._thread is not None:
            return
        jobs: list[Job] = []
        for row, state in enumerate(self._rows):
            if state.status == STATUS_DONE:
                continue
            job = Job(row=row, source=state.source)
            if state.parsed or state.manual:
                job.manual_filename = self._cell_text(row, COL_TARGET)
                job.manual_category = self._cell_text(row, COL_CATEGORY)
            jobs.append(job)

        if not jobs:
            QMessageBox.information(self, "알림", "처리할 파일이 없습니다. PDF 파일을 먼저 추가하세요.")
            return

        self._set_busy(True)
        self.progress.setValue(0)
        self._results: list[JobResult] = []

        self._thread = QThread(self)
        self._worker = Worker(jobs, get_output_root())
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.result.connect(self._on_result)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._thread.start()

    def _on_progress(self, done: int, total: int) -> None:
        self.progress.setValue(int(done * 100 / total) if total else 0)

    def _on_result(self, result: JobResult) -> None:
        self._results.append(result)
        state = self._rows[result.row]
        state.parsed = True
        state.status = result.status
        state.saved_path = result.saved_path
        self._updating = True
        try:
            self.table.item(result.row, COL_TARGET).setText(result.filename)
            self.table.item(result.row, COL_TARGET).setToolTip(result.message)
            try:
                folder = folder_name_for(result.category) if result.category else ""
            except ValueError:
                folder = result.category or ""
            self.table.item(result.row, COL_CATEGORY).setText(folder)
        finally:
            self._updating = False
        self._set_status(result.row, result.status, result.message)
        self._set_open_enabled(result.row, result.status == STATUS_DONE)

    def _on_finished(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._worker = None
        self._set_busy(False)
        self.progress.setValue(100)

        done = [r for r in self._results if r.status == STATUS_DONE]
        errors = [r for r in self._results if r.status == STATUS_ERROR]
        if len(done) == 1 and not errors:
            QMessageBox.information(self, "완료", f"{done[0].saved_path.parent} 폴더에 저장되었습니다.")
            return
        folders = sorted({str(r.saved_path.parent) for r in done if r.saved_path})
        lines = []
        if done:
            lines.append(f"{len(done)}개 파일이 다음 폴더에 저장되었습니다.")
            lines += [f"  - {f}" for f in folders]
        if errors:
            lines.append("")
            lines.append(f"{len(errors)}개 파일은 정보 추출에 실패했습니다. "
                         "목록에서 파일명/비목을 직접 수정한 뒤 [작업 시작]을 다시 누르세요.")
        QMessageBox.information(self, "완료" if not errors else "완료 (일부 에러)", "\n".join(lines))

    # ------------------------------------------------------------- 헬퍼
    def _cell_text(self, row: int, col: int) -> str:
        item = self.table.item(row, col)
        return item.text().strip() if item else ""

    def _set_status(self, row: int, status: str, tooltip: str) -> None:
        self._updating = True
        try:
            item = self.table.item(row, COL_STATUS)
            item.setText(status)
            item.setToolTip(tooltip)
        finally:
            self._updating = False

    def _set_open_enabled(self, row: int, enabled: bool) -> None:
        widget = self.table.cellWidget(row, COL_OPEN)
        if widget is not None:
            widget.setEnabled(enabled)

    def _set_busy(self, busy: bool) -> None:
        for w in (self.btn_add, self.btn_start, self.btn_clear, self.drop_area):
            w.setEnabled(not busy)
        self.table.setEnabled(not busy)

    def _open_folder(self, row: int) -> None:
        if row >= len(self._rows):
            return
        saved = self._rows[row].saved_path
        if not saved:
            return
        folder = saved.parent
        if sys.platform == "win32":
            try:
                subprocess.Popen(["explorer", "/select,", str(saved)])
                return
            except Exception:
                pass
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
