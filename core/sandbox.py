"""Daytona sandbox helpers."""
import os
from contextlib import contextmanager

import daytona_api_client
from daytona import CreateSandboxFromSnapshotParams, Daytona, DaytonaConfig

# The generated API client ignores HTTPS_PROXY, so route it through the proxy explicitly.
# The toolbox client deep-copies this configuration, so it inherits the setting.
_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
if _proxy:
    _orig_init = daytona_api_client.Configuration.__init__

    def _init_with_proxy(self, *args, **kwargs):
        _orig_init(self, *args, **kwargs)
        self.proxy = _proxy
        self.ssl_ca_cert = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")

    daytona_api_client.Configuration.__init__ = _init_with_proxy

_client = None


def client() -> Daytona:
    global _client
    if _client is None:
        # In the cloud session the proxy injects the real key, so any placeholder works.
        _client = Daytona(DaytonaConfig(api_key=os.environ.get("DAYTONA_API_KEY") or "injected-by-proxy"))
    return _client


@contextmanager
def sandbox(**params):
    """Create a sandbox for the duration of the block, then delete it."""
    sb = client().create(CreateSandboxFromSnapshotParams(**params) if params else None)
    try:
        yield sb
    finally:
        client().delete(sb)


def run_python(sb, code: str, timeout: int = 60):
    """Run Python code in the sandbox. Returns (exit_code, output)."""
    r = sb.process.code_run(code, timeout=timeout)
    return r.exit_code, r.result
