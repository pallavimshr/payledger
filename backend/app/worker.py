"""Retries webhook events that failed or were never processed.

  make retry          # run once
  make worker         # keep running, check every 10 seconds
"""
import sys
import time

from app.db import SessionLocal
from app.webhooks.inbox import process_pending


def run_once() -> None:
    with SessionLocal() as session:
        counts = process_pending(session)
    print(f"Retry pass done: {counts or 'nothing pending'}")


if __name__ == "__main__":
    if "--loop" in sys.argv:
        while True:
            run_once()
            time.sleep(10)
    else:
        run_once()
