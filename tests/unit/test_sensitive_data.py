import pytest

from skill_dna_compiler.security import SensitiveDataScanner, Severity


def test_scanner_redacts_credentials_without_storing_values():
    openai_key = "sk-proj-exampleSecretValue1234567890"
    github_token = "ghp_abcdefghijklmnopqrstuvwxyz123456"
    text = f"OPENAI_API_KEY={openai_key}\ngithub={github_token}\n"

    result = SensitiveDataScanner().scan(text)

    assert openai_key not in result.sanitized_text
    assert github_token not in result.sanitized_text
    assert {finding.kind for finding in result.findings} == {
        "openai_api_key",
        "github_token",
    }
    assert all(finding.severity == Severity.HIGH for finding in result.findings)
    assert openai_key not in result.model_dump_json()
    assert github_token not in result.model_dump_json()


def test_scanner_redacts_contact_details_and_preserves_line_locations():
    text = "Contact test@example.com\nPhone 090-1234-5678\n"

    result = SensitiveDataScanner().scan(text)

    assert "test@example.com" not in result.sanitized_text
    assert "090-1234-5678" not in result.sanitized_text
    assert [(item.kind, item.line) for item in result.findings] == [
        ("email_address", 1),
        ("phone_number", 2),
    ]


def test_scanner_redacts_windows_paths_that_can_expose_local_identity():
    local_path = r"C:\Users\ExamplePerson\OneDrive\Notes\Project memo.md"
    network_path = r"\\private-server\personal-share\planning\notes.md"
    text = f"Project: `{local_path}`\nBackup: '{network_path}'\n"

    result = SensitiveDataScanner().scan(text)

    assert local_path not in result.sanitized_text
    assert network_path not in result.sanitized_text
    assert result.sanitized_text.count("[REDACTED:local_path]") == 2
    assert [(item.kind, item.severity, item.line) for item in result.findings] == [
        ("local_path", Severity.MEDIUM, 1),
        ("local_path", Severity.MEDIUM, 2),
    ]


def test_scanner_preserves_relative_project_paths():
    text = ".venv\\Scripts\\python.exe run.py\nreports/latest_check.md\n"

    result = SensitiveDataScanner().scan(text)

    assert result.sanitized_text == text
    assert result.findings == []


def test_scanner_redacts_multiline_private_key():
    private_key = (
        "-----BEGIN PRIVATE KEY-----\n"
        "super-secret-key-material\n"
        "-----END PRIVATE KEY-----"
    )

    result = SensitiveDataScanner().scan(private_key)

    assert "super-secret-key-material" not in result.sanitized_text
    assert result.findings[0].kind == "private_key"
    assert result.sanitized_text.count("\n") == private_key.count("\n")


@pytest.mark.parametrize(
    ("text", "secret", "expected_kind"),
    [
        ('{"client_secret": "json-secret-value-123"}', "json-secret-value-123", "assigned_secret"),
        ('{"password": "json-password-value-123"}', "json-password-value-123", "assigned_secret"),
        ("client_secret: 'yaml-secret-value-123'", "yaml-secret-value-123", "assigned_secret"),
        (
            "Authorization: Bearer bearer-token-value-123456",
            "bearer-token-value-123456",
            "bearer_token",
        ),
    ],
)
def test_scanner_redacts_structured_and_bearer_credentials(
    text, secret, expected_kind
):
    result = SensitiveDataScanner().scan(text)

    assert secret not in result.sanitized_text
    assert len(result.findings) == 1
    assert result.findings[0].kind == expected_kind
    assert result.findings[0].severity == Severity.HIGH


def test_scanner_preserves_benign_quoted_configuration():
    text = '{"theme": "high-contrast", "description": "Bearer of good news"}'

    result = SensitiveDataScanner().scan(text)

    assert result.sanitized_text == text
    assert result.findings == []


def test_scanner_is_idempotent_for_its_own_redaction_markers():
    scanner = SensitiveDataScanner()
    first = scanner.scan('password="json-password-value-123"')

    second = scanner.scan(first.sanitized_text)

    assert second.sanitized_text == first.sanitized_text
    assert second.findings == []
