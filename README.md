# Yunnan Address Translator

This repository provides a command line and Tkinter based tool that converts
Chinese addresses from the Pu'er and Jinghong regions into consistent English
representations. The translator understands natural village names, production
groups, and common aliases that appear in spreadsheets, and outputs addresses in
the fixed order **Group → Village → Town → District/County → City → Province**.

## Features

- Extensive mapping for Pu'er City, Jinghong City, and their surrounding
  counties and towns with alias support for colloquial core words.
- Alias normalisation that automatically expands entries such as
  `"普洱市思茅区南屏大开河"` to the formal village name before translation.
- Optional fuzzy matching (RapidFuzz or a built in fallback) for group, village,
  and town layers to correct common typos.
- English input reshuffling: if a line already contains mainly English words it
  is deduplicated and re-ordered instead of being retranslated.
- Generic fallback for non Pu'er/Jinghong addresses that appends `Province`,
  `City`, `District`, `Town`, and `Village` suffixes using optional
  *pypinyin* transliteration when available.
- CLI logs every line to stderr with the detected hierarchy while writing the
  final translation to stdout, making it safe to use in pipelines.
- Tkinter UI with side-by-side input/output panes, line numbered results, log
  window, and incremental learning: newly confirmed aliases or villages can be
  appended to `mapping.json` directly from the interface.
- Built in regression tests that exercise the four mandatory sample lines.

## Getting started

1. **Install dependencies** (Python 3.10+). The translator uses `rapidfuzz`,
   `pytest`, and optionally `pypinyin` for generic fallback transliteration. In
a restricted environment the translator falls back to a `difflib` based scorer.
2. **Review configuration** in `config.json`. You can adjust the fuzzy match
   threshold, alias handling sensitivity, the English detection ratio, and the
   target level order.
3. **Run translations via CLI**:

   ```bash
   python translate.py --mapping mapping.json --config config.json < input.txt > output.txt
   ```

   Add `--tsv` to emit `原文\t英文` format.

4. **Launch the UI** for interactive workflows:

   ```bash
   python translate.py --ui
   ```

   Use the “追加映射” button to add alias/village entries and persist them back
   to `mapping.json` without restarting the program.

## Tests

Execute the regression suite with:

```bash
pytest
```

The tests ensure that the mandatory sample inputs always produce the expected
English addresses, that English reordering works, and that generic fallback
returns suffixed results.

## Data files

- `mapping.json` – Chinese to English dictionaries for each administrative
  level plus alias definitions.
- `config.json` – runtime configuration.

Feel free to expand `mapping.json` with new entries; the loader validates the
schema and will continue using the previous good mapping if a JSON error is
introduced.
