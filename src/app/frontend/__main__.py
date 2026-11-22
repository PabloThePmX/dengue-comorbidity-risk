"""`python -m app.frontend`: sobe o Streamlit só em 127.0.0.1 e sem telemetria."""

import sys
from pathlib import Path

CAMINHO_APP = Path(__file__).resolve().parent / "app.py"
ARGS = [
    "streamlit",
    "run",
    str(CAMINHO_APP),
    "--server.address",
    "127.0.0.1",
    "--browser.gatherUsageStats",
    "false",
]

if __name__ == "__main__":
    from streamlit.web import cli

    sys.argv = ARGS
    cli.main()
