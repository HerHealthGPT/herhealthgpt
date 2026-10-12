"""scripts/check_repo_hygiene.py: the rules that would have stopped the
injected postcss payload and the fake font file, and the one narrow exemption
for graphify's generated output. No git, network or filesystem is involved."""

import check_repo_hygiene as hygiene
import pytest

PADDING = " " * 500
PAYLOAD_LINE = "export default config;" + PADDING + "x" * 13_000


@pytest.mark.parametrize(
    "path", ["graphify-out/graph.html", "graphify-out/.graphify_labels.json"]
)
def test_graphify_generated_files_may_have_long_lines(path: str) -> None:
    assert hygiene.check_line_length(path, "y" * 50_000) is None


def test_other_files_under_graphify_out_are_not_exempt() -> None:
    # The exemption names two generated files. It must not turn the directory
    # into a place where a long hidden line goes unnoticed.
    finding = hygiene.check_line_length("graphify-out/postcss.config.mjs", PAYLOAD_LINE)
    assert finding is not None
    assert finding.rule == "minified-blob"


def test_graphify_output_is_still_scanned_for_credentials() -> None:
    leaked = "token: " + "sk-or-v1-" + "a" * 40
    findings = hygiene.check_secrets("graphify-out/graph.html", leaked)
    assert [finding.rule for finding in findings] == ["credential"]


def test_a_hidden_line_in_the_frontend_config_is_reported() -> None:
    finding = hygiene.check_line_length(
        "services/frontend/postcss.config.mjs", PAYLOAD_LINE
    )
    assert finding is not None
    assert "line 1" in finding.detail


def test_the_clean_frontend_config_passes() -> None:
    clean = (
        'const config = {\n  plugins: {\n    "@tailwindcss/postcss": {},\n  },\n};\n'
    )
    assert (
        hygiene.check_line_length("services/frontend/postcss.config.mjs", clean) is None
    )


def test_text_wearing_a_font_extension_is_reported() -> None:
    blob = (" " * 200 + "global.i = 1;").encode()
    finding = hygiene.check_text_posing_as_binary("public/fonts/fa-solid-700.otf", blob)
    assert finding is not None
    assert finding.rule == "text-posing-as-binary"


def test_a_real_font_is_not_reported() -> None:
    blob = b"wOF2\x00\x01\x00\x00" + b"\x00" * 64
    assert (
        hygiene.check_text_posing_as_binary("public/fonts/fa-solid-900.woff2", blob)
        is None
    )


def test_a_root_level_public_directory_is_reported() -> None:
    finding = hygiene.check_root_entry("public/fonts/README.md")
    assert finding is not None
    assert finding.rule == "unexpected-root-entry"
