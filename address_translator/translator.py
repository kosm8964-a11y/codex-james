"""Core translation logic for Chinese to English address normalisation."""
from __future__ import annotations

from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple
import re
import sys

try:
    from rapidfuzz import fuzz, process
except ImportError:  # pragma: no cover
    from difflib import SequenceMatcher

    class _DiffLibFuzz:
        @staticmethod
        def ratio(a: str, b: str) -> float:
            return SequenceMatcher(None, a, b).ratio() * 100

        @staticmethod
        def partial_ratio(a: str, b: str) -> float:
            shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
            if not shorter:
                return 0.0
            best = 0.0
            for start in range(0, len(longer) - len(shorter) + 1):
                window = longer[start : start + len(shorter)]
                score = SequenceMatcher(None, shorter, window).ratio() * 100
                if score > best:
                    best = score
            return best

    class _DiffLibProcess:
        @staticmethod
        def extractOne(query: str, choices, scorer=_DiffLibFuzz.partial_ratio, score_cutoff: float = 0):
            best_choice = None
            best_score = score_cutoff
            best_index = -1
            for idx, choice in enumerate(choices):
                score = scorer(query, choice)
                if score >= best_score:
                    best_choice = choice
                    best_score = score
                    best_index = idx
            if best_choice is None:
                return None
            return best_choice, best_score, best_index

    fuzz = _DiffLibFuzz()
    process = _DiffLibProcess()

try:  # pragma: no cover - optional dependency
    from pypinyin import lazy_pinyin  # type: ignore
except ImportError:  # pragma: no cover
    lazy_pinyin = None

from .config import TranslatorConfig
from .mapping_loader import MappingLoader


@dataclass
class Match:
    level: str
    key: str
    english: str
    matched_text: str
    score: Optional[float] = None


@dataclass
class TranslationResult:
    """Container for a translated row."""

    line_number: int
    original: str
    detected: Dict[str, List[str]]
    output: List[str]

    def as_text(self, *, tsv: bool = False) -> str:
        if tsv:
            return f"{self.original}\t{', '.join(self.output)}"
        return ", ".join(self.output)


class AddressTranslator:
    """Translate Chinese addresses into a canonical English order."""

    def __init__(self, loader: MappingLoader, config: Optional[TranslatorConfig] = None) -> None:
        self.loader = loader
        self.config = config or TranslatorConfig()
        self.mapping = self.loader.load()
        self._level_keys: Dict[str, Tuple[str, ...]] = {
            level: tuple(self.mapping.raw.get(level, {}).keys())
            for level in ("group", "village", "town", "district", "city", "province")
        }
        self._english_levels = self.mapping.english_to_level()

    def reload_mapping(self) -> None:
        self.mapping = self.loader.load()
        self._level_keys = {
            level: tuple(self.mapping.raw.get(level, {}).keys())
            for level in ("group", "village", "town", "district", "city", "province")
        }
        self._english_levels = self.mapping.english_to_level()

    def translate_lines(
        self, lines: Iterable[str], *, tsv: bool = False, log: bool = True
    ) -> List[TranslationResult]:
        results: List[TranslationResult] = []
        for idx, line in enumerate(lines, start=1):
            result = self.translate_line(
                line.rstrip("\n"), line_number=idx, tsv=tsv, log=log
            )
            results.append(result)
        return results

    def translate_line(
        self, line: str, *, line_number: int, tsv: bool = False, log: bool = True
    ) -> TranslationResult:
        if not line.strip():
            return TranslationResult(line_number, line, defaultdict(list), [line])

        if self._is_mostly_english(line):
            ordered = self._normalise_english_line(line)
            detected = defaultdict(list)
            for value in ordered:
                level = self._english_levels.get(value.lower())
                if level:
                    detected[level].append(value)
            return TranslationResult(line_number, line, detected, ordered)

        text = line
        alias_hits: List[Tuple[str, str]] = []
        for alias, canonical in sorted(
            self.mapping.alias.items(), key=lambda item: len(item[0]), reverse=True
        ):
            if alias in text and canonical not in text:
                text = text.replace(alias, canonical)
                alias_hits.append((alias, canonical))

        detected: Dict[str, List[str]] = defaultdict(list)
        residual = text

        for level in ("group", "village", "town", "district", "city", "province"):
            matches = self._collect_matches(residual, level)
            for match in matches:
                detected[level].append(match.english)
                residual = self._remove_once(residual, match.matched_text)

        ordered_output = self._order_and_dedupe(detected)
        if not ordered_output:
            fallback = self._generic_translate(line)
            if fallback:
                detected = fallback
                ordered_output = self._order_and_dedupe(detected)

        if not ordered_output:
            ordered_output = [line]

        if log and alias_hits:
            alias_log = ", ".join(f"{src}->{dst}" for src, dst in alias_hits)
            print(f"第{line_number}行 alias 替换: {alias_log}", file=sys.stderr)

        if log:
            print(
                f"第{line_number}行 原文: {line} | 识别: "
                + ", ".join(
                    f"{level}:{'/'.join(values)}" for level, values in detected.items() if values
                )
                + f" | 输出: {', '.join(ordered_output)}",
                file=sys.stderr,
            )
        return TranslationResult(line_number, line, detected, ordered_output)

    def _collect_matches(self, text: str, level: str) -> List[Match]:
        mapping = self.mapping.raw.get(level, {})
        keys = self._level_keys.get(level, ())
        matches: List[Match] = []
        working = text
        while True:
            match = self._find_single_match(working, level, mapping, keys)
            if not match:
                break
            matches.append(match)
            working = self._remove_once(working, match.matched_text)
        return matches

    def _find_single_match(
        self,
        text: str,
        level: str,
        mapping: Dict[str, str],
        keys: Tuple[str, ...],
    ) -> Optional[Match]:
        if not text.strip():
            return None

        direct = self._find_direct_match(text, level, mapping, keys)
        if direct:
            return direct

        if level in set(self.config.fuzzy_levels):
            fuzzy = self._find_fuzzy_match(text, level, mapping, keys)
            if fuzzy:
                return fuzzy
        return None

    def _find_direct_match(
        self, text: str, level: str, mapping: Dict[str, str], keys: Tuple[str, ...]
    ) -> Optional[Match]:
        for key in sorted(keys, key=len, reverse=True):
            if key and key in text:
                return Match(level=level, key=key, english=mapping[key], matched_text=key)
        return None

    def _find_fuzzy_match(
        self,
        text: str,
        level: str,
        mapping: Dict[str, str],
        keys: Tuple[str, ...],
    ) -> Optional[Match]:
        if not keys:
            return None
        result = process.extractOne(
            text,
            keys,
            scorer=fuzz.partial_ratio,
            score_cutoff=self.config.fuzzy_threshold,
        )
        if not result:
            return None
        key, score, _ = result
        matched = self._best_substring(text, key)
        return Match(level=level, key=key, english=mapping[key], matched_text=matched, score=score)

    @staticmethod
    def _best_substring(text: str, target: str) -> str:
        if target in text:
            return target
        best = target
        best_score = -1
        for start in range(len(text)):
            for end in range(start + 1, len(text) + 1):
                candidate = text[start:end]
                score = fuzz.ratio(candidate, target)
                if score > best_score:
                    best_score = score
                    best = candidate
        return best

    @staticmethod
    def _remove_once(text: str, fragment: str) -> str:
        if not fragment:
            return text
        return text.replace(fragment, "", 1)

    def _order_and_dedupe(self, detected: Dict[str, List[str]]) -> List[str]:
        ordered: List[str] = []
        seen = OrderedDict()
        for level in self.config.level_order():
            for value in detected.get(level, []):
                if value not in seen:
                    seen[value] = None
        ordered.extend(seen.keys())
        return ordered

    def _normalise_english_line(self, line: str) -> List[str]:
        tokens = [token.strip() for token in re.split(r"[,;/]+", line) if token.strip()]
        detected: Dict[str, List[str]] = defaultdict(list)
        for token in tokens:
            level = self._english_levels.get(token.lower())
            if level:
                detected[level].append(token)
            else:
                detected.setdefault("other", []).append(token)
        ordered = self._order_and_dedupe(detected)
        others: List[str] = []
        for token in detected.get("other", []):
            if token not in others:
                others.append(token)
        ordered.extend(others)
        return ordered

    def _generic_translate(self, text: str) -> Dict[str, List[str]]:
        level_patterns = {
            "province": r"(?P<value>[\u4e00-\u9fff]+?省)",
            "city": r"(?P<value>[\u4e00-\u9fff]+?(市|州))",
            "district": r"(?P<value>[\u4e00-\u9fff]+?(区|县|自治县))",
            "town": r"(?P<value>[\u4e00-\u9fff]+?(镇|乡|街道))",
            "village": r"(?P<value>[\u4e00-\u9fff]+?(村|村委会|村民委员会|村民小组))",
        }
        result: Dict[str, List[str]] = defaultdict(list)
        for level, pattern in level_patterns.items():
            matches = re.findall(pattern, text)
            for match in matches:
                english = self._generic_level_to_english(match, level)
                if english:
                    result[level].append(english)
        return result

    def _generic_level_to_english(self, value: str, level: str) -> Optional[str]:
        suffix_map = {
            "province": "Province",
            "city": "City",
            "district": "District",
            "town": "Town",
            "village": "Village",
        }
        if not value:
            return None
        suffix = suffix_map.get(level, "")
        if suffix:
            return f"{self._transliterate(value)} {suffix}".strip()
        return self._transliterate(value)

    @staticmethod
    def _transliterate(value: str) -> str:
        if lazy_pinyin:
            words = lazy_pinyin(value, strict=False)
            return " ".join(word.capitalize() for word in words if word)
        return value

    def _is_mostly_english(self, text: str) -> bool:
        letters = sum(1 for ch in text if ch.isalpha())
        ascii_letters = sum(1 for ch in text if ch.isascii() and ch.isalpha())
        if letters == 0:
            return False
        return ascii_letters / max(len(text.strip()), 1) >= self.config.english_ratio_threshold
