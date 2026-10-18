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


# --- Terminal labs (lesson.sh extracted from slides) ---

def rule_fix_shell(files, results, verdicts, teacher):
    script = files["lesson.sh"]
    lines = script.splitlines()
    after_cd = next((i + 1 for i, l in enumerate(lines) if l.startswith("cd ")), 1)
    inserts, causes = [], {}
    for pid, verdict in verdicts.items():
        err = results[pid].stderr
        if verdict == FAIL and (m := re.search(r"(\w[\w.-]*): command not found", err)):
            tool = m.group(1)
            causes[pid] = f"이 PC에는 {tool}이(가) 없어 명령이 실패했습니다. 슬라이드의 괄호 속 설치 안내를 학생이 놓친 경우입니다. 없으면 자동 설치하는 줄을 추가했습니다."
            inserts.append(f"command -v {tool} >/dev/null || (sudo apt-get update -qq && sudo apt-get install -y -qq {tool})")
        elif verdict == FAIL and "No such file" in err:
            causes[pid] = "영상 파일 이름이 슬라이드의 input.mp4와 다릅니다 (예: 아이폰의 IMG_0412.MOV). 폴더 안의 영상을 확장자와 대소문자에 상관없이 찾도록 바꿨습니다."
            inserts.append('VIDEO=$(ls *.mp4 *.MP4 *.mov *.MOV 2>/dev/null | head -1)')
            lines = [re.sub(r"-i\s+(\"[^\"]*\"|\S+)", '-i "$VIDEO"', l) if l.lstrip().startswith("ffmpeg") else l for l in lines]
        elif verdict in (WRONG, WARN):
            size = re.search(r"(\d+)x(\d+)", teacher.stdout)
            if size and "scale=" not in "\n".join(lines):
                h = size.group(2)
                causes[pid] = (f"에러는 없지만 사진 해상도가 선생님과 다릅니다 ({results[pid].stdout.strip().splitlines()[-1]}). "
                               f"4K 사진은 다음 단계인 COLMAP dense stereo에서 GPU 메모리를 크게 늘려 튕길 수 있어, 세로 {h}px 이하로 줄이도록 했습니다.")
                lines = [re.sub(r'-vf "([^"]+)"', rf'-vf "\1,scale=-2:\'min({h},ih)\'"', l) if l.startswith("ffmpeg") else l for l in lines]
    for cmd in reversed(dict.fromkeys(inserts)):
        lines.insert(after_cd, cmd)
    return {"lesson.sh": "\n".join(lines) + "\n", "causes": causes, "by": "rules"}


SHELL_PROMPT = """You are Dry Run. A teacher's terminal lab (extracted from class slides) is rehearsed on several student PCs.
The teacher's PC is the reference. Fix lesson.sh so EVERY student PC produces the teacher's result.

lesson.sh:
```bash
{script}
```

Teacher result summary:
```
{teacher_out}
```

Student PCs that did not match:
{failures}

Rules:
- Make the minimal changes; keep `set -e` and the `cd` line.
- If a tool is missing, install it only when missing: `command -v X >/dev/null || (sudo apt-get update -qq && sudo apt-get install -y -qq X)`.
- If a student's input file has another name, find it in the folder instead of hard-coding the name. Student videos can be
  .mp4 or .mov in any letter case (iPhone: IMG_0412.MOV), e.g. VIDEO=$(ls *.mp4 *.MP4 *.mov *.MOV 2>/dev/null | head -1).
- If outputs differ from the teacher's (e.g. image resolution), make them match the teacher's (e.g. an ffmpeg scale filter).
Reply with ONLY a JSON object:
{{"causes": {{"<pc id>": "<one Korean sentence: root cause and the fix>"}}, "lesson.sh": "<full fixed script>"}}"""


def llm_fix_shell(files, results, verdicts, teacher, profiles):
    failures = "\n".join(
        f"- id={pid} ({profiles[pid].description}) verdict={v} exit={results[pid].exit_code}\n"
        f"  result summary: {results[pid].stdout.strip()!r}\n  stderr tail: {results[pid].stderr.strip()[-600:]!r}"
        for pid, v in verdicts.items()
    )
    msg = SHELL_PROMPT.format(script=files["lesson.sh"], teacher_out=teacher.stdout.strip(), failures=failures)
    raw = llm.chat([{"role": "user", "content": msg}], temperature=0.1, max_tokens=1500)
    data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    if "lesson.sh" not in data:
        raise ValueError("LLM reply is missing lesson.sh")
    data["by"] = "llm"
    return data
