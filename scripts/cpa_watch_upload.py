#!/usr/bin/env python3
"""Watch cpa_auths/ and upload new xai-*.json files to a remote CLIProxyAPI (CPA).

Usage:
  set CPA_BASE=http://127.0.0.1:8317
  set CPA_MANAGEMENT_KEY=your-management-password
  uv run python -u scripts/cpa_watch_upload.py

Optional:
  CPA_AUTH_DIR   default: ./cpa_auths
  CPA_STATE_FILE default: ./logs/cpa_uploaded.json
  CPA_POLL_SEC   default: 8
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time
from datetime import datetime


def env(name: str, default: str = "") -> str:
    return str(os.environ.get(name, default) or "").strip()


BASE = pathlib.Path(__file__).resolve().parents[1]
AUTH_DIR = pathlib.Path(env("CPA_AUTH_DIR") or (BASE / "cpa_auths")).expanduser()
STATE = pathlib.Path(env("CPA_STATE_FILE") or (BASE / "logs" / "cpa_uploaded.json")).expanduser()
CPA_BASE = env("CPA_BASE", "http://127.0.0.1:8317").rstrip("/")
KEY = env("CPA_MANAGEMENT_KEY") or env("CPA_MGMT_KEY")
POLL = float(env("CPA_POLL_SEC") or "8")
UPLOAD_URL = f"{CPA_BASE}/v0/management/auth-files"


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(st: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def file_key(p: pathlib.Path) -> str:
    h = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    return f"{p.name}:{p.stat().st_size}:{h}"


def upload(p: pathlib.Path) -> tuple[bool, str]:
    cmd = [
        "curl",
        "-sS",
        "-X",
        "POST",
        UPLOAD_URL,
        "-H",
        f"X-Management-Key: {KEY}",
        "-F",
        f"file=@{p};type=application/json;filename={p.name}",
        "--connect-timeout",
        "20",
        "--max-time",
        "60",
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, errors="replace")
        return True, out.strip()
    except subprocess.CalledProcessError as e:
        return False, (e.output or str(e)).strip()
    except FileNotFoundError:
        return False, "curl not found in PATH"


def main() -> int:
    if not KEY:
        print(
            "ERROR: set CPA_MANAGEMENT_KEY (CPA management password), e.g.\n"
            "  set CPA_BASE=http://127.0.0.1:8317\n"
            "  set CPA_MANAGEMENT_KEY=your-password\n"
            "  uv run python -u scripts/cpa_watch_upload.py",
            file=sys.stderr,
        )
        return 2

    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    st = load_state()
    print(f"[uploader] watch {AUTH_DIR}", flush=True)
    print(f"[uploader] target {UPLOAD_URL}", flush=True)

    while True:
        files = sorted(AUTH_DIR.glob("xai-*.json"))
        for p in files:
            k = file_key(p)
            if st.get(p.name) == k:
                continue
            ok, msg = upload(p)
            ts = datetime.now().strftime("%H:%M:%S")
            compact = msg.replace(" ", "")
            if ok and '"status":"ok"' in compact:
                st[p.name] = k
                save_state(st)
                print(f"[{ts}] + uploaded {p.name} -> {msg}", flush=True)
            else:
                print(f"[{ts}] ! upload fail {p.name}: {msg}", flush=True)

        if (BASE / "logs" / "STOP_UPLOADER").exists():
            print("[uploader] stop flag found, exit", flush=True)
            break
        time.sleep(max(2.0, POLL))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
