"""ARES API server entry point — run with: python main.py"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "ares.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
