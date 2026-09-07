from PyQt6.QtCore import QThread, pyqtSignal
from src.core.parser import PDFParser
from src.core.file_manager import FileManager
import os

class ProcessWorker(QThread):
    # (row_index, target_filename, status_text, target_dir)
    item_processed = pyqtSignal(int, str, str, str)
    # (current, total)
    progress_updated = pyqtSignal(int, int)
    # 진행 완료 시 signal
    finished_processing = pyqtSignal(int, int, int) # 총 갯수, 성공 갯수, 에러 갯수

    def __init__(self, file_data_list, root_dir=None):
        """
        file_data_list : [{'row': int, 'source_path': str, 'custom_filename': str}]
        root_dir : 비목별 폴더가 생성될 루트 폴더 (None이면 설정값 사용)
        """
        super().__init__()
        self.file_data_list = file_data_list
        self.root_dir = root_dir

    def run(self):
        total = len(self.file_data_list)
        success_count = 0
        error_count = 0

        for i, item in enumerate(self.file_data_list):
            row_idx = item['row']
            source_path = item['source_path']
            custom_filename = item.get('custom_filename', '')

            try:
                # 파싱
                parsed_data = PDFParser.parse(source_path)

                if parsed_data.get("error"):
                    self.item_processed.emit(row_idx, "", f"[에러] 파싱 실패: {parsed_data.get('error')}", "")
                    error_count += 1
                else:
                    # 파일 복사, 중복된 경우 번호가 붙은 final_name이 반환됨
                    target_dir, final_name = FileManager.copy_to_target(
                        source_path, parsed_data, custom_filename, self.root_dir
                    )
                    self.item_processed.emit(row_idx, final_name, "완료", target_dir)
                    success_count += 1
            except Exception as e:
                self.item_processed.emit(row_idx, "", f"[에러] {str(e)}", "")
                error_count += 1

            # 프로그레스바 갱신
            self.progress_updated.emit(i + 1, total)

        # 전체 완료 알림
        self.finished_processing.emit(total, success_count, error_count)
