# daytona_hacksprint

Daytona HackSprint Seoul (2026-10-18) 프로젝트.

> 아이디어 확정 후 이 섹션에 문제 정의 / 해결 방법 / 데모 방법을 채운다.

## 아키텍처

- **Nosana**: GPU 마켓(RTX 4090)에 vLLM으로 오픈소스 LLM(Qwen3-14B-AWQ)을 띄워 OpenAI 호환 API로 사용
- **Daytona**: LLM이 생성한 코드를 격리된 샌드박스에서 실행

## 구조

| 파일 | 역할 |
|---|---|
| `core/sandbox.py` | Daytona 클라이언트, `sandbox()` 컨텍스트 매니저, `run_python()` |
| `core/llm.py` | Nosana에 띄운 LLM 호출 (`chat()`) |
| `core/nosana.py` | Nosana LLM 배포 관리 CLI (`validate` / `deploy` / `status` / `stop` / `balance`) |
| `scripts/smoke_test.py` | Daytona, Nosana, LLM 연결 확인 |

## 실행

```bash
pip install -r requirements.txt
cp .env.example .env   # 로컬 실행 시에만: API 키 입력
python -m core.nosana deploy   # LLM 배포 (크레딧 사용)
python -m core.nosana status   # RUNNING + 엔드포인트 확인
python scripts/smoke_test.py
```
