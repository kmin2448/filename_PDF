import os
import shutil
import re

from src.core.config import Config

class FileManager:
    # 비목명 -> 실제 생성할 폴더명 매핑
    # 키는 공백을 모두 제거한 형태 (PDF 줄바꿈 때문에 "교육 연구프로그램개발 운영비" 처럼 들어옴)
    CATEGORY_FOLDER_MAP = {
        "인건비": "01. 인건비",
        "장학금": "02. 장학금",
        "교육연구프로그램개발운영비": "03. 교육연구프로그램개발운영비",
        "교육연구환경개선비": "04. 교육연구환경개선비",
        "실험실습장비및기자재구입운영비": "05. 실험실습장비및기자재구입운영비",
        "지역연계협업지원비": "06. 지역연계협업지원비",
        "기업지원협력활동비": "07. 기업지원협력활동비",
        "성과활용확산지원비": "08. 성과활용확산지원비",
        "기타운영경비": "09. 그 밖의사업운영경비",
        # 문서에 따라 "그 밖의 사업운영경비"로 표기되는 경우도 동일 폴더로 처리
        "그밖의사업운영경비": "09. 그 밖의사업운영경비",
        "그밖의사업운영비": "09. 그 밖의사업운영경비",
        "간접비": "10. 간접비",
    }

    @staticmethod
    def map_category_to_folder(category: str) -> str:
        """비목명을 규정된 폴더명(번호 포함)으로 변환.
        매핑에 없는 비목은 원래 비목명을 그대로 사용한다.
        """
        if not category:
            return ""

        # 공백/줄바꿈을 모두 제거하여 비교 (PDF 추출 시 위치가 제각각임)
        normalized = "".join(category.split())

        if normalized in FileManager.CATEGORY_FOLDER_MAP:
            return FileManager.CATEGORY_FOLDER_MAP[normalized]

        # ">선택" 등 부가 문자가 붙은 경우를 대비해 긴 키부터 포함 여부 검사
        for key in sorted(FileManager.CATEGORY_FOLDER_MAP, key=len, reverse=True):
            if key in normalized:
                return FileManager.CATEGORY_FOLDER_MAP[key]

        return category.strip()

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """파일 시스템에서 허용하지 않는 특수문자 제거"""
        # \ / : * ? " < > |
        return re.sub(r'[\\/*?:"<>|]', "", name)

    @staticmethod
    def generate_target_filename(parsed_data: dict) -> str:
        """파싱된 데이터를 기반으로 타겟 파일명 생성
        Format: (YYMMDD) 적요_거래처명(성명)_(금회청구액).pdf
        """
        date_str = parsed_data.get("date", "000000")
        summary_str = parsed_data.get("summary", "적요없음")
        partner_str = parsed_data.get("partner", "거래처없음")
        amount_str = parsed_data.get("amount", "0")
        
        # 거래처명 중복 표시 방지 로직 (적요 안에 파싱된 거래처명이 포함된 경우 제거)
        clean_partner = partner_str
        if " 외 " in clean_partner:
            clean_partner = clean_partner.split(" 외 ")[0]
        if ", " in clean_partner:
            clean_partner = clean_partner.split(", ")[0]
            
        clean_partner = clean_partner.strip()
        
        if clean_partner and clean_partner != "거래처없음" and clean_partner in summary_str:
            base_name = f"({date_str}) {summary_str}_({amount_str})"
        else:
            base_name = f"({date_str}) {summary_str}_{partner_str}_({amount_str})"
            
        safe_name = FileManager.sanitize_filename(base_name)
        
        # 문자열이 너무 길 경우 적요를 자를 수 있음 (일단 그대로 사용)
        return f"{safe_name}.pdf"

    @staticmethod
    def get_target_directory(category: str, root_dir: str = None) -> str:
        """저장할 목표 디렉토리 경로 계산 ([루트 폴더]/[번호. 비목])
        root_dir 미지정 시 설정에 저장된 루트 폴더(기본: 바탕화면/청구서정리)를 사용한다.
        """
        if not root_dir or not str(root_dir).strip():
            root_dir = Config.get_root_dir()
        folder_name = FileManager.map_category_to_folder(category)
        safe_cat = FileManager.sanitize_filename(folder_name)
        if not safe_cat:
            safe_cat = "미분류비목"
        target_dir = os.path.join(root_dir, safe_cat)
        return target_dir

    @staticmethod
    def copy_to_target(source_path: str, parsed_data: dict, custom_filename: str = None, root_dir: str = None) -> tuple:
        """
        원본 파일을 대상 폴더로 복사합니다.
        :param source_path: 원본 PDF 경로
        :param parsed_data: 파싱된 데이터 Dict
        :param custom_filename: 유저가 UI에서 수정한 파일명 (있을 경우 최우선 사용)
        :param root_dir: 비목별 폴더를 생성할 루트 폴더 (미지정 시 설정값 사용)
        :return: (복사 완료된 폴더 경로, 최종 저장된 파일명) 튜플 반환
        """
        if not os.path.exists(source_path):
            raise FileNotFoundError("원본 파일을 찾을 수 없습니다.")

        # 파일명 결정
        if custom_filename and custom_filename.strip():
            final_filename = custom_filename.strip()
            # .pdf 확장자 없으면 추가
            if not final_filename.lower().endswith(".pdf"):
                final_filename += ".pdf"
        else:
            final_filename = FileManager.generate_target_filename(parsed_data)
            
        category = parsed_data.get("category", "")
        target_dir = FileManager.get_target_directory(category, root_dir)

        # 디렉토리 생성
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        # 파일명 중복 체크 및 순번 부여
        base, ext = os.path.splitext(final_filename)
        counter = 1
        target_file_path = os.path.join(target_dir, final_filename)
        while os.path.exists(target_file_path):
            final_filename = f"{base}_{counter}{ext}"
            target_file_path = os.path.join(target_dir, final_filename)
            counter += 1

        # 파일 복사
        shutil.copy2(source_path, target_file_path)

        return target_dir, final_filename

    @staticmethod
    def open_directory(path: str):
        """윈도우 탐색기로 해당 폴더 열기"""
        if os.path.exists(path):
            os.startfile(path)
