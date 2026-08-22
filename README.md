# PDF Auto-Renamer

업로드한 PDF 청구서 내부의 텍스트를 추출해 지정된 규칙에 맞게 파일명을 자동 변경하고,
비목별 폴더로 분류해주는 Windows 데스크톱 GUI 프로그램입니다.

## 기능

- PDF 다중 업로드 (드래그 앤 드롭 / 파일 탐색기)
- 1페이지에서 이체일자, 적요, 비목, 금회청구액 추출
- 3페이지에서 거래처명(성명) 추출
- `(YYMMDD) 적요_거래처명(성명)_(금회청구액).pdf` 형식으로 파일명 자동 생성
- `바탕화면/청구서정리/[비목]/` 경로에 자동 분류 저장 (원본 파일은 그대로 유지)

자세한 사양은 [prd.md](prd.md)를 참고하세요.

## 기술 스택

- Python 3.x
- PyQt6 (GUI)
- pdfplumber (PDF 파싱)
- PyInstaller (실행 파일 패키징)

## 설치 및 실행

```bash
pip install -r requirements.txt
python main.py
```

## 실행 파일 빌드

```bash
pyinstaller PDF_AutoRenamer.spec
```

빌드 결과물은 `dist/` 폴더에 생성됩니다.

## 주의

100% 로컬 환경에서만 동작하며, 외부 서버로 데이터를 전송하지 않습니다.
실제 청구서 PDF와 파싱 결과 파일은 개인정보 및 계좌정보를 포함하므로
`.gitignore`에 의해 저장소에 커밋되지 않습니다.
