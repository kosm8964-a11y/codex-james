"""Configuration loading for the address translator."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional
import json


DEFAULT_CONFIG_PATH = Path("config.json")


@dataclass
class TranslatorConfig:
    """Runtime configuration for translation behaviour."""

    fuzzy_threshold: int = 85
    alias_threshold: int = 90
    english_ratio_threshold: float = 0.5
    include_level_suffixes: bool = True
    output_mode: str = "plain"
    city_priority: List[str] = field(default_factory=lambda: ["普洱市", "景洪市"])
    fuzzy_levels: List[str] = field(default_factory=lambda: ["group", "village", "town"])

    @classmethod
    def from_file(cls, path: Optional[Path] = None) -> "TranslatorConfig":
        """Load configuration from a JSON file.

        Parameters
        ----------
        path:
            Optional override for the path to load. When ``None`` the default
            location :data:`DEFAULT_CONFIG_PATH` is used.
        """

        file_path = path or DEFAULT_CONFIG_PATH
        if not file_path.exists():
            return cls()

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Failed to parse configuration {file_path}: {exc.msg} at position {exc.pos}"
            ) from exc

        field_names = {field.name for field in cls.__dataclass_fields__.values()}
        filtered = {key: value for key, value in data.items() if key in field_names}
        return cls(**filtered)

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON serialisable representation of the config."""

        return {
            "fuzzy_threshold": self.fuzzy_threshold,
            "alias_threshold": self.alias_threshold,
            "english_ratio_threshold": self.english_ratio_threshold,
            "include_level_suffixes": self.include_level_suffixes,
            "output_mode": self.output_mode,
            "city_priority": list(self.city_priority),
            "fuzzy_levels": list(self.fuzzy_levels),
        }

    def save(self, path: Optional[Path] = None) -> None:
        """Persist the configuration to disk."""

        file_path = path or DEFAULT_CONFIG_PATH
        file_path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def level_order(self) -> Iterable[str]:
        """Return the canonical output order."""

        return ("group", "village", "town", "district", "city", "province")
