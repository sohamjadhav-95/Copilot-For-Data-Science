"""
Browser Automation Agent — Entry Point.

Launch with:  python main.py
              python main.py --headed
              python main.py --port 9000
"""

import sys


import argparse
from pathlib import Path

import uvicorn
from loguru import logger

from config import settings


def setup_logging() -> None:
    """Configure loguru for file + console output."""
    logger.remove()  # remove default stderr handler

    # Console: colorful, concise
    logger.add(
        sys.stderr,
        level=settings.LOG_LEVEL,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # File: detailed, with rotation
    log_path = Path(settings.LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(log_path),
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} — {message}",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
    )


def main() -> None:
    """Parse CLI args and launch the FastAPI server."""
    parser = argparse.ArgumentParser(description="Browser Automation Agent")
    parser.add_argument(
        "--port", type=int, default=settings.PORT, help="Server port"
    )
    parser.add_argument(
        "--host", type=str, default=settings.HOST, help="Server host"
    )
    parser.add_argument(
        "--headed", action="store_true", help="Run browser in headed mode"
    )
    parser.add_argument(
        "--reload", action="store_true", help="Auto-reload on code changes"
    )
    args = parser.parse_args()

    if args.headed:
        settings.HEADLESS = False

    setup_logging()

    logger.info(
        f"🚀 Browser Automation Agent starting on http://{args.host}:{args.port}"
    )
    logger.info(f"   Headless: {settings.HEADLESS}")
    logger.info(f"   Default target: {settings.DEFAULT_TARGET} (GPT + Claude available)")
    logger.info(f"   Max concurrent sessions: {settings.MAX_CONCURRENT_SESSIONS}")


    uvicorn.run(
        "app.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
