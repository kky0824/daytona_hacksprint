"""Deploy and manage an LLM on Nosana.

Usage:
    python -m core.nosana validate   # check the job definition (free)
    python -m core.nosana deploy     # create + start the LLM deployment (spends credits)
    python -m core.nosana status     # show status and save the LLM URL
    python -m core.nosana stop       # stop the deployment
"""
import json
import os
import sys
from pathlib import Path

import requests

API = "https://dashboard.k8s.prd.nos.ci/api"
STATE = Path(__file__).resolve().parent.parent / "nosana_deployment.json"

MODEL_ID = os.environ.get("NOSANA_MODEL_ID", "Qwen/Qwen2.5-7B-Instruct")
SERVED_NAME = os.environ.get("LLM_MODEL", "qwen2.5-7b")
MARKET = os.environ.get("NOSANA_MARKET", "97G9NnvBDQ2WpKu6fasoMsAKmfj63C9rhysJnkeWodAf")  # NVIDIA 4090 (premium)

JOB_DEFINITION = {
    "version": "0.1",
    "type": "container",
    "meta": {"trigger": "api"},
    "ops": [
        {
            "type": "container/run",
            "id": "llm",
            "args": {
                "image": "docker.io/vllm/vllm-openai:v0.8.5",
                "cmd": [
                    "--model", MODEL_ID,
                    "--served-model-name", SERVED_NAME,
                    "--port", "8000",
                    "--max-model-len", "16384",
                    "--gpu-memory-utilization", "0.9",
                ],
                "gpu": True,
                "expose": 8000,
            },
        }
    ],
}


def _headers():
    # In the cloud session the proxy injects the key; locally, read it from the environment.
    key = os.environ.get("NOSANA_API_KEY")
    return {"Authorization": f"Bearer {key}"} if key else {}


def _call(method, path, **kwargs):
    r = requests.request(method, API + path, headers=_headers(), timeout=30, **kwargs)
    if not r.ok:
        raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:500]}")
    return r.json() if r.content else {}


def balance():
    return _call("GET", "/credits/balance")


def validate():
    return _call("POST", "/deployments/validate", json={"job_definition": JOB_DEFINITION})


def deploy(timeout_minutes=240):
    body = {
        "name": f"hacksprint-{SERVED_NAME}",
        "market": MARKET,
        "replicas": 1,
        "timeout": timeout_minutes,
        "strategy": "SIMPLE",
        "autostart": True,
        "job_definition": JOB_DEFINITION,
    }
    dep = _call("POST", "/deployments/create", json=body)
    STATE.write_text(json.dumps({"id": dep["id"]}, indent=2))
    return dep


def status():
    dep_id = json.loads(STATE.read_text())["id"]
    dep = _call("GET", f"/deployments/{dep_id}")
    endpoints = dep.get("endpoints") or []
    state = {"id": dep_id, "status": dep.get("status"), "endpoints": endpoints}
    if endpoints:
        state["llm_base_url"] = endpoints[0]["url"]
    STATE.write_text(json.dumps(state, indent=2))
    return state


def stop():
    dep_id = json.loads(STATE.read_text())["id"]
    return _call("POST", f"/deployments/{dep_id}/stop")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    fn = {"balance": balance, "validate": validate, "deploy": deploy, "status": status, "stop": stop}[cmd]
    print(json.dumps(fn(), indent=2, ensure_ascii=False))
