# 설치 & 시작 (온보딩)

## 1. 설치

```bash
git clone https://github.com/kmjy98-sketch/Gyeongguk.git
cd Gyeongguk
pip install -e .            # 최소(mcp + PyMuPDF) — 디지털 PDF 처리까지 동작
# 또는 전부:
pip install -e ".[all]"     # + opendataloader · python-docx · anthropic
```

## 2. LAW_API_KEY 발급 (법령·판례 검증에 필수)

법제처 국가법령정보 OPEN API 키(OC 값)를 발급받는다.

1. **https://open.law.go.kr** 접속 → 회원가입/로그인
2. 상단 **OPEN API → OPEN API 활용신청** (또는 마이페이지 > OPEN API)
3. 활용 신청 후, 신청 시 등록한 **이메일의 `@` 앞부분(아이디)이 그대로 OC 값 = `LAW_API_KEY`** 다.
   - 예: 이메일이 `hong@gmail.com` 이면 → `LAW_API_KEY=hong`
4. 승인까지 수 분~수 시간 걸릴 수 있다.

`.env` 작성:

```bash
python -m girokhyeong_mcp.setup --init     # .env 생성(.env.example 복사)
# .env 를 열어 LAW_API_KEY=<OC값> 입력
python -m girokhyeong_mcp.setup --check    # 라이브 검증(법령 1건 실제 조회)
```

`--check` 가 `[check] OK …` 를 출력하면 준비 끝. (인자 없이 `python -m girokhyeong_mcp.setup` 만 실행하면 전체 상태 점검 + 다음 할 일 안내.)

> `.env` 는 cwd 또는 리포 루트에 두면 서버가 자동으로 읽는다(`config._autoload_dotenv`). 환경변수로 직접 줘도 된다(환경변수가 `.env` 보다 우선).

## 3. (선택) opendataloader OCR — Java 필요

스캔 PDF의 진짜 OCR·표 레이아웃 추출에는 [opendataloader-pdf](https://opendataloader.org)를 쓴다. **Java 11+ 가 PATH에 있어야** 동작한다.

- Java 설치: [Adoptium](https://adoptium.net/) (Temurin 11+).
- 없으면 자동으로 **PyMuPDF(디지털 텍스트레이어)** 로 폴백한다 — 디지털 PDF는 문제없이 처리.
- 스캔본 hybrid OCR:
  ```bash
  pip install "opendataloader-pdf[hybrid]"
  opendataloader-pdf-hybrid --port 5002 --ocr-lang "ko,en"
  # .env: GIROK_ODL_HYBRID=docling-fast   (또는 hybrid 백엔드명/주소)
  ```

## 4. MCP 클라이언트 등록 (예: Claude Code)

```json
{
  "mcpServers": {
    "girokhyeong": {
      "command": "girokhyeong-mcp",
      "env": {
        "LAW_API_KEY": "<OC값>",
        "GIROK_WORK_ROOT": "C:/work/기록형"
      }
    }
  }
}
```

`command`는 `pip install` 로 만들어진 콘솔 스크립트다. 안 잡히면 `"command": "python", "args": ["-m", "girokhyeong_mcp.server"]` 로 대체.

등록 후 클라이언트에서 **`check_setup`** 도구를 한 번 호출하면 키가 살아있는지 즉시 확인된다.

## 5. 첫 실행

```
solve_record(source="C:/cases/2025고합123", brief_type="형사변론요지서", party_side="변호인")
```

파싱 → 00_인벤토리.md 생성 + 단계 플레이북 반환. 호스트 LLM이 각 단계를 수행하며 `save_stage` 로 01~06을 저장한다. `auto=True` + `ANTHROPIC_API_KEY` 면 서버가 01~06을 직접 생성한다.

## 빠른 진단

| 증상 | 확인 |
|---|---|
| 법령·판례 도구가 "LAW_API_KEY 없음" | `python -m girokhyeong_mcp.setup --check` |
| 스캔 PDF가 빈 텍스트 | Java 설치 + opendataloader, 또는 hybrid OCR |
| `export_docx` 실패 | `pip install python-docx` |
| auto 모드 비활성 | `ANTHROPIC_API_KEY` 설정 |
