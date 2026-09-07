# PDF Auto-Renamer

업로드한 PDF 청구서 내부의 텍스트를 추출해 지정된 규칙에 맞게 파일명을 자동 변경하고,
비목별 폴더로 분류해주는 Windows 데스크톱 GUI 프로그램입니다.

## 실행 파일(EXE) 다운로드

Windows용 실행 파일은 GitHub Actions에서 자동으로 빌드됩니다. 별도 설치 없이 `PDF_Auto-Renamer.exe` 하나만 받아 실행하면 됩니다.

- **최신 빌드**: 저장소의 **Actions** 탭 → `Build Windows EXE` 워크플로 → 가장 최근 성공한 실행 → 하단 **Artifacts**의 `PDF_Auto-Renamer-windows` 다운로드 (zip 안에 exe가 들어 있습니다. GitHub 로그인 필요)
- **정식 배포본**: `v1.0.0` 처럼 `v`로 시작하는 태그를 푸시하면 **Releases** 페이지에 exe가 자동으로 첨부됩니다.

```bash
git tag v1.0.0
git push origin v1.0.0
```

> 처음 실행할 때 Windows SmartScreen 경고가 뜨면 **추가 정보 → 실행**을 누르세요. (코드 서명이 없는 개인 배포용 실행 파일이라 나타나는 안내입니다.)

## 기능

- PDF 다중 업로드 (드래그 앤 드롭 / 파일 탐색기, 최대 50개)
- 1페이지에서 이체일자, 적요, 비목, 금회청구액 추출
- 3페이지에서 거래처명(성명) 추출
- `(YYMMDD) 적요_거래처명(성명)_(금회청구액).pdf` 형식으로 파일명 자동 생성
- `바탕화면/청구서정리/[비목]/` 경로에 자동 분류 저장 (원본 파일은 그대로 유지)
- 정보 추출에 실패한 항목은 목록에서 파일명·비목을 더블클릭해 직접 수정한 뒤 다시 실행 가능
- 완료된 항목은 [폴더 열기] 버튼으로 저장 위치를 바로 확인

## 비목 폴더 이름 규칙

비목 폴더는 아래와 같이 **번호가 붙은 이름**으로 자동 생성됩니다. 추출된 비목의 띄어쓰기 차이는 무시하고 매칭합니다.

| 추출된 비목 | 생성되는 폴더 |
| --- | --- |
| 인건비 | `01. 인건비` |
| 장학금 | `02. 장학금` |
| 교육연구프로그램개발운영비 | `03. 교육연구프로그램개발운영비` |
| 교육연구환경개선비 | `04. 교육연구환경개선비` |
| 실험실습장비및기자재구입운영비 | `05. 실험실습장비및기자재구입운영비` |
| 기업지원협력활동비 | `07. 기업지원협력활동비` |
| 성과활용확산지원비 | `08. 성과활용확산지원비` |
| 그 밖의사업운영경비 | `09. 그 밖의사업운영경비` |

목록에 없는 비목은 번호 없이 비목명 그대로 폴더가 만들어집니다.
번호나 비목을 추가·변경하려면 [`src/core/categories.py`](src/core/categories.py)의 `BUDGET_CATEGORIES` 목록만 수정하면 됩니다.

자세한 사양은 [prd.md](prd.md)를 참고하세요.

## 기술 스택

- Python 3.x
- PyQt6 (GUI)
- pdfplumber (PDF 파싱)
- PyInstaller (실행 파일 패키징)

## 소스에서 실행

```bash
pip install -r requirements.txt
python main.py
```

## 테스트

```bash
pip install reportlab   # 파서 테스트용 샘플 PDF 생성에 필요 (선택)
python -m unittest discover -s tests -v
```

## 실행 파일 직접 빌드

```bash
pyinstaller --clean --noconfirm PDF_AutoRenamer.spec
```

빌드 결과물은 `dist/PDF_Auto-Renamer.exe` 로 생성됩니다.

## 프로젝트 구조

```
main.py                  # 진입점
src/core/categories.py   # 비목 → 번호 폴더명 매핑
src/core/parser.py       # pdfplumber 기반 청구서 정보 추출
src/core/renamer.py      # 파일명 조합, 바탕화면 경로, 폴더 생성 및 복사
src/ui/main_window.py    # PyQt6 다크 모드 메인 창
tests/                   # 단위 테스트
.github/workflows/       # Windows EXE 자동 빌드
```

## 주의

100% 로컬 환경에서만 동작하며, 외부 서버로 데이터를 전송하지 않습니다.
실제 청구서 PDF와 파싱 결과 파일은 개인정보 및 계좌정보를 포함하므로
`.gitignore`에 의해 저장소에 커밋되지 않습니다.
