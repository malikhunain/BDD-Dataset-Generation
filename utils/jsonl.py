import json
from pathlib import Path
from typing import Iterator, Dict, Any


def read_jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    """Yield non-empty JSONL records from a file."""
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)