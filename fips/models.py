from dataclasses import dataclass
from typing import List


@dataclass
class StatusOptions:
    active: bool = False  # Действует
    may_terminate: bool = False  # Может прекратить свое действие
    terminated_recoverable: bool = (
        False  # Прекратил действие, но может быть восстановлен
    )
    terminated: bool = False  # Прекратил действие


@dataclass
class PatentHeader:
    """Single patent header at top right corner."""

    doc_url: str
    country_code: str
    number: str
    kind_code: str
    ipc_codes: List[str]  # List of IPC codes with dates


@dataclass
class PatentResult:
    """Single patent search result."""

    number: str
    publication_date: str
    title: str
    document_type: str
    link_id: str
    image_url: str | None = None
