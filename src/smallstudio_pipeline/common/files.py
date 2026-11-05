"""Writing files safely on shared storage.

write_atomic() writes through a temp file in the same folder and renames it into place,
so another machine never reads half a file. replace_with_retry() retries that rename,
which Windows refuses while another process is reading the file. Metadata, publish
records, in-use markers and hero files are all written this way.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

log = logging.getLogger(__name__)


def write_atomic(path: Path, text: str) -> None:
    """Write text to path through a temp file, so nobody ever reads half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Same folder as the target, so the rename stays on one filesystem and is atomic.
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text(text, encoding="utf-8")
    replace_with_retry(temp, path)


def replace_with_retry(source: Path, target: Path, attempts: int = 10, delay: float = 0.5) -> None:
    """Move source over target, retrying: Windows refuses while another process reads target."""
    for attempt in range(1, attempts + 1):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == attempts:
                raise
            log.warning("Couldn't replace %s (attempt %d), retrying", target, attempt)
            time.sleep(delay)
