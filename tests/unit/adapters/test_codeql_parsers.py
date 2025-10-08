"""Tests for CodeQL parsers."""

import csv
import json
from pathlib import Path

import pytest
from patchsmith.adapters.codeql.parsers import CSVParser, ParserError, SARIFParser
from patchsmith.models.finding import Severity


class TestSARIFParser:
    """Tests for SARIF parser."""

    @pytest.fixture
    def sample_sarif(self) -> dict:
        """Create a sample SARIF structure."""
        return {
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "CodeQL",
                            "version": "2.15.3",
                            "rules": [
                                {
                                    "id": "py/sql-injection",
                                    "name": "SQL Injection",
                                    "shortDescription": {"text": "SQL injection vulnerability"},
                                    "defaultConfiguration": {"level": "error"},
                                    "properties": {
                                        "tags": ["security", "external/cwe/cwe-89"],
                                        "problem.severity": "error",
                                    },
                                }
                            ],
                        }
                    },
                    "results": [
                        {
                            "ruleId": "py/sql-injection",
                            "level": "error",
                            "message": {"text": "Potential SQL injection vulnerability"},
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "src/app.py"},
                                        "region": {
                                            "startLine": 42,
                                            "endLine": 45,
                                            "snippet": {
                                                "text": 'query = f"SELECT * FROM users WHERE id = {user_id}"'
                                            },
                                        },
                                    }
                                }
                            ],
                        }
                    ],
                }
            ],
        }

    def test_parse_basic_sarif(self, sample_sarif: dict) -> None:
        """Test parsing basic SARIF structure."""
        parser = SARIFParser()
        findings = parser.parse(sample_sarif)

        assert len(findings) == 1
        finding = findings[0]

        assert finding.rule_id == "py/sql-injection"
        assert finding.severity == Severity.HIGH  # "error" maps to HIGH
        assert finding.file_path == Path("src/app.py")
        assert finding.start_line == 42
        assert finding.end_line == 45
        assert "SQL injection" in finding.message
        assert finding.snippet is not None
        assert "SELECT" in finding.snippet

    def test_parse_with_cwe(self, sample_sarif: dict) -> None:
        """Test parsing SARIF with CWE information."""
        parser = SARIFParser()
        findings = parser.parse(sample_sarif)

        assert len(findings) == 1
        finding = findings[0]

        assert finding.cwe is not None
        assert finding.cwe.id == "CWE-89"

    def test_parse_multiple_results(self) -> None:
        """Test parsing SARIF with multiple results."""
        sarif = {
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "CodeQL", "rules": []}},
                    "results": [
                        {
                            "ruleId": "rule1",
                            "level": "warning",
                            "message": {"text": "Issue 1"},
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "file1.py"},
                                        "region": {"startLine": 10, "endLine": 10},
                                    }
                                }
                            ],
                        },
                        {
                            "ruleId": "rule2",
                            "level": "note",
                            "message": {"text": "Issue 2"},
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "file2.py"},
                                        "region": {"startLine": 20, "endLine": 20},
                                    }
                                }
                            ],
                        },
                    ],
                }
            ],
        }

        parser = SARIFParser()
        findings = parser.parse(sarif)

        assert len(findings) == 2
        assert findings[0].rule_id == "rule1"
        assert findings[0].severity == Severity.MEDIUM  # warning
        assert findings[1].rule_id == "rule2"
        assert findings[1].severity == Severity.LOW  # note

    def test_parse_multiple_runs(self) -> None:
        """Test parsing SARIF with multiple runs."""
        sarif = {
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "Tool1", "rules": []}},
                    "results": [
                        {
                            "ruleId": "rule1",
                            "message": {"text": "Issue 1"},
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "file.py"},
                                        "region": {"startLine": 1},
                                    }
                                }
                            ],
                        }
                    ],
                },
                {
                    "tool": {"driver": {"name": "Tool2", "rules": []}},
                    "results": [
                        {
                            "ruleId": "rule2",
                            "message": {"text": "Issue 2"},
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "file.py"},
                                        "region": {"startLine": 2},
                                    }
                                }
                            ],
                        }
                    ],
                },
            ],
        }

        parser = SARIFParser()
        findings = parser.parse(sarif)

        assert len(findings) == 2

    def test_parse_empty_results(self) -> None:
        """Test parsing SARIF with no results."""
        sarif = {
            "version": "2.1.0",
            "runs": [{"tool": {"driver": {"name": "CodeQL"}}, "results": []}],
        }

        parser = SARIFParser()
        findings = parser.parse(sarif)

        assert len(findings) == 0

    def test_parse_result_without_rule_id(self) -> None:
        """Test parsing result without rule ID (should skip)."""
        sarif = {
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "CodeQL", "rules": []}},
                    "results": [
                        {
                            # Missing ruleId
                            "message": {"text": "Some issue"},
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "file.py"},
                                        "region": {"startLine": 1},
                                    }
                                }
                            ],
                        }
                    ],
                }
            ],
        }

        parser = SARIFParser()
        findings = parser.parse(sarif)

        assert len(findings) == 0  # Should skip invalid result

    def test_parse_result_without_locations(self) -> None:
        """Test parsing result without locations (should skip)."""
        sarif = {
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "CodeQL", "rules": []}},
                    "results": [
                        {
                            "ruleId": "rule1",
                            "message": {"text": "Some issue"},
                            "locations": [],  # Empty locations
                        }
                    ],
                }
            ],
        }

        parser = SARIFParser()
        findings = parser.parse(sarif)

        assert len(findings) == 0  # Should skip result without location

    def test_severity_mapping(self) -> None:
        """Test SARIF severity level mapping."""
        parser = SARIFParser()

        assert parser.SEVERITY_MAP["error"] == Severity.HIGH
        assert parser.SEVERITY_MAP["warning"] == Severity.MEDIUM
        assert parser.SEVERITY_MAP["note"] == Severity.LOW
        assert parser.SEVERITY_MAP["none"] == Severity.INFO

    def test_extract_severity_from_result(self) -> None:
        """Test severity extraction from result level."""
        parser = SARIFParser()

        result = {"level": "error"}
        rule = {}

        severity = parser._extract_severity(result, rule)
        assert severity == Severity.HIGH

    def test_extract_severity_from_rule(self) -> None:
        """Test severity extraction from rule configuration."""
        parser = SARIFParser()

        result = {}
        rule = {"defaultConfiguration": {"level": "warning"}}

        severity = parser._extract_severity(result, rule)
        assert severity == Severity.MEDIUM

    def test_extract_severity_from_properties(self) -> None:
        """Test severity extraction from rule properties."""
        parser = SARIFParser()

        result = {}
        rule = {"properties": {"problem.severity": "high"}}

        severity = parser._extract_severity(result, rule)
        assert severity == Severity.HIGH

    def test_extract_severity_default(self) -> None:
        """Test default severity when none specified."""
        parser = SARIFParser()

        result = {}
        rule = {}

        severity = parser._extract_severity(result, rule)
        assert severity == Severity.MEDIUM  # Default

    def test_extract_cwe_from_tags(self) -> None:
        """Test CWE extraction from rule tags."""
        parser = SARIFParser()

        rule = {"properties": {"tags": ["security", "external/cwe/cwe-89", "injection"]}}

        cwe = parser._extract_cwe(rule)

        assert cwe is not None
        assert cwe.id == "CWE-89"

    def test_extract_cwe_not_found(self) -> None:
        """Test CWE extraction when no CWE in tags."""
        parser = SARIFParser()

        rule = {"properties": {"tags": ["security", "performance"]}}

        cwe = parser._extract_cwe(rule)

        assert cwe is None

    def test_parse_file_success(self, sample_sarif: dict, tmp_path: Path) -> None:
        """Test parsing SARIF from file."""
        sarif_file = tmp_path / "results.sarif"
        sarif_file.write_text(json.dumps(sample_sarif))

        parser = SARIFParser()
        findings = parser.parse_file(sarif_file)

        assert len(findings) == 1
        assert findings[0].rule_id == "py/sql-injection"

    def test_parse_file_not_exists(self, tmp_path: Path) -> None:
        """Test parsing non-existent file."""
        parser = SARIFParser()
        nonexistent = tmp_path / "nonexistent.sarif"

        with pytest.raises(ParserError, match="does not exist"):
            parser.parse_file(nonexistent)

    def test_parse_file_invalid_json(self, tmp_path: Path) -> None:
        """Test parsing file with invalid JSON."""
        sarif_file = tmp_path / "invalid.sarif"
        sarif_file.write_text("not valid json {")

        parser = SARIFParser()

        with pytest.raises(ParserError, match="Invalid JSON"):
            parser.parse_file(sarif_file)

    def test_parse_invalid_structure(self) -> None:
        """Test parsing with invalid SARIF structure."""
        parser = SARIFParser()

        # Missing required fields
        invalid_sarif = {"invalid": "structure"}

        # Should handle gracefully and return empty list
        findings = parser.parse(invalid_sarif)
        assert len(findings) == 0

    def test_finding_id_generation(self, sample_sarif: dict) -> None:
        """Test finding ID generation."""
        parser = SARIFParser()
        findings = parser.parse(sample_sarif)

        assert len(findings) == 1
        # ID format: {rule_id}_{filename}_{line}
        assert findings[0].id == "py/sql-injection_app.py_42"

    def test_parse_with_multiline_region(self) -> None:
        """Test parsing result with multi-line region."""
        sarif = {
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "CodeQL", "rules": []}},
                    "results": [
                        {
                            "ruleId": "test/rule",
                            "message": {"text": "Test issue"},
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "test.py"},
                                        "region": {
                                            "startLine": 10,
                                            "endLine": 15,  # Multi-line
                                        },
                                    }
                                }
                            ],
                        }
                    ],
                }
            ],
        }

        parser = SARIFParser()
        findings = parser.parse(sarif)

        assert len(findings) == 1
        assert findings[0].start_line == 10
        assert findings[0].end_line == 15


class TestCSVParser:
    """Tests for CSV parser."""

    @pytest.fixture
    def sample_csv_rows(self) -> list[dict[str, str]]:
        """Create sample CSV rows."""
        return [
            {
                "name": "py/sql-injection",
                "description": "SQL injection vulnerability",
                "severity": "error",
                "message": "Potential SQL injection",
                "path": "src/app.py",
                "start line": "42",
                "end line": "42",
            },
            {
                "name": "py/command-injection",
                "description": "Command injection vulnerability",
                "severity": "warning",
                "message": "Potential command injection",
                "path": "src/utils.py",
                "start line": "15",
                "end line": "18",
            },
        ]

    def test_parse_success(self, sample_csv_rows: list[dict[str, str]]) -> None:
        """Test successful CSV parsing."""
        parser = CSVParser()
        findings = parser.parse(sample_csv_rows)

        assert len(findings) == 2

        # Check first finding
        assert findings[0].rule_id == "py/sql-injection"
        assert findings[0].severity == Severity.HIGH
        assert findings[0].file_path == Path("src/app.py")
        assert findings[0].start_line == 42
        assert findings[0].end_line == 42
        assert findings[0].message == "Potential SQL injection"

        # Check second finding
        assert findings[1].rule_id == "py/command-injection"
        assert findings[1].severity == Severity.MEDIUM
        assert findings[1].file_path == Path("src/utils.py")
        assert findings[1].start_line == 15
        assert findings[1].end_line == 18

    def test_parse_with_alternative_column_names(self) -> None:
        """Test parsing CSV with different column name variations."""
        rows = [
            {
                "Rule": "test/rule",
                "Message": "Test message",
                "Severity": "HIGH",
                "File": "test.py",
                "Line": "10",
            }
        ]

        parser = CSVParser()
        findings = parser.parse(rows)

        assert len(findings) == 1
        assert findings[0].rule_id == "test/rule"
        assert findings[0].severity == Severity.HIGH
        assert findings[0].file_path == Path("test.py")
        assert findings[0].start_line == 10
        assert findings[0].end_line == 10

    def test_parse_missing_path(self) -> None:
        """Test parsing row without file path (should skip)."""
        rows = [
            {
                "name": "test/rule",
                "message": "Test",
                "severity": "medium",
                # Missing path
            }
        ]

        parser = CSVParser()
        findings = parser.parse(rows)

        assert len(findings) == 0  # Should skip row without path

    def test_parse_invalid_line_numbers(self) -> None:
        """Test parsing with invalid line numbers."""
        rows = [
            {
                "name": "test/rule",
                "path": "test.py",
                "start line": "invalid",
                "end line": "also-invalid",
                "message": "Test",
            }
        ]

        parser = CSVParser()
        findings = parser.parse(rows)

        # Should use default line numbers (1, 1)
        assert len(findings) == 1
        assert findings[0].start_line == 1
        assert findings[0].end_line == 1

    def test_parse_missing_rule_id(self) -> None:
        """Test parsing row without rule ID (should use fallback)."""
        rows = [
            {
                # No rule ID columns
                "path": "test.py",
                "message": "Test",
                "severity": "low",
                "start line": "5",
            }
        ]

        parser = CSVParser()
        findings = parser.parse(rows)

        assert len(findings) == 1
        # Should generate fallback rule ID
        assert findings[0].rule_id == "unknown-rule-0"

    def test_severity_parsing(self) -> None:
        """Test severity string parsing."""
        parser = CSVParser()

        # Test various severity strings
        assert parser._parse_severity("error") == Severity.HIGH
        assert parser._parse_severity("high") == Severity.HIGH
        assert parser._parse_severity("critical") == Severity.HIGH

        assert parser._parse_severity("warning") == Severity.MEDIUM
        assert parser._parse_severity("medium") == Severity.MEDIUM
        assert parser._parse_severity("moderate") == Severity.MEDIUM

        assert parser._parse_severity("note") == Severity.LOW
        assert parser._parse_severity("low") == Severity.LOW
        assert parser._parse_severity("recommendation") == Severity.LOW

        assert parser._parse_severity("info") == Severity.INFO
        assert parser._parse_severity("information") == Severity.INFO

        # Test unknown severity (should default to MEDIUM)
        assert parser._parse_severity("unknown") == Severity.MEDIUM

    def test_parse_file_success(
        self, sample_csv_rows: list[dict[str, str]], tmp_path: Path
    ) -> None:
        """Test parsing CSV from file."""
        csv_file = tmp_path / "results.csv"

        # Write CSV file
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            fieldnames = sample_csv_rows[0].keys()
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sample_csv_rows)

        parser = CSVParser()
        findings = parser.parse_file(csv_file)

        assert len(findings) == 2
        assert findings[0].rule_id == "py/sql-injection"
        assert findings[1].rule_id == "py/command-injection"

    def test_parse_file_not_exists(self, tmp_path: Path) -> None:
        """Test parsing non-existent file."""
        parser = CSVParser()
        nonexistent = tmp_path / "nonexistent.csv"

        with pytest.raises(ParserError, match="does not exist"):
            parser.parse_file(nonexistent)

    def test_parse_file_invalid_csv(self, tmp_path: Path) -> None:
        """Test parsing file that causes CSV error."""
        csv_file = tmp_path / "invalid.csv"
        # Write binary content that will cause encoding issues
        csv_file.write_bytes(b"\xff\xfe\x00\x00invalid")

        parser = CSVParser()

        with pytest.raises(ParserError):
            parser.parse_file(csv_file)

    def test_finding_id_generation(self, sample_csv_rows: list[dict[str, str]]) -> None:
        """Test finding ID generation."""
        parser = CSVParser()
        findings = parser.parse(sample_csv_rows)

        assert len(findings) == 2
        # ID format: {rule_id}_{filename}_{line}
        assert findings[0].id == "py/sql-injection_app.py_42"
        assert findings[1].id == "py/command-injection_utils.py_15"

    def test_parse_empty_csv(self) -> None:
        """Test parsing empty CSV."""
        parser = CSVParser()
        findings = parser.parse([])

        assert len(findings) == 0

    def test_csv_no_cwe_or_snippet(self, sample_csv_rows: list[dict[str, str]]) -> None:
        """Test that CSV parser doesn't populate CWE or snippet."""
        parser = CSVParser()
        findings = parser.parse(sample_csv_rows)

        # CSV format typically doesn't include CWE or snippet
        for finding in findings:
            assert finding.cwe is None
            assert finding.snippet is None
            assert finding.false_positive_score is None
