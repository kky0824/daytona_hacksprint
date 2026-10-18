"""Judge each student run against the teacher's, then diagnose and fix what broke."""
import json
import re

from core import llm
from dryrun.runner import ENTRYPOINT, RunResult

PASS, FAIL, WRONG, WARN, ERROR = "pass", "fail", "wrong", "warn", "error"


def judge(result: RunResult, teacher: RunResult) -> str:
    if result.error:
        return ERROR  # the sandbox itself failed, not the lab
    if result.exit_code != 0:
        return FAIL
    if result.stdout.strip() != teacher.stdout.strip():
        return WRONG
    # Only warnings the teacher doesn't see count: the teacher's own warnings are the baseline.
    new = set(re.findall(r"\w+(?:Warning|Error)", result.stderr)) - set(re.findall(r"\w+(?:Warning|Error)", teacher.stderr))
    if new:
        return WARN
    return PASS


def _imports(code: str) -> list[str]:
    return sorted({m.group(1) for m in re.finditer(r"^\s*(?:import|from)\s+([A-Za-z_]\w*)", code, re.M)})


def rule_fix(files, results, verdicts, versions):
    """Deterministic fallback when the LLM is unavailable or its answer can't be used."""
    code = files[ENTRYPOINT]
    reqs = [l.strip() for l in files.get("requirements.txt", "").splitlines() if l.strip()]
    causes = {}
    for pid, verdict in verdicts.items():
        err = results[pid].stderr
        if verdict == FAIL and (m := re.search(r"No module named '([\w.]+)'", err)):
            mod = m.group(1).split(".")[0]
            causes[pid] = f"requirements.txt에 {mod}가 빠져 있어 새 PC에서 import가 실패했습니다."
            if not any(r.split("=")[0].lower() == mod.lower() for r in reqs):
                reqs.append(mod)
        elif verdict == FAIL and "FileNotFoundError" in err:
            causes[pid] = "데이터 파일을 '현재 폴더' 기준으로 찾아서, 다른 폴더에서 실행하면 실패합니다. 스크립트 위치 기준 경로로 바꿨습니다."
            code = re.sub(r"""(pd\.read_csv\()(["'])([^"']+)\2""", r"\1Path(__file__).parent / \2\3\2", code)
            code = re.sub(r"""(plt\.savefig\()(["'])([^"']+)\2""", r"\1Path(__file__).parent / \2\3\2", code)
            if "from pathlib import Path" not in code:
                code = "from pathlib import Path\n" + code
        elif verdict in (WRONG, WARN):
            causes[pid] = "에러 없이 결과가 다릅니다. 최신 버전의 라이브러리가 설치되어 동작이 바뀐 것으로, 선생님 PC와 같은 버전으로 고정했습니다."
    # Pin every requirement to the teacher's version so every student gets the same behavior.
    pinned = []
    for r in reqs:
        name = re.split(r"[=<>~!]", r)[0].strip()
        pinned.append(f"{name}=={versions[name.lower()]}" if name.lower() in versions else r)
    return {"lesson.py": code, "requirements.txt": "\n".join(pinned) + "\n", "causes": causes, "by": "rules"}


PROMPT = """You are Dry Run, a tool that rehearses a coding lab on several student machines before class.
The teacher's machine is the reference. Fix the lab so it produces the teacher's output on EVERY student machine.

Teacher's installed versions of the packages the lab imports: {versions}

lesson.py:
```python
{code}
```

requirements.txt:
```
{reqs}
```

Teacher output (stdout):
```
{teacher_out}
```

Student machines that did not match:
{failures}

Rules:
- Keep the lesson's intent and output the same as the teacher's.
- Pin every package in requirements.txt to the teacher's version (name==version) and add any missing ones.
- Make file paths work no matter which folder the script is run from (use pathlib and __file__).
- Prefer code that works on both old and new library versions (e.g. use df.loc instead of chained assignment).
- Do not add try/except or other code that hides errors; make the minimal change.

Reply with ONLY a JSON object, no markdown:
{{"causes": {{"<machine id>": "<one sentence in Korean explaining the root cause and the fix>"}},
  "lesson.py": "<full fixed file>",
  "requirements.txt": "<full fixed file>"}}"""


def llm_fix(files, results, verdicts, teacher, versions, profiles):
    code = files[ENTRYPOINT]
    used = {m.lower() for m in _imports(code)}
    used_versions = {k: v for k, v in versions.items() if k in used or k in files.get("requirements.txt", "").lower()}
    failures = "\n".join(
        f"- id={pid} ({profiles[pid].description}) verdict={v} exit={results[pid].exit_code}\n"
        f"  stdout: {results[pid].stdout.strip()[:300]!r}\n  stderr: {results[pid].stderr.strip()[-800:]!r}"
        for pid, v in verdicts.items()
    )
    msg = PROMPT.format(versions=json.dumps(used_versions), code=code, reqs=files.get("requirements.txt", ""),
                        teacher_out=teacher.stdout.strip()[:500], failures=failures)
    raw = llm.chat([{"role": "user", "content": msg}], temperature=0.1, max_tokens=2500)
    data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    if ENTRYPOINT not in data or "requirements.txt" not in data:
        raise ValueError("LLM reply is missing files")
    data["by"] = "llm"
    return data


def fix(files, results, verdicts, teacher, versions, profiles):
    """Ask the LLM first; fall back to rules if it fails."""
    try:
        return llm_fix(files, results, verdicts, teacher, versions, profiles)
    except Exception as e:
        out = rule_fix(files, results, verdicts, versions)
        out["llm_error"] = str(e)[:200]
        return out
