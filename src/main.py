
import sys
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

LOG_DIR.mkdir(exist_ok=True)

def log(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def run():
    log("Car project started")
    log(f"Base directory: {BASE_DIR}")
    log(f"Data directory exists: {DATA_DIR.exists()}")
    log("Running initial checks...")
    log("Car project finished successfully")

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        log("Execution interrupted by user")
        sys.exit(1)
    except Exception as e:
        log(f"Error occurred: {e}")
        sys.exit(1)