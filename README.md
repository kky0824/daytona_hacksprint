# Dry Run — Lab Material Rehearsal

> **실습 자료, 학생 PC에서 먼저.** Rehearse your lab material on every student’s machine — before class.
> Daytona HackSprint Seoul (2026-10-18)

Dry Run은 수업·실습 자료를 수업 전에 **여러 학생 PC 환경(Daytona 샌드박스)에서 동시에 리허설**하고, 크래시뿐 아니라 **에러 없이 결과만 다른 경우**까지 잡아낸다. **Nosana GPU에서 돌아가는 오픈소스 LLM**이 원인을 진단해 고치고, 모든 PC가 통과할 때까지 다시 돌려 **검증된 실습 키트**를 돌려준다.

![Dry Run 데모 화면](docs/demo.png)

## In the News

- **heise online (2026.01)** — [“Pandas 3.0 brings unified string type and performance optimization”](https://www.heise.de/en/news/Pandas-3-0-brings-unified-string-type-and-performance-optimization-11154474.html): 기존 코드 동작 변경
- **pandas.pydata.org (2026.01.21)** — [“pandas 3.0 released!”](https://pandas.pydata.org/community/blog/pandas-3.0.html): 공식 breaking change
- **The Carpentries blog** — [“Keeping track of problems”](https://carpentries.org/blog/2014/02/keeping-track-of-problems/): 설치 = 학습자 최대 난관
- **Garden Developer Productivity Survey (2021)** — [리포트](https://resources.garden.io/hubfs/Garden_Developer_Productivity_Survey_Report_2021.pdf): 개발자가 주 15시간 이상을 환경 설정 등 코드 외 작업에 사용 (벤더 설문)

## 문제 (Problem)

1. **선생님 PC에선 되는데, 학생 PC에선 안 된다.** 실습 자료는 늘 선생님 PC 한 대에서만 테스트된다. 학생 PC는 프로그램이 **설치 안 돼 있거나**, **버전이 다르거나**, 가져온 **파일이 다르다.** (예: 고교 3D 복원 실습에서 같은 설치 스크립트를 썼지만 수업 중 학생 PC가 줄줄이 멈췄다.)
2. **더 무서운 건, 에러 없이 결과만 다른 것.** 같은 코드가 학생 PC에서 에러 없이 끝나지만 결과는 선생님과 다르다. 에러가 없으니 선생님도 학생도 모른 채 수업이 진행된다.

## 해결책 (Solution)

1. **Upload**: 실습 자료 (PDF / PPTX, 또는 코드·requirements·데이터)
2. **Rehearse (Daytona)**: 선생님 PC + 학생 PC 3대를 병렬로 띄워 실행하고, 선생님 결과를 기준으로 실패 / 결과 다름 / 새 경고를 판정
3. **Fix (Nosana)**: Nosana GPU 위 vLLM으로 띄운 Qwen3-14B가 원인을 한국어로 설명하고 자료를 고침 (LLM이 실패하면 규칙 기반으로 대체)
4. **Verified Kit**: 모든 PC가 통과할 때까지 다시 돌리고, 검증된 키트를 zip으로 다운로드

### 학생 프로필

| 프로필 | 재현 방법 | 데모 실습에서 잡는 문제 |
|---|---|---|
| 선생님 PC | Daytona 기본 스냅샷 (패키지 이미 설치됨) | 기준 출력 |
| 새 PC 학생 | 빈 가상환경(venv)에 `pip install -r requirements.txt`만 설치 | requirements에 빠진 패키지 (matplotlib) |
| 바탕화면에서 실행한 학생 | 다른 폴더에서 `python lab/lesson.py` | 상대 경로 (`data.csv`) |
| 오늘 설치한 학생 | `pip install -U -r requirements.txt` (최신 버전) | pandas 3에서 **에러 없이 답이 바뀜** |

### 수업 자료(PDF / PPTX)로 시작하기

![수업 PDF 리허설 화면](docs/demo-slides.png)

웹 화면에서 **수업 자료로 시작하기**에 PDF나 PPTX를 올리면:

1. 슬라이드에서 학생이 터미널에 입력하는 명령과 작업 폴더를 찾아 `lesson.sh`로 만든다 (`{영상 파일 이름}` 같은 템플릿 줄은 건너뛰고 슬라이드의 구체적 예시를 사용).
2. GUI로만 하는 단계(COLMAP, CloudCompare 화면 조작)는 슬라이드 범위와 함께 "자동 리허설 불가"로 따로 표시한다.
3. 영상 실습용 학생 프로필로 리허설한다.

| 프로필 | 재현 방법 | 실제 수업(3D 복원 실습)에서 잡은 문제 |
|---|---|---|
| 선생님 PC | ffmpeg 설치됨, 1080p 영상 `input.mp4` | 기준 결과 (jpg 100장, 1920x1080) |
| ffmpeg 없는 학교 PC | ffmpeg 패키지 제거 | 슬라이드 괄호 속 설치 안내를 놓치면 `command not found` |
| 4K로 촬영한 학생 | 4K 영상 | **에러 없이** 3840x2160 사진 100장 생성. 다음 단계 COLMAP dense stereo에서 GPU 메모리 초과 위험 |
| 아이폰으로 찍은 학생 | 파일명 `IMG_0412.MOV` | 슬라이드의 `input.mp4`가 없어 실패 |

## 혁신 포인트 (Innovation)

1. **PC 한 대가 아닌 반 전체**: 학생 프로필마다 독립된 Daytona 샌드박스(이미지, 패키지, 실행 위치가 다름)를 몇 초 만에 병렬로 실행
2. **조용히 틀린 답까지**: 크래시만 보는 CI와 달리, 모든 학생 출력을 선생님 출력과 비교
3. **프라이빗 AI + 검증 키트**: 오픈소스 LLM을 Nosana GPU에 직접 띄워 학생 코드가 유료 외부 API로 나가지 않음. 결과는 패치가 아니라 재실행으로 검증된 키트

## 스폰서 활용 (Sponsor usage)

- **Daytona**: 학생 PC 역할. 프로필마다 독립된 샌드박스를 병렬 생성, 파일 업로드, 설치·실행, 종료 후 삭제. 생성 실패 시 1회 재시도하고, 인프라 오류는 코드 문제와 구분해 표시 (`dryrun/runner.py`)
- **Nosana**: 진단 두뇌. Deployments API로 RTX 4090 마켓에 vLLM + Qwen3-14B-AWQ를 배포하고 OpenAI 호환 API로 호출 (`core/nosana.py`, `core/llm.py`, `dryrun/fixer.py`)

## 구조

| 파일 | 역할 |
|---|---|
| `dryrun/profiles.py` | 학생 프로필 정의 (Python 실습용, 영상·터미널 실습용) |
| `dryrun/slides.py` | PDF/PPTX에서 학생 실행 단계(lesson.sh)와 GUI 단계 추출 |
| `dryrun/runner.py` | 프로필별 Daytona 샌드박스 병렬 실행 |
| `dryrun/fixer.py` | 판정(선생님 출력 기준), LLM 진단·수정, 규칙 기반 대체 |
| `dryrun/engine.py` | 실행 → 판정 → 수정 → 재실행 루프, 리포트 |
| `dryrun/__main__.py` | CLI (`python -m dryrun`) |
| `app/main.py`, `app/index.html` | 웹 화면 (FastAPI) |
| `core/sandbox.py` | Daytona 클라이언트 |
| `core/nosana.py`, `core/llm.py` | Nosana LLM 배포·호출 |
| `examples/lesson1/` | 함정 3개를 심은 데모 실습 |
| `examples/recon3d/` | 영상 실습용 샘플 영상 (1080p, 4K, 각 18초) |

## 실행 방법

### 1. 설치

```bash
git clone https://github.com/kky0824/daytona_hacksprint.git
cd daytona_hacksprint
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. API 키 설정

```bash
export DAYTONA_API_KEY=<Daytona 대시보드 → API Keys>
export NOSANA_API_KEY=<Nosana 대시보드 → Developers → API Keys>
```

Windows PowerShell은 `$env:DAYTONA_API_KEY="..."` 형식으로 설정합니다.

### 3. LLM 준비 (Nosana)

```bash
python -m core.nosana status    # 이미 배포했다면: RUNNING과 엔드포인트 확인
python -m core.nosana deploy    # 없다면 새로 배포 (RTX 4090, 약 $0.36/시간, 기동 약 10분)
```

`status`를 실행하면 LLM 주소가 `nosana_deployment.json`에 저장되고 자동으로 사용됩니다. 직접 지정하려면 `export LLM_BASE_URL=https://<엔드포인트>.node.k8s.prd.nos.ci` 를 설정하세요. LLM이 없어도 규칙 기반 수정으로 데모는 동작합니다.

### 4. 연결 확인

```bash
python scripts/smoke_test.py    # Daytona, Nosana, LLM 모두 [OK]인지 확인
```

### 5-a. 웹 화면으로 실행 (데모용)

```bash
uvicorn app.main:app --port 8000
```

브라우저에서 http://localhost:8000 → **리허설 시작**. 데모 실습이 미리 채워져 있습니다.
수업 자료로 하려면 **수업 자료로 시작하기**에서 PDF/PPTX를 고른 뒤 **리허설 시작**을 누르세요.

### 5-b. CLI로 실행

```bash
python -m dryrun examples/lesson1 dryrun_kit
```

결과 키트는 `dryrun_kit/`(lesson.py, requirements.txt, REPORT.md)에 저장됩니다.

### 끝나면

```bash
python -m core.nosana stop      # GPU 과금 중지
```

## 로드맵

- 사양 리허설: 저사양(RAM 1GB) 샌드박스로 메모리 부족 재현
- 입력 리허설: 4K 사진, HEIC, 세로 영상 같은 학생 입력 자동 생성
- 설치 안내문 검증: AI가 초보 학생처럼 안내문을 한 줄씩 따라 하며 빠진 단계 찾기
- GPU 실습 리허설: COLMAP 같은 무거운 실습을 GPU 샌드박스나 Nosana에서
- 학기 중 자동 재검증: 라이브러리 업데이트 시 기존 자료가 깨지는지 주기 점검
