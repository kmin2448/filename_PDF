import os
import pdfplumber
import re
from typing import Dict, Any

class ParserError(Exception):
    pass

class PDFParser:
    @staticmethod
    def parse(file_path: str) -> Dict[str, Any]:
        result = {
            "date": "",
            "summary": "",
            "category": "",
            "amount": "",
            "partner": "",
            "error": None
        }
        
        try:
            with pdfplumber.open(file_path) as pdf:
                # 1. 대상 페이지 유효성 검사
                if len(pdf.pages) < 1:
                    raise ParserError("PDF 페이지를 읽을 수 없습니다.")
                
                # --- 1페이지 분석 ---
                page_1 = pdf.pages[0]
                tables_1 = page_1.extract_tables()
                if not tables_1:
                    raise ParserError("1페이지에서 표(Table)를 찾지 못했습니다.")
                
                # 이체일자, 적요 찾기
                found_date = False
                found_summary = False
                
                for table in tables_1:
                    for row in table:
                        # 리스트 내 모든 None 제거 및 문자열 변환
                        clean_row = [str(cell).strip() for cell in row if cell is not None]
                        
                        # 1) 이체일자
                        if not found_date:
                            for i, cell in enumerate(clean_row):
                                if "이체일자 :" in cell or "이체일자:" in cell:
                                    # 이체일자 글자 자체가 분리되어 있지 않고 같이 들어있을 경우
                                    if len(cell) > 7:
                                        date_str = cell.replace("이체일자", "").replace(":", "").strip()
                                        if date_str:
                                            result["date"] = date_str
                                            found_date = True
                                            break
                                    # 다음 인덱스 혹은 다다음 인덱스에 날짜가 있을 경우
                                    else:
                                        # 남은 배열 내에서 202x로 시작하는 포맷 찾기
                                        for remain in clean_row[i+1:]:
                                            if re.match(r'20\d{2}-\d{2}-\d{2}', remain):
                                                result["date"] = remain
                                                found_date = True
                                                break
                        
                        # 2) 적요
                        if not found_summary and len(clean_row) >= 2:
                            if clean_row[0] == "적요":
                                raw_summary = clean_row[1]
                                # 개행문자는 공백으로 치환
                                result["summary"] = raw_summary.replace("\n", " ").strip()
                                found_summary = True
                                
                # 비목 & 금회청구액 찾기
                found_category = False
                for table in tables_1:
                    # 헤더행을 찾기
                    header_idx = -1
                    category_col = -1
                    amount_col = -1
                    
                    for r_idx, row in enumerate(table):
                        row_strs = [str(x).replace('\n', '') if x is not None else "" for x in row]
                        if "비목" in row_strs:
                            header_idx = r_idx
                            category_col = row_strs.index("비목")
                            # 금회청구액 인덱스 찾기
                            for c_idx, cell in enumerate(row_strs):
                                if "금회청구액" in cell:
                                    amount_col = c_idx
                                    break
                            break
                    
                    if header_idx != -1 and amount_col != -1 and category_col != -1:
                        # 데이터 행 순회
                        for row in table[header_idx+1:]:
                            row_strs = [str(x) if x is not None else "" for x in row]
                            # 데이터가 충분한지 확인
                            if len(row_strs) > amount_col:
                                amt_str = row_strs[amount_col].replace(',', '').strip()
                                # 0이 아니고 숫자로 구성되어있다면 청구항목으로 인식
                                if amt_str and amt_str != '0' and amt_str.isdigit():
                                    raw_cat = row_strs[category_col]
                                    result["category"] = raw_cat.replace("\n", " ").strip()
                                    result["amount"] = row_strs[amount_col].strip() # 콤마 포함 원형 유지
                                    found_category = True
                                    break
                    if found_category:
                        break
                        
                # --- 3페이지 이상 분석 (거래처명, 여러 페이지에 걸쳐 있는 경우 모두 탐색) ---
                if len(pdf.pages) >= 3:
                    partners = []
                    for page in pdf.pages[2:6]: # 3~6페이지까지만 제한하여 속도 최적화
                        text_content = page.extract_text() or ""
                        # '지급명세서' 관련 키워드가 없는 페이지는 표 추출 스킵
                        if "지급명세서" not in text_content.replace(" ", ""):
                            continue
                            
                        tables = page.extract_tables()
                        for table in tables:
                            header_idx = -1
                            partner_col = -1
                            
                            for r_idx, row in enumerate(table):
                                row_strs = [str(x).replace('\n', '') if x is not None else "" for x in row]
                                # "거래처명(성명)" 형태를 찾기 포괄적 탐색
                                for c_idx, cell in enumerate(row_strs):
                                    if "거래처명" in cell or "성명" in cell:
                                        header_idx = r_idx
                                        partner_col = c_idx
                                        break
                                if header_idx != -1:
                                    break
                                    
                            if header_idx != -1 and partner_col != -1:
                                for row in table[header_idx+1:]:
                                    row_strs = [str(x) if x is not None else "" for x in row]
                                    if len(row_strs) > partner_col:
                                        # 순번이 숫자인 행이면 거래처로 간주
                                        if row_strs[0].isdigit():
                                            raw_partner = row_strs[partner_col]
                                            clean_partner = raw_partner.replace("\n", "").strip()
                                            if clean_partner:
                                                partners.append(clean_partner)
                    
                    if partners:
                        if len(partners) <= 3:
                            result["partner"] = ", ".join(partners)
                        else:
                            result["partner"] = f"{partners[0]} 외 {len(partners) - 1}건"
                                        
                # YYMMDD 날짜 포맷팅 변환 (예: 2026-02-27 -> 260227)
                if result["date"]:
                    match = re.search(r'\d{4}-\d{2}-\d{2}', result["date"])
                    if match:
                        raw_date_str = match.group()
                        parts = raw_date_str.split('-')
                        if len(parts) == 3:
                            result["date"] = f"{parts[0][2:]}{parts[1]}{parts[2]}"
                            
                # 필드 누락 검열(경고용, 실제 에러는 아님, 빈칸으로 UI에 노출되도록)
                if not result["date"] or not result["summary"] or not result["category"] or not result["amount"] or not result["partner"]:
                    missing = []
                    if not result["date"]: missing.append("이체일자")
                    if not result["summary"]: missing.append("적요")
                    if not result["category"]: missing.append("비목")
                    if not result["amount"]: missing.append("금회청구액")
                    if not result["partner"]: missing.append("거래처명")
                    # 필수 항목이 전부 없다면 파싱 실패 예외로 처리
                    if len(missing) >= 4:
                        raise ParserError("문서에서 주요 데이터를 찾지 못했습니다.")
                        
        except Exception as e:
            result["error"] = f"에러: {str(e)}"
            
        return result
