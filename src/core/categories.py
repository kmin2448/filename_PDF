"""비목(예산 항목) → 출력 폴더명 매핑.

추출된 비목 문자열을 번호가 붙은 폴더명으로 변환한다.
예) "인건비" -> "01. 인건비", "장학금" -> "02. 장학금"
"""
from __future__ import annotations

import re

# (번호, 비목명) - 폴더 정렬 순서를 유지하기 위해 리스트로 관리한다.
# 번호는 기관의 예산 비목 코드 체계를 그대로 따르므로 연속되지 않을 수 있다.
BUDGET_CATEGORIES: list[tuple[str, str]] = [
    ("01", "인건비"),
    ("02", "장학금"),
    ("03", "교육연구프로그램개발운영비"),
    ("04", "교육연구환경개선비"),
    ("05", "실험실습장비및기자재구입운영비"),
    ("07", "기업지원협력활동비"),
    ("08", "성과활용확산지원비"),
    ("09", "그 밖의사업운영경비"),
]

_INVALID_FOLDER_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]')


def normalize(text: str | None) -> str:
    """공백을 모두 제거해 비교용 문자열로 만든다."""
    return re.sub(r"\s+", "", text or "")


def category_names() -> list[str]:
    """등록된 비목명 목록 (파서에서 텍스트 매칭용으로 사용)."""
    return [name for _, name in BUDGET_CATEGORIES]


def folder_names() -> list[str]:
    """생성될 폴더명 목록. 예) ['01. 인건비', '02. 장학금', ...]"""
    return [f"{num}. {name}" for num, name in BUDGET_CATEGORIES]


def folder_name_for(category: str | None) -> str:
    """추출된 비목 문자열에 해당하는 폴더명을 반환한다.

    - 등록된 비목과 일치(공백 무시)하면 "NN. 비목명" 형식으로 반환
    - 부분 일치(추출 문자열이 비목명을 포함하거나 그 반대)도 허용
    - 등록되지 않은 비목은 원문에서 파일시스템 금지 문자만 제거해 그대로 사용
    """
    raw = (category or "").strip()
    key = normalize(raw)
    if not key:
        raise ValueError("비목이 비어 있습니다.")

    # 이미 "01. 인건비" 형태로 입력된 경우 (수동 수정 등) 그대로 인정
    for num, name in BUDGET_CATEGORIES:
        if key == normalize(f"{num}. {name}") or key == normalize(f"{num}.{name}"):
            return f"{num}. {name}"

    # 정확히 일치
    for num, name in BUDGET_CATEGORIES:
        if normalize(name) == key:
            return f"{num}. {name}"

    # 부분 일치 - 긴 이름부터 검사해 짧은 이름에 잘못 걸리는 것을 방지
    ordered = sorted(BUDGET_CATEGORIES, key=lambda c: len(normalize(c[1])), reverse=True)
    for num, name in ordered:
        norm_name = normalize(name)
        if norm_name in key or (len(key) >= 3 and key in norm_name):
            return f"{num}. {name}"

    # 미등록 비목: 원문 그대로(금지문자 제거)
    cleaned = _INVALID_FOLDER_CHARS.sub(" ", raw)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().rstrip(".")
    if not cleaned:
        raise ValueError(f"폴더명으로 사용할 수 없는 비목입니다: {category!r}")
    return cleaned
