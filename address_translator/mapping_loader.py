"""Utilities for loading mapping.json with validation and resilience."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, MutableMapping, Optional
import json
import threading


MANDATORY_FIELDS = ("province", "city", "district", "town", "village", "group", "alias")


@dataclass
class LoadedMapping:
    """Typed view over the mapping configuration."""

    raw: Dict[str, Dict[str, str]]

    @property
    def province(self) -> Dict[str, str]:
        return self.raw["province"]

    @property
    def city(self) -> Dict[str, str]:
        return self.raw["city"]

    @property
    def district(self) -> Dict[str, str]:
        return self.raw["district"]

    @property
    def town(self) -> Dict[str, str]:
        return self.raw["town"]

    @property
    def village(self) -> Dict[str, str]:
        return self.raw["village"]

    @property
    def group(self) -> Dict[str, str]:
        return self.raw["group"]

    @property
    def alias(self) -> Dict[str, str]:
        return self.raw["alias"]

    def english_to_level(self) -> Dict[str, str]:
        reverse: Dict[str, str] = {}
        for level in ("group", "village", "town", "district", "city", "province"):
            for _, english in self.raw.get(level, {}).items():
                reverse[english.lower()] = level
        return reverse


class MappingLoader:
    """Load mapping.json with schema validation and caching."""

    def __init__(self, path: Path | str = Path("mapping.json")) -> None:
        self.path = Path(path)
        self._cache: Optional[LoadedMapping] = None
        self._lock = threading.Lock()

    def load(self, *, silent: bool = False) -> LoadedMapping:
        """Load and validate the mapping file.

        The loader remembers the last successful mapping. When the file
        contains invalid JSON or fails schema validation the last good
        mapping is returned and a warning is emitted.
        """

        with self._lock:
            try:
                raw = self._read()
                self._validate(raw)
            except Exception as exc:  # pylint: disable=broad-except
                if self._cache is None:
                    raise
                if not silent:
                    print(
                        f"mapping 加载失败，使用上一次成功的映射: {exc}",
                    )
                return self._cache

            self._cache = LoadedMapping(raw)
            return self._cache

    def _read(self) -> Dict[str, Dict[str, str]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"mapping.json 解析失败：第 {exc.pos} 字符附近错误"
            ) from exc
        return data

    def _validate(self, data: Mapping[str, object]) -> None:
        missing = [field for field in MANDATORY_FIELDS if field not in data]
        if missing:
            raise ValueError(f"mapping.json 缺少字段: {', '.join(missing)}")

        for field in MANDATORY_FIELDS:
            value = data[field]
            if not isinstance(value, MutableMapping):
                raise ValueError(f"mapping.json 字段 {field} 必须是对象 (dict)")
            for key, english in value.items():
                if not isinstance(key, str) or not isinstance(english, str):
                    raise ValueError(f"{field} 下的键和值都必须是字符串: {key!r} -> {english!r}")

    def save(self, mapping: LoadedMapping) -> None:
        """Persist the mapping data back to disk."""

        with self._lock:
            self.path.write_text(
                json.dumps(mapping.raw, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            self._cache = mapping

    def update_entry(self, level: str, key: str, value: str) -> LoadedMapping:
        """Add or update an entry in the mapping file."""

        mapping = self.load(silent=True)
        if level not in mapping.raw:
            raise ValueError(f"不支持的层级: {level}")
        mapping.raw[level][key] = value
        self.save(mapping)
        return mapping

    def last_loaded(self) -> Optional[LoadedMapping]:
        """Return the last successfully loaded mapping."""

        return self._cache
