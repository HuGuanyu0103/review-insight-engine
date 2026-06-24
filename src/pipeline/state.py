"""Pipeline state manager — tracks execution progress for checkpoint/resume."""

import json
import logging
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PipelineState:
    """Memento tracking the execution status of each pipeline stage."""

    input_file: str = ""
    started_at: str = ""
    updated_at: str = ""

    parse_status: StageStatus = StageStatus.PENDING
    parse_count: int = 0

    filter_status: StageStatus = StageStatus.PENDING
    filter_kept: int = 0
    filter_dropped: int = 0

    map_status: StageStatus = StageStatus.PENDING
    map_batches: int = 0
    map_extracted: int = 0
    map_hitl: int = 0

    reduce_status: StageStatus = StageStatus.PENDING

    rag_status: StageStatus = StageStatus.PENDING
    rag_doc_count: int = 0

    report_status: StageStatus = StageStatus.PENDING

    def start(self, input_file: str):
        self.input_file = input_file
        self.started_at = datetime.now().isoformat()
        self.updated_at = self.started_at

    def touch(self):
        self.updated_at = datetime.now().isoformat()

    def save(self, path: str):
        """Persist state to JSON."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.touch()
        with open(p, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str) -> "PipelineState":
        """Load state from JSON."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        state = cls()
        for key, value in data.items():
            if key in ("parse_status", "filter_status", "map_status",
                       "reduce_status", "rag_status", "report_status"):
                value = StageStatus(value)
            if hasattr(state, key):
                setattr(state, key, value)
        return state
