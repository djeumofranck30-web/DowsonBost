#!/usr/bin/env python3
"""Run the DowsonBost REST API."""

from __future__ import annotations

import uvicorn

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=False)
