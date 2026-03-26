"""Generate and persist the OpenAPI schema for the FastAPI app.

This script is typically used in CI or during development to export the backend
OpenAPI spec to `interfaces/openapi.json`.

It imports the FastAPI app object from `api.main`.
"""

from __future__ import annotations

import json
import os

from api.main import app


def main() -> None:
    """Write the OpenAPI schema to `interfaces/openapi.json`."""
    openapi_schema = app.openapi()

    output_dir = "interfaces"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "openapi.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2)


if __name__ == "__main__":
    main()
