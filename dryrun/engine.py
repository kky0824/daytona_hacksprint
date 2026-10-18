"""Rehearsal loop: run on every profile, judge, fix, rerun until everything passes."""
import time
from concurrent.futures import ThreadPoolExecutor

from dryrun.fixer import ERROR, PASS, fix, judge, rule_fix
from dryrun.profiles import PROFILES
from dryrun.runner import run_all, package_versions

MAX_ROUNDS = 3


def rehearse(files: dict[str, str], emit=lambda event: None):
    """Run the rehearsal and report progress through `emit(dict)`. Returns the final state."""
    profiles = {p.id: p for p in PROFILES}
    started = time.time()
    state = {"rounds": [], "files": dict(files), "done": False}
    with ThreadPoolExecutor(1) as pool:
        versions_future = pool.submit(package_versions, files)
        current = dict(files)
        asked_llm = False
        for n in range(1, MAX_ROUNDS + 1):
            emit({"type": "round", "round": n})
            results = run_all(PROFILES, current, on_status=lambda pid, s: emit({"type": "status", "round": n, "profile": pid, "status": s}))
            teacher = results["teacher"]
            verdicts = {pid: judge(r, teacher) for pid, r in results.items() if pid != "teacher"}
            rnd = {"round": n, "results": {pid: vars(r) for pid, r in results.items()}, "verdicts": verdicts}
            state["rounds"].append(rnd)
            emit({"type": "results", **rnd})
            broken = {pid: v for pid, v in verdicts.items() if v != PASS}
            if not broken:
                state["files"], state["done"] = current, True
                break
            if n == MAX_ROUNDS:
                break
            broken = {pid: v for pid, v in broken.items() if v != ERROR}
            if not broken:
                continue  # only infrastructure errors: rerun the same files
            emit({"type": "fixing", "round": n})
            versions = versions_future.result()
            # The first fix asks the LLM; if failures remain, the next one adds the rule-based fixes on top.
            if not asked_llm:
                asked_llm = True
                patch = fix(current, results, broken, teacher, versions, profiles)
            else:
                patch = rule_fix(current, results, broken, versions)
            current = {**current, "lesson.py": patch["lesson.py"], "requirements.txt": patch["requirements.txt"]}
            rnd["fix"] = patch
            emit({"type": "fix", "round": n, "by": patch["by"], "causes": patch.get("causes", {}),
                  "files": {k: current[k] for k in ("lesson.py", "requirements.txt")}, "llm_error": patch.get("llm_error")})
    state["files"] = current
    state["seconds"] = round(time.time() - started, 1)
    state["report"] = report(state, files)
    emit({"type": "done", "done": state["done"], "seconds": state["seconds"], "report": state["report"],
          "files": {k: current[k] for k in ("lesson.py", "requirements.txt")}})
    return state


def report(state, original):
    profiles = {p.id: p for p in PROFILES}
    first, last = state["rounds"][0], state["rounds"][-1]
    label = {"pass": "통과", "fail": "실패", "wrong": "답이 다름", "warn": "경고", "error": "인프라 오류"}
    ok = sum(v == "pass" for v in last["verdicts"].values())
    lines = [
        "# Dry Run 리허설 리포트", "",
        f"- 학생 환경 {len(last['verdicts'])}개 중 **{ok}개 통과** (최종), 리허설 {len(state['rounds'])}회, {state.get('seconds', 0)}초", "",
        "## 1차 실행 결과", "", "| 환경 | 결과 | 원인과 수정 |", "|---|---|---|",
    ]
    causes = (first.get("fix") or {}).get("causes", {})
    for pid, v in first["verdicts"].items():
        lines.append(f"| {profiles[pid].name} | {label[v]} | {causes.get(pid, '-')} |")
    lines += ["", "## 최종 실행 결과", "", "| 환경 | 결과 |", "|---|---|"]
    lines += [f"| {profiles[pid].name} | {label[v]} |" for pid, v in last["verdicts"].items()]
    lines += ["", "## 검증된 requirements.txt", "", "```", state["files"]["requirements.txt"].strip(), "```"]
    return "\n".join(lines) + "\n"
