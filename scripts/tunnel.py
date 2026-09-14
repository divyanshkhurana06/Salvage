"""Open a public tunnel to the local Salvage server so ElevenLabs can call its tools.

    .venv/bin/python scripts/tunnel.py [port]

Prints the public URL, writes it to data/public_url.txt, and keeps running until Ctrl+C.
The URL changes every time the tunnel restarts, so scripts/setup_voice.py reads this file
and updates the agent's tool URLs.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from salvage.config import DATA_DIR, settings  # noqa: E402


def main() -> None:
    from pyngrok import conf, ngrok

    token = os.getenv("NGROK_AUTHTOKEN", "")
    if not token:
        raise SystemExit("NGROK_AUTHTOKEN is not set in .env")
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    conf.get_default().auth_token = token
    tunnel = ngrok.connect(port, "http")
    url = tunnel.public_url
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "public_url.txt").write_text(url)
    print(f"public url: {url}  ->  http://127.0.0.1:{port}")
    print("written to data/public_url.txt; leave this running")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        ngrok.kill()


if __name__ == "__main__":
    main()
