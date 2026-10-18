"""Run a lab in one Daytona sandbox per student profile, in parallel."""
import re
import shlex
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from daytona import CreateSandboxFromImageParams

from core.sandbox import client
from dryrun.profiles import Profile

ROOT = Path(__file__).resolve().parent.parent

# Summarize what a terminal lab produced, so student results can be compared with the teacher's.
CHECK = r"""python3 - <<'PY'
import collections, glob, os
from PIL import Image
inputs = set(os.environ.get("DRYRUN_INPUTS", "").split(","))
made = sorted(f for f in os.listdir(".") if os.path.isfile(f) and f not in inputs and not f.startswith("."))
by_ext = collections.Counter(os.path.splitext(f)[1].lstrip(".").lower() for f in made)
print(", ".join(f"{e} {n}개" for e, n in sorted(by_ext.items())) or "생성된 파일 없음")
imgs = [f for f in made if f.lower().endswith((".jpg", ".jpeg", ".png"))]
if imgs:
    w, h = Image.open(imgs[0]).size
    print(f"이미지 해상도 {w}x{h}")
PY"""

LAB_DIR = "lab"
ENTRYPOINT = "lesson.py"


@dataclass
class RunResult:
    profile_id: str
    exit_code: int
    stdout: str
    stderr: str
    seconds: float
    error: str = ""  # infrastructure error (sandbox could not start, etc.)


def _sh(sb, cmd, cwd=None, timeout=300):
    r = sb.process.exec(f"bash -lc {shlex.quote(cmd)}", cwd=cwd, timeout=timeout)
    return r.exit_code, r.result


def _run_shell_lab(sb, profile, files, status):
    """Run lesson.sh (commands extracted from slides) the way the student would, in their work folder."""
    home = sb.get_user_home_dir()
    script = files["lesson.sh"]
    m = re.search(r"^cd\s+(\S+)", script, re.M)
    workdir = (m.group(1) if m else "~/lab").replace("~", home, 1)
    _sh(sb, f"mkdir -p {shlex.quote(workdir)} /tmp/dryrun")
    sb.fs.upload_file(script.encode(), "/tmp/dryrun/lesson.sh")
    for name, sample in profile.inputs.items():
        sb.fs.upload_file((ROOT / sample).read_bytes(), f"{workdir}/{name}")
    status(profile.id, "installing")
    for cmd in profile.setup:
        _sh(sb, cmd, cwd=home)
    status(profile.id, "running")
    _sh(sb, "bash /tmp/dryrun/lesson.sh > /tmp/out.txt 2> /tmp/err.txt; echo $? > /tmp/code.txt", cwd=home, timeout=600)
    code = int(_sh(sb, "cat /tmp/code.txt")[1].strip() or 1)
    err = _sh(sb, "tail -c 4000 /tmp/err.txt")[1]
    summary = _sh(sb, f"DRYRUN_INPUTS={shlex.quote(','.join(profile.inputs))} bash -c {shlex.quote(CHECK)}", cwd=workdir)[1]
    return code, summary, err


def run_profile(profile: Profile, files: dict[str, str], on_status=None) -> RunResult:
    import time

    t = time.time()
    status = on_status or (lambda *_: None)
    params = CreateSandboxFromImageParams(image=profile.image) if profile.image else None
    status(profile.id, "starting")
    sb = client().create(params, timeout=180)
    try:
        if "lesson.sh" in files:
            code, out, err = _run_shell_lab(sb, profile, files, status)
            return RunResult(profile.id, code, out, err, time.time() - t)
        home = sb.get_user_home_dir()
        lab = f"{home}/{LAB_DIR}"
        _sh(sb, f"mkdir -p {lab}")
        for name, content in files.items():
            sb.fs.upload_file(content.encode(), f"{lab}/{name}")
        status(profile.id, "installing")
        for cmd in profile.setup:
            _sh(sb, cmd, cwd=lab, timeout=600)
        status(profile.id, "running")
        cwd, target = (home, f"{LAB_DIR}/{ENTRYPOINT}") if profile.run_from_home else (lab, ENTRYPOINT)
        _sh(sb, f"{profile.python} {target} > /tmp/out.txt 2> /tmp/err.txt; echo $? > /tmp/code.txt", cwd=cwd, timeout=300)
        code = int(_sh(sb, "cat /tmp/code.txt")[1].strip() or 1)
        out = _sh(sb, "cat /tmp/out.txt")[1]
        err = _sh(sb, "cat /tmp/err.txt")[1]
        return RunResult(profile.id, code, out, err, time.time() - t)
    finally:
        client().delete(sb)


def package_versions(files: dict[str, str]) -> dict[str, str]:
    """Versions installed on the teacher's machine (default snapshot), used to pin requirements."""
    sb = client().create(timeout=120)
    try:
        out = sb.process.exec("pip freeze 2>/dev/null").result
    finally:
        client().delete(sb)
    versions = {}
    for line in out.splitlines():
        if "==" in line:
            name, ver = line.split("==", 1)
            versions[name.lower()] = ver.strip()
    return versions


def run_all(profiles: list[Profile], files: dict[str, str], on_status=None) -> dict[str, RunResult]:
    def safe(p):
        # Retry once: a busy Daytona region occasionally fails or times out a sandbox create.
        for attempt in range(2):
            try:
                return run_profile(p, files, on_status)
            except Exception as e:  # keep the other profiles going
                err = str(e)[:500]
                if on_status:
                    on_status(p.id, "retrying" if attempt == 0 else "error")
        return RunResult(p.id, -1, "", "", 0.0, error=err)

    with ThreadPoolExecutor(max_workers=len(profiles)) as pool:
        return {r.profile_id: r for r in pool.map(safe, profiles)}
