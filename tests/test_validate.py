"""validate.py のテスト"""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from validate import (
    check_decisions,
    check_file_exists,
    check_index_links,
    check_mermaid_syntax,
    check_openapi,
    check_rag_sections,
    check_yaml,
    validate_name,
)


class TestValidateName:
    """--name 引数のバリデーション"""

    def test_normal_name(self):
        assert validate_name("user-authentication") == "user-authentication"

    def test_name_with_dots(self):
        assert validate_name("my.feature") == "my.feature"

    def test_path_traversal_blocked(self):
        with pytest.raises(ValueError, match="path traversal"):
            validate_name("../../etc/passwd")

    def test_absolute_path_blocked(self):
        with pytest.raises(ValueError, match="path traversal"):
            validate_name("/etc/passwd")

    def test_path_separator_blocked(self):
        with pytest.raises(ValueError, match="path traversal"):
            validate_name("sub/dir")

    def test_backslash_blocked(self):
        with pytest.raises(ValueError, match="path traversal"):
            validate_name("sub\\dir")


class TestCheckFileExists:
    def test_existing_file(self, capsys):
        with tempfile.NamedTemporaryFile() as f:
            assert check_file_exists(f.name, "test") is True

    def test_missing_file(self, capsys):
        assert check_file_exists("/nonexistent/file.md", "test") is False


class TestCheckRagSections:
    def test_all_sections_present(self, tmp_path):
        rag = tmp_path / "test.rag.md"
        rag.write_text(
            "## SYSTEM_OVERVIEW\n## COMPONENTS\n## FLOW\n"
            "## DEPENDENCY\n## ERROR_HANDLING\n## BUSINESS_RULES\n"
            "## CONSTRAINTS\n## KEYWORDS\n"
        )
        assert check_rag_sections(str(rag), "test") is True

    def test_missing_sections(self, tmp_path):
        rag = tmp_path / "test.rag.md"
        rag.write_text("## SYSTEM_OVERVIEW\n## COMPONENTS\n")
        assert check_rag_sections(str(rag), "test") is False

    def test_file_not_found(self):
        assert check_rag_sections("/nonexistent", "test") is False


class TestCheckYaml:
    def test_valid_yaml(self, tmp_path):
        y = tmp_path / "test.yaml"
        y.write_text("id: test\nversion: 1.0.0\n")
        assert check_yaml(str(y), "test") is True

    def test_invalid_yaml(self, tmp_path):
        y = tmp_path / "test.yaml"
        y.write_text("invalid: yaml: content: [broken")
        assert check_yaml(str(y), "test") is False

    def test_file_not_found(self):
        assert check_yaml("/nonexistent", "test") is False


class TestCheckDecisions:
    def test_with_unverified(self, tmp_path):
        d = tmp_path / "test.md"
        d.write_text("| 1 | 判断 | 未確認 |\n| 2 | 判断 | 未確認 |\n")
        assert check_decisions(str(d), "test") is True  # 警告つきでTrue

    def test_all_verified(self, tmp_path):
        d = tmp_path / "test.md"
        d.write_text("| 1 | 判断 | 確認済み |\n")
        assert check_decisions(str(d), "test") is True

    def test_file_not_found(self):
        assert check_decisions("/nonexistent", "test") is False


class TestCheckOpenapi:
    """OpenAPI YAML バリデーション"""

    def test_valid_openapi(self, tmp_path):
        """Valid OpenAPI with all required fields should pass."""
        f = tmp_path / "openapi.yaml"
        f.write_text(
            "openapi: 3.0.0\n"
            "info:\n"
            "  title: Test API\n"
            "  version: 1.0.0\n"
            "paths:\n"
            "  /health:\n"
            "    get:\n"
            "      summary: Health check\n"
        )
        errors = check_openapi(str(f))
        assert errors == []

    def test_missing_paths(self, tmp_path):
        """OpenAPI YAML missing 'paths' field should fail."""
        f = tmp_path / "openapi.yaml"
        f.write_text(
            "openapi: 3.0.0\n"
            "info:\n"
            "  title: Test API\n"
            "  version: 1.0.0\n"
        )
        errors = check_openapi(str(f))
        assert any("paths" in e for e in errors)

    def test_missing_info(self, tmp_path):
        """OpenAPI YAML missing 'info' field should fail."""
        f = tmp_path / "openapi.yaml"
        f.write_text(
            "openapi: 3.0.0\n"
            "paths:\n"
            "  /health:\n"
            "    get:\n"
            "      summary: Health check\n"
        )
        errors = check_openapi(str(f))
        assert any("info" in e for e in errors)

    def test_missing_openapi_version(self, tmp_path):
        """OpenAPI YAML missing 'openapi' field should fail."""
        f = tmp_path / "openapi.yaml"
        f.write_text(
            "info:\n"
            "  title: Test API\n"
            "  version: 1.0.0\n"
            "paths: {}\n"
        )
        errors = check_openapi(str(f))
        assert any("openapi" in e for e in errors)

    def test_invalid_yaml(self, tmp_path):
        """Invalid YAML should return parse error."""
        f = tmp_path / "openapi.yaml"
        f.write_text("invalid: yaml: [broken")
        errors = check_openapi(str(f))
        assert len(errors) > 0
        assert any("parse" in e.lower() or "YAML" in e for e in errors)

    def test_file_not_found(self):
        """Non-existent file should return error."""
        errors = check_openapi("/nonexistent/openapi.yaml")
        assert len(errors) > 0


class TestCheckMermaidSyntax:
    """Mermaid .mmd ファイルの構文チェック"""

    def test_valid_flowchart(self, tmp_path):
        """Valid flowchart diagram should pass."""
        f = tmp_path / "test.mmd"
        f.write_text("flowchart TD\n  A --> B\n")
        errors = check_mermaid_syntax(str(f))
        assert errors == []

    def test_valid_sequence_diagram(self, tmp_path):
        """Valid sequenceDiagram should pass."""
        f = tmp_path / "test.mmd"
        f.write_text("sequenceDiagram\n  Alice->>Bob: Hello\n")
        errors = check_mermaid_syntax(str(f))
        assert errors == []

    def test_valid_er_diagram(self, tmp_path):
        """Valid erDiagram should pass."""
        f = tmp_path / "test.mmd"
        f.write_text("erDiagram\n  USER ||--o{ ORDER : places\n")
        errors = check_mermaid_syntax(str(f))
        assert errors == []

    def test_valid_c4context(self, tmp_path):
        """Valid C4Context diagram should pass."""
        f = tmp_path / "test.mmd"
        f.write_text("C4Context\n  Person(user, \"User\")\n")
        errors = check_mermaid_syntax(str(f))
        assert errors == []

    def test_valid_class_diagram(self, tmp_path):
        """Valid classDiagram should pass."""
        f = tmp_path / "test.mmd"
        f.write_text("classDiagram\n  class Animal\n")
        errors = check_mermaid_syntax(str(f))
        assert errors == []

    def test_valid_state_diagram(self, tmp_path):
        """Valid stateDiagram should pass."""
        f = tmp_path / "test.mmd"
        f.write_text("stateDiagram-v2\n  [*] --> Active\n")
        errors = check_mermaid_syntax(str(f))
        assert errors == []

    def test_invalid_content(self, tmp_path):
        """File not starting with valid diagram type should fail."""
        f = tmp_path / "test.mmd"
        f.write_text("This is not a mermaid diagram\n")
        errors = check_mermaid_syntax(str(f))
        assert len(errors) > 0

    def test_empty_file(self, tmp_path):
        """Empty file should fail."""
        f = tmp_path / "test.mmd"
        f.write_text("")
        errors = check_mermaid_syntax(str(f))
        assert len(errors) > 0

    def test_file_not_found(self):
        """Non-existent file should return error."""
        errors = check_mermaid_syntax("/nonexistent/test.mmd")
        assert len(errors) > 0


class TestCheckIndexLinks:
    """index.md 内リンクの存在チェック"""

    def test_all_links_valid(self, tmp_path):
        """All links pointing to existing files should pass."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "architecture").mkdir()
        (docs / "architecture" / "app.md").write_text("# Architecture")
        (docs / "manual").mkdir()
        (docs / "manual" / "guide.md").write_text("# Guide")

        index = docs / "index.md"
        index.write_text(
            "# Index\n"
            "[Architecture](architecture/app.md)\n"
            "[Manual](manual/guide.md)\n"
        )

        broken = check_index_links(str(index), str(docs))
        assert broken == []

    def test_broken_link_reported(self, tmp_path):
        """Broken links should be reported."""
        docs = tmp_path / "docs"
        docs.mkdir()

        index = docs / "index.md"
        index.write_text(
            "# Index\n"
            "[Missing](nonexistent/file.md)\n"
            "[Also Missing](another/missing.md)\n"
        )

        broken = check_index_links(str(index), str(docs))
        assert len(broken) == 2
        assert any("nonexistent/file.md" in b for b in broken)
        assert any("another/missing.md" in b for b in broken)

    def test_mixed_valid_and_broken(self, tmp_path):
        """Should only report broken links, not valid ones."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "exists.md").write_text("# Exists")

        index = docs / "index.md"
        index.write_text(
            "[Good](exists.md)\n"
            "[Bad](missing.md)\n"
        )

        broken = check_index_links(str(index), str(docs))
        assert len(broken) == 1
        assert any("missing.md" in b for b in broken)

    def test_external_links_ignored(self, tmp_path):
        """External URLs (http/https) should be ignored."""
        docs = tmp_path / "docs"
        docs.mkdir()

        index = docs / "index.md"
        index.write_text(
            "[Google](https://google.com)\n"
            "[HTTP](http://example.com)\n"
        )

        broken = check_index_links(str(index), str(docs))
        assert broken == []

    def test_index_file_not_found(self):
        """Non-existent index file should return error."""
        broken = check_index_links("/nonexistent/index.md", "/nonexistent")
        assert len(broken) > 0
