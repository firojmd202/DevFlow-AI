"""Write the API contract without starting a server."""

import json
from pathlib import Path

from devflow_api.main import app


def main() -> None:
    target = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"
    target.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
