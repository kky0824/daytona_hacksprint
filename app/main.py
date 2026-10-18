"""Dry Run web app: uvicorn app.main:app --port 8000"""
import io
import threading
import uuid
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from dryrun.engine import rehearse
from dryrun.profiles import PROFILES
from dryrun.slides import extract_text, lesson_script, to_lab

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "lesson1"
app = FastAPI(title="Dry Run")
jobs: dict[str, dict] = {}


class Lab(BaseModel):
    files: dict[str, str]


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "index.html")


@app.get("/api/example")
def example():
    return {
        "files": {p.name: p.read_text() for p in sorted(EXAMPLE.iterdir()) if p.is_file()},
        "profiles": [{"id": p.id, "name": p.name, "description": p.description} for p in PROFILES],
    }


@app.post("/api/slides")
async def slides(file: UploadFile = File(...)):
    """Class slides (PDF / PPTX) -> the terminal steps a student would run, as lesson.sh."""
    pages = extract_text(file.filename or "", await file.read())
    lab = to_lab(pages)
    if not lab.get("script"):
        raise HTTPException(422, "슬라이드에서 실행할 명령을 찾지 못했습니다.")
    return {"pages": len(pages), "lab": lab, "files": {"lesson.sh": lesson_script(lab)}}


@app.post("/api/rehearse")
def start(lab: Lab):
    if "lesson.py" not in lab.files and "lesson.sh" not in lab.files:
        raise HTTPException(400, "lesson.py or lesson.sh is required")
    job_id = uuid.uuid4().hex[:8]
    job = jobs[job_id] = {"events": [], "state": None}

    def work():
        try:
            job["state"] = rehearse(lab.files, job["events"].append)
        except Exception as e:
            job["events"].append({"type": "error", "message": str(e)[:500]})

    threading.Thread(target=work, daemon=True).start()
    return {"job": job_id}


@app.get("/api/jobs/{job_id}")
def events(job_id: str, since: int = 0):
    job = jobs.get(job_id) or {}
    if not job:
        raise HTTPException(404)
    return {"events": job["events"][since:], "next": len(job["events"])}


@app.get("/api/jobs/{job_id}/kit.zip")
def kit(job_id: str):
    state = (jobs.get(job_id) or {}).get("state")
    if not state:
        raise HTTPException(404, "not finished")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, content in state["files"].items():
            z.writestr(f"dryrun-kit/{name}", content)
        z.writestr("dryrun-kit/REPORT.md", state["report"])
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": "attachment; filename=dryrun-kit.zip"})
