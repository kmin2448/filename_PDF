import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QProgressBar, QMessageBox, QFileDialog,
    QTableWidgetItem, QHeaderView, QLineEdit
)
from PyQt6.QtCore import Qt
from src.ui.components import DropArea, FileTable, FolderOpenButton
from src.ui.worker import ProcessWorker
from src.core.file_manager import FileManager
from src.core.config import Config

MAX_FILES = 50

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Auto-Renamer")
        self.resize(1000, 700)
        
        # 다크 모드 스타일시트 적용
        self.setStyleSheet("""
            QMainWindow {
                background-color: #111827;
                color: #f3f4f6;
            }
            QWidget {
                font-family: 'Pretendard', 'Malgun Gothic', 'Segoe UI', 'Arial';
            }
            QLabel {
                color: #e5e7eb;
            }
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:disabled {
                background-color: #4b5563;
                color: #9ca3af;
            }
            QTableWidget {
                background-color: #1f2937;
                color: #f3f4f6;
                gridline-color: #374151;
                border: 1px solid #374151;
                border-radius: 4px;
            }
            QHeaderView::section {
                background-color: #374151;
                color: #f3f4f6;
                padding: 6px;
                border: none;
                font-weight: bold;
            }
            QLineEdit {
                background-color: #1f2937;
                color: #f3f4f6;
                border: 1px solid #374151;
                border-radius: 4px;
                padding: 8px;
            }
            QProgressBar {
                border: 1px solid #374151;
                border-radius: 4px;
                text-align: center;
                background-color: #1f2937;
                color: #f3f4f6;
            }
            QProgressBar::chunk {
                background-color: #10b981;
                border-radius: 4px;
            }
            QMessageBox {
                background-color: #ffffff;
            }
            QMessageBox QLabel {
                color: #000000;
            }
        """)

        # Main Widget & Layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 0. 최상단: 저장 루트 폴더 선택
        root_layout = QHBoxLayout()
        root_title = QLabel("저장 루트 폴더")
        root_title.setStyleSheet("font-weight: bold; color: #f3f4f6;")

        self.root_path_edit = QLineEdit(Config.get_root_dir())
        self.root_path_edit.setReadOnly(True)
        self.root_path_edit.setToolTip("이 폴더 아래에 비목별 폴더가 자동으로 생성됩니다.")

        self.btn_change_root = QPushButton("폴더 변경")
        self.btn_change_root.clicked.connect(self.change_root_dir)

        self.btn_reset_root = QPushButton("기본값")
        self.btn_reset_root.setToolTip("바탕화면/청구서정리 로 되돌립니다.")
        self.btn_reset_root.setStyleSheet("background-color: #6b7280;")
        self.btn_reset_root.clicked.connect(self.reset_root_dir)

        self.btn_open_root = QPushButton("폴더 열기")
        self.btn_open_root.setStyleSheet("background-color: #374151; border: 1px solid #4b5563;")
        self.btn_open_root.clicked.connect(self.open_root_dir)

        root_layout.addWidget(root_title)
        root_layout.addWidget(self.root_path_edit, stretch=1)
        root_layout.addWidget(self.btn_change_root)
        root_layout.addWidget(self.btn_reset_root)
        root_layout.addWidget(self.btn_open_root)
        layout.addLayout(root_layout)

        # 1. 상단: 드래그 앤 드롭 & 파일 추가 로직
        top_layout = QVBoxLayout()
        self.drop_area = DropArea()
        self.drop_area.setMinimumHeight(100)
        self.drop_area.files_dropped.connect(self.add_files)
        top_layout.addWidget(self.drop_area)

        add_btn_layout = QHBoxLayout()
        self.btn_add_files = QPushButton("파일 추가")
        self.btn_add_files.clicked.connect(self.browse_files)
        add_btn_layout.addStretch()
        add_btn_layout.addWidget(self.btn_add_files)
        top_layout.addLayout(add_btn_layout)
        layout.addLayout(top_layout)

        # 2. 중단: 목록 Table
        self.table = FileTable()
        layout.addWidget(self.table)

        # 3. 하단: 제어부
        bottom_layout = QVBoxLayout()
        
        info_label = QLabel("※ 파일은 [저장 루트 폴더]/[비목] 경로에 복사되며, 원본 PDF 파일은 안전하게 유지됩니다.")
        info_label.setStyleSheet("color: #9ca3af; font-size: 13px;")
        bottom_layout.addWidget(info_label)

        ctrl_layout = QHBoxLayout()
        self.btn_reset = QPushButton("목록 초기화")
        self.btn_reset.setStyleSheet("background-color: #ef4444;")
        self.btn_reset.clicked.connect(self.clear_table)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% (0/0)")
        
        self.btn_start = QPushButton("작업 시작")
        self.btn_start.setStyleSheet("background-color: #10b981;")
        self.btn_start.clicked.connect(self.start_processing)
        
        ctrl_layout.addWidget(self.btn_reset)
        ctrl_layout.addWidget(self.progress_bar, stretch=1)
        ctrl_layout.addWidget(self.btn_start)
        bottom_layout.addLayout(ctrl_layout)

        layout.addLayout(bottom_layout)
        
        self.worker = None

    def change_root_dir(self):
        current = self.root_path_edit.text().strip() or Config.get_root_dir()
        # 아직 만들어지지 않은 폴더면 상위 폴더에서 탐색 시작
        start_dir = current if os.path.isdir(current) else os.path.dirname(current)
        selected = QFileDialog.getExistingDirectory(self, "비목별 폴더를 생성할 루트 폴더 선택", start_dir)
        if selected:
            Config.set_root_dir(selected)
            self.root_path_edit.setText(selected)

    def reset_root_dir(self):
        Config.reset_root_dir()
        self.root_path_edit.setText(Config.get_root_dir())

    def open_root_dir(self):
        path = self.root_path_edit.text().strip()
        try:
            os.makedirs(path, exist_ok=True)
        except Exception as e:
            QMessageBox.warning(self, "경고", f"폴더를 열 수 없습니다.\n{str(e)}")
            return
        FileManager.open_directory(path)

    def browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "PDF 파일 선택", "", "PDF Files (*.pdf)")
        if files:
            self.add_files(files)

    def add_files(self, files):
        current_rows = self.table.rowCount()
        new_pdf_files = [f for f in files if f.lower().endswith('.pdf')]
        
        if len(new_pdf_files) == 0:
            QMessageBox.warning(self, "경고", "PDF 파일만 추가 스크립트가 가능합니다.")
            return

        added_count = 0
        for file_path in new_pdf_files:
            if current_rows + added_count >= MAX_FILES:
                QMessageBox.warning(self, "제한 초과", f"최대 {MAX_FILES}개까지만 처리가 가능합니다.")
                break
                
            # 중복 체크
            is_dup = False
            for r in range(self.table.rowCount()):
                if self.table.item(r, 0).data(Qt.ItemDataRole.UserRole) == file_path:
                    is_dup = True
                    break
            if is_dup: continue

            row = self.table.rowCount()
            self.table.insertRow(row)

            # 0번 컬럼: 원본파일명
            filename = os.path.basename(file_path)
            item_src = QTableWidgetItem(filename)
            item_src.setData(Qt.ItemDataRole.UserRole, file_path) # Data 숨김 저장
            item_src.setFlags(item_src.flags() & ~Qt.ItemFlag.ItemIsEditable) # 읽기 전용
            self.table.setItem(row, 0, item_src)

            # 1번 컬럼: 변경될 파일명 (더블클릭 편집 가능) -> 툴팁 표시
            item_dest = QTableWidgetItem("")
            item_dest.setToolTip("더블클릭하여 파일명을 직접 지정할경우, 이 이름이 우선으로 사용됩니다.")
            self.table.setItem(row, 1, item_dest)

            # 2번 컬럼: 상태
            item_status = QTableWidgetItem("대기")
            item_status.setFlags(item_status.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 2, item_status)
            
            # 3번 컬럼: 폴더열기 (버튼은 비워두고, 완료 시 삽입)
            empty_item = QTableWidgetItem("")
            empty_item.setFlags(empty_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 3, empty_item)
            
            added_count += 1

    def clear_table(self):
        self.table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p% (0/0)")

    def start_processing(self):
        total_rows = self.table.rowCount()
        if total_rows == 0:
            QMessageBox.information(self, "알림", "처리할 파일이 없습니다.")
            return

        # 저장 루트 폴더 확인 (없으면 생성)
        root_dir = self.root_path_edit.text().strip() or Config.get_root_dir()
        try:
            os.makedirs(root_dir, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(
                self, "저장 폴더 오류",
                f"저장 루트 폴더를 사용할 수 없습니다.\n\n{root_dir}\n{str(e)}\n\n[폴더 변경] 버튼으로 다른 폴더를 지정해 주세요."
            )
            return

        # UI 잠금
        self.btn_start.setEnabled(False)
        self.btn_reset.setEnabled(False)
        self.btn_add_files.setEnabled(False)
        self.btn_change_root.setEnabled(False)
        self.btn_reset_root.setEnabled(False)
        self.drop_area.setAcceptDrops(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(f"%p% (0/{total_rows})")

        # 워커로 보낼 배열 생성
        task_list = []
        for i in range(total_rows):
            # 상태를 '처리 중' 으로 변경
            self.table.item(i, 2).setText("처리 중")
            
            src_path = self.table.item(i, 0).data(Qt.ItemDataRole.UserRole)
            custom_name = self.table.item(i, 1).text().strip()
            
            task_list.append({
                'row': i,
                'source_path': src_path,
                'custom_filename': custom_name
            })

        self.worker = ProcessWorker(task_list, root_dir)
        self.worker.item_processed.connect(self.on_item_processed)
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.finished_processing.connect(self.on_finished)
        self.worker.start()

    def on_item_processed(self, row, final_name, status_text, target_dir):
        # UI 업데이트
        if final_name:
            self.table.item(row, 1).setText(final_name)
        
        if "[에러]" in status_text:
            self.table.item(row, 2).setText(status_text)
            self.table.item(row, 2).setForeground(Qt.GlobalColor.red)
        else:
            self.table.item(row, 2).setText(status_text)
            self.table.item(row, 2).setForeground(Qt.GlobalColor.green)
            
            if target_dir: # 성공적으로 복사되었으면 버튼 추가
                btn_widget = FolderOpenButton(target_dir)
                self.table.setCellWidget(row, 3, btn_widget)

    def on_progress_updated(self, current, total):
        val = int((current / total) * 100)
        self.progress_bar.setValue(val)
        self.progress_bar.setFormat(f"%p% ({current}/{total})")

    def on_finished(self, total, success, error):
        self.btn_start.setEnabled(True)
        self.btn_reset.setEnabled(True)
        self.btn_add_files.setEnabled(True)
        self.btn_change_root.setEnabled(True)
        self.btn_reset_root.setEnabled(True)
        self.drop_area.setAcceptDrops(True)
        
        QMessageBox.information(self, "작업 완료", f"총 {total}건의 작업이 완료되었습니다.\n성공: {success}건\n오류: {error}건")
