from dataclasses import dataclass
from pathlib import Path

@dataclass
class ParsedOutput:
    feature_content: str
    steps_content:   str
    feature_path:    Path
    steps_path:      Path
    solution_path:   Path

class ParseError(Exception):
    pass