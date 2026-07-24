from string import Formatter

import pytest

from skill_dna_compiler.ui.i18n import LANGUAGE_LABELS, TEXT, text


def _fields(value: str) -> set[str]:
    return {
        field_name
        for _, field_name, _, _ in Formatter().parse(value)
        if field_name is not None
    }


def test_every_ui_entry_has_all_supported_languages_and_matching_placeholders():
    expected_languages = set(LANGUAGE_LABELS)

    for key, translations in TEXT.items():
        assert set(translations) == expected_languages, key
        assert all(value.strip() for value in translations.values()), key
        placeholder_sets = {
            frozenset(_fields(value)) for value in translations.values()
        }
        assert len(placeholder_sets) == 1, key


def test_unknown_ui_translation_fails_closed():
    with pytest.raises(KeyError, match="Unknown UI translation"):
        text("en", "missing.key")
