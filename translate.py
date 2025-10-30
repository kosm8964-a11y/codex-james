"""Command line interface for the address translator."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

from address_translator import AddressTranslator, MappingLoader, TranslatorConfig
from address_translator import translator_ui


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Translate Yunnan addresses to English")
    parser.add_argument(
        "--mapping",
        type=Path,
        default=Path("mapping.json"),
        help="Path to mapping.json",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.json"),
        help="Path to configuration JSON file",
    )
    parser.add_argument(
        "--tsv",
        action="store_true",
        help="Emit tab separated original and translated output",
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Launch the Tkinter UI instead of running in CLI mode",
    )
    return parser.parse_args(list(argv))


def run_cli(args: argparse.Namespace) -> int:
    try:
        config = TranslatorConfig.from_file(args.config)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2

    loader = MappingLoader(args.mapping)
    try:
        translator = AddressTranslator(loader, config)
    except Exception as exc:  # pylint: disable=broad-except
        print(f"无法初始化翻译器: {exc}", file=sys.stderr)
        return 2

    lines = sys.stdin.read().splitlines()
    results = translator.translate_lines(lines, tsv=args.tsv)
    for result in results:
        output_line = result.as_text(tsv=args.tsv)
        print(output_line)
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.ui:
        config = TranslatorConfig.from_file(args.config)
        loader = MappingLoader(args.mapping)
        translator_ui.launch(loader, config)
        return 0
    return run_cli(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
