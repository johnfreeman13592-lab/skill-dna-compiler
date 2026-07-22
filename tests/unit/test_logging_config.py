import logging

from skill_dna_compiler.logging_config import SensitiveDataFilter, redact_text


def test_redact_text_removes_openai_key():
    text = "OPENAI_API_KEY=sk-example_secret_123456789"

    result = redact_text(text)

    assert "example_secret" not in result
    assert "[REDACTED]" in result


def test_filter_redacts_format_arguments():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="key=%s",
        args=("sk-example_secret_123456789",),
        exc_info=None,
    )

    SensitiveDataFilter().filter(record)

    assert "example_secret" not in record.getMessage()

