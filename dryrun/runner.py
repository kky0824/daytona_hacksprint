"""Run a lab in one Daytona sandbox per student profile, in parallel."""
import shlex
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from daytona import CreateSandboxFromImageParams

from core.sandbox import client
from dryrun.profiles import Profile

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


def run_profile(profile: Profile, files: dict[str, str], on_status=None) -> RunResult:
    import time

    t = time.time()
    status = on_status or (lambda *_: None)
    params = CreateSandboxFromImageParams(image=profile.image) if profile.image else None
    status(profile.id, "starting")
    sb = client().create(params, timeout=180)
    try:
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
