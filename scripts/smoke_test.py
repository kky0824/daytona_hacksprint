"""Check that Daytona, Nosana and (if deployed) the LLM are all reachable."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import llm, nosana
from core.sandbox import run_python, sandbox


def check(name, fn):
    t = time.time()
    try:
        print(f"[OK]   {name}: {fn()} ({time.time() - t:.1f}s)")
    except Exception as e:
        print(f"[FAIL] {name}: {e}")


def daytona_roundtrip():
    with sandbox() as sb:
        code, out = run_python(sb, "import pandas, matplotlib; print(pandas.__version__)")
        return f"sandbox {sb.id} ran code (exit {code}, pandas {out.strip()})"


check("Daytona sandbox", daytona_roundtrip)
check("Nosana credits", nosana.balance)
check("LLM", lambda: llm.chat([{"role": "user", "content": "Reply with just: pong"}], max_tokens=5))
