import sys
import os

# src 모듈 경로 인식용
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from src.ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    
    # 애플리케이션 시스템 기본 폰트 설정 (다크모드 지원을 위한 뼈대)
    font = app.font()
    font.setFamily("Pretendard")
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
