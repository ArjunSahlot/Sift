from __future__ import annotations

import logging

from app.db.init import init_db
from app.utils.cleanup import run_cleanup
from app.utils.files import ensure_data_dirs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def main() -> None:
    ensure_data_dirs()
    init_db()
    run_cleanup()
    print("Cleanup complete.")


if __name__ == "__main__":
    main()
