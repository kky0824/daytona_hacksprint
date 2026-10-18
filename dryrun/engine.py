"""Rehearsal loop: run on every profile, judge, fix, rerun until everything passes."""
import time
from concurrent.futures import ThreadPoolExecutor

from dryrun.fixer import ERROR, PASS, fix, judge, llm_fix_shell, rule_fix, rule_fix_shell
from dryrun.profiles import profiles_for
from dryrun.runner import run_all, package_versions

MAX_ROUNDS = 3


def rehearse(files: dict[str, str], emit=lambda event: None):
    """Run the rehearsal and report progress through `emit(dict)`. Returns the final state."""
    plist = profiles_for(files)
    profiles = {p.id: p for p in plist}
    shell = "lesson.sh" in files
    edited = ("lesson.sh",) if shell else ("lesson.py", "requirements.txt")
    emit({"type": "profiles", "profiles": [{"id": p.id, "name": p.name, "description": p.description} for p in plist]})
    started = time.time()
    state = {"rounds": [], "files": dict(files), "done": False}
    with ThreadPoolExecutor(1) as pool:
        versions_future = pool.submit(package_versions, files) if not shell else None
        current = dict(files)
        asked_llm = False
        for n in range(1, MAX_ROUNDS + 1):
            emit({"type": "round", "round": n})
            results = run_all(plist, current, on_status=lambda pid, s: emit({"type": "status", "round": n, "profile": pid, "status": s}))
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
            # The first fix asks the LLM; if failures remain, the next one adds the rule-based fixes on top.
            if shell:
                patch = None
                if not asked_llm:
                    asked_llm = True
                    try:
                        patch = llm_fix_shell(current, results, broken, teacher, profiles)
                    except Exception as e:
                        patch = {**rule_fix_shell(current, results, broken, teacher), "llm_error": str(e)[:200]}
                patch = patch or rule_fix_shell(current, results, broken, teacher)
            else:
                versions = versions_future.result()
                if not asked_llm:
                    asked_llm = True
                    patch = fix(current, results, broken, teacher, versions, profiles)
                else:
                    patch = rule_fix(current, results, broken, versions)
            current = {**current, **{k: patch[k] for k in edited}}
            rnd["fix"] = patch
            emit({"type": "fix", "round": n, "by": patch["by"], "causes": patch.get("causes", {}),
                  "files": {k: current[k] for k in edited}, "llm_error": patch.get("llm_error")})
    state["files"] = current
    state["seconds"] = round(time.time() - started, 1)
    state["report"] = report(state, profiles)
    emit({"type": "done", "done": state["done"], "seconds": state["seconds"], "report": state["report"],
          "files": {k: current[k] for k in edited}})
    return state


def report(state, profiles):
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
    final = "lesson.sh" if "lesson.sh" in state["files"] else "requirements.txt"
    lines += ["", f"## 검증된 {final}", "", "```", state["files"][final].strip(), "```"]
    return "\n".join(lines) + "\n"
