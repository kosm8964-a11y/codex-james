"""Unit tests for the address translator."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from address_translator import AddressTranslator, MappingLoader, TranslatorConfig


@pytest.fixture(scope="module")
def translator() -> AddressTranslator:
    config = TranslatorConfig.from_file(Path("config.json"))
    loader = MappingLoader(Path("mapping.json"))
    return AddressTranslator(loader, config)


def extract_output(result) -> str:
    return ", ".join(result.output)


def test_required_cases(translator: AddressTranslator) -> None:
    lines = [
        "普洱市思茅区南屏大开河",
        "景洪市普文镇坡脚",
        "普洱市思茅区南屏镇南岛河",
        "景洪市普文镇称杆村委会曼广村",
    ]
    results = translator.translate_lines(lines, log=False)
    outputs = [extract_output(res) for res in results]
    assert outputs[0] == "Dakaihe Village, Nanping Town, Simao District, Puer City"
    assert outputs[1] == "Pojiao Village, Puwen Town, Jinghong City"
    assert outputs[2] == "Nandaohe Village, Nanping Town, Simao District, Puer City"
    assert outputs[3] == "Manguang Village, Chenggan Village, Puwen Town, Jinghong City"


def test_english_reordering(translator: AddressTranslator) -> None:
    line = "Nanping Town, Nanping Town, Simao District, Simao District"
    result = translator.translate_line(line, line_number=1, log=False)
    assert result.output == ["Nanping Town", "Simao District"]


def test_generic_fallback(translator: AddressTranslator) -> None:
    line = "中国云南省昆明市官渡区关上街道办事处"
    result = translator.translate_line(line, line_number=2, log=False)
    assert "Province" in result.output[-1]
