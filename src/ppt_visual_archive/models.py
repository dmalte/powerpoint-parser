"""Domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class DeckStatus(str, Enum):
    ACTIVE = "active"
    DELETED = "deleted"


class ChangeType(str, Enum):
    NEW = "new"
    CHANGED = "changed"
    UNCHANGED = "unchanged"
    DELETED = "deleted"


@dataclass
class ScanResult:
    """Result of scanning a single .pptx file on disk."""

    file_path: str
    file_name: str
    folder_path: str
    file_size: int
    modified_time: float  # unix timestamp
    file_signature: str  # "path|size|mtime"

    @staticmethod
    def compute_signature(file_path: str, file_size: int, modified_time: float) -> str:
        return f"{file_path}|{file_size}|{modified_time}"


@dataclass
class Deck:
    deck_id: str
    file_path: str
    file_name: str
    folder_path: str
    file_size: int
    modified_time: float
    processed_time: float = 0.0
    slide_count: int = 0
    file_signature: str = ""
    status: str = DeckStatus.ACTIVE.value


@dataclass
class Slide:
    slide_id: str
    deck_id: str
    slide_number: int
    title: str = ""
    subtitle_text: str = ""
    body_text: str = ""
    extra_text: str = ""
    extracted_text: str = ""
    notes_text: str = ""
    thumb_path: str = ""
    preview_path: str = ""
    width: int = 0
    height: int = 0


@dataclass
class ProcessingResult:
    """Result of processing a single deck."""

    deck: Deck
    slides: list[Slide] = field(default_factory=list)
    success: bool = True
    error: str = ""


@dataclass
class ChangeSet:
    """Classified results of comparing scan results to existing index."""

    new: list[ScanResult] = field(default_factory=list)
    changed: list[ScanResult] = field(default_factory=list)
    unchanged: list[ScanResult] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)  # deck_ids
