"""Read-only Obsidian Vault discovery and Markdown parsing."""

from skill_dna_compiler.vault.models import (
    DocumentSection,
    InternalLink,
    ParsedNote,
    VaultFile,
)
from skill_dna_compiler.vault.parser import MarkdownParseError, parse_markdown_file
from skill_dna_compiler.vault.scanner import VaultScanError, scan_vault

__all__ = [
    "DocumentSection",
    "InternalLink",
    "MarkdownParseError",
    "ParsedNote",
    "VaultFile",
    "VaultScanError",
    "parse_markdown_file",
    "scan_vault",
]

