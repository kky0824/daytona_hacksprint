"""CLI: python -m dryrun [lab folder] [output folder]"""
import json
import sys
from pathlib import Path

from dryrun.engine import rehearse

ICON = {"pass": "🟢 통과", "fail": "🔴 실패", "wrong": "🟠 답이 다름", "warn": "🟡 경고", "error": "⚪ 인프라 오류"}


def main():
    lab = Path(sys.argv[1] if len(sys.argv) > 1 else "examples/lesson1")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "dryrun_kit")
    files = {p.name: p.read_text() for p in lab.iterdir() if p.is_file() and p.suffix in (".py", ".txt", ".csv", ".md")}

    def emit(e):
        if e["type"] == "round":
            print(f"\n=== 리허설 {e['round']}회차: 선생님 + 학생 PC 동시 실행 ===")
        elif e["type"] == "results":
            for pid, v in e["verdicts"].items():
                r = e["results"][pid]
                detail = (r["stderr"].strip().splitlines() or [r["error"] or ""])[-1][:100] if v != "pass" else r["stdout"].strip()[:60]
                print(f"  {pid:8s} {ICON[v]:12s} {detail}")
            print(f"  teacher  기준 출력: {e['results']['teacher']['stdout'].strip()[:60]}")
        elif e["type"] == "fix":
            print(f"\n--- 진단·수정 ({'Nosana LLM' if e['by'] == 'llm' else '규칙 기반'}) ---")
            for pid, c in e["causes"].items():
                print(f"  {pid}: {c}")
            if e.get("llm_error"):
                print(f"  (LLM 사용 실패, 규칙으로 대체: {e['llm_error']})")
        elif e["type"] == "done":
            print(f"\n{'✅ 모든 학생 PC 통과' if e['done'] else '⚠️ 일부 실패'} ({e['seconds']}초)")

    state = rehearse(files, emit)
    out.mkdir(exist_ok=True)
    for name, content in state["files"].items():
        (out / name).write_text(content)
    (out / "REPORT.md").write_text(state["report"])
    (out / "rehearsal.json").write_text(json.dumps(state, ensure_ascii=False, indent=2, default=str))
    print(f"검증 키트: {out}/ (lesson.py, requirements.txt, REPORT.md)")


if __name__ == "__main__":
    main()
