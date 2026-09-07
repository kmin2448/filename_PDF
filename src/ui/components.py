from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QPushButton, QHeaderView, QWidget, QHBoxLayout
)
from PyQt6.QtCore import Qt, pyqtSignal
from src.core.file_manager import FileManager

class DropArea(QFrame):
    files_dropped = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #6b7280;
                border-radius: 8px;
                background-color: #1f2937;
            }
        """)
        
        layout = QVBoxLayout()
        label = QLabel("여기에 PDF 파일들을 끌어서 추가해 주세요.<br><br>또는 [파일 추가] 버튼 클릭")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #d1d5db; font-size: 14px; border: none; background: transparent; padding: 10px;")
        
        layout.addWidget(label)
        self.setLayout(layout)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = []
        for url in event.mimeData().urls():
            files.append(url.toLocalFile())
        self.files_dropped.emit(files)

class FileTable(QTableWidget):
    def __init__(self):
        super().__init__(0, 4) # 파일명, 대상파일명, 상태, 폴더열기
        self.setHorizontalHeaderLabels(["원본 파일명", "변경될 파일명 (더블클릭 편집)", "상태", "폴더 열기"])
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        self.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)
        # 1컬럼(변경될 파일명)을 제외하고는 편집 금지 로직은 뷰에서 처리

    def keyPressEvent(self, event):
        # 삭제 버튼 (Delete/Backspace) 지원
        if event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace:
            rows = set(item.row() for item in self.selectedItems())
            for row in sorted(rows, reverse=True):
                self.removeRow(row)
        else:
            super().keyPressEvent(event)

class FolderOpenButton(QWidget):
    def __init__(self, folder_path, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn = QPushButton("폴더 열기")
        self.btn.setStyleSheet("""
            QPushButton {
                background-color: #374151;
                color: #e5e7eb;
                border: 1px solid #4b5563;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)
        layout.addWidget(self.btn)
        self.setLayout(layout)
        
        self.btn.clicked.connect(lambda: FileManager.open_directory(folder_path))
