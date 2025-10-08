"""Parsers for CodeQL result formats (SARIF, CSV, JSON)."""

import csv
import json
from pathlib import Path
from typing import Any, Optional

from patchsmith.models.finding import CWE, Finding, Severity
from patchsmith.utils.logging import get_logger

logger = get_logger()


class ParserError(Exception):
    """Parser operation failed."""

    pass


class SARIFParser:
    """Parser for SARIF (Static Analysis Results Interchange Format) files."""

    # SARIF severity level mapping to our Severity enum
    SEVERITY_MAP = {
        "error": Severity.HIGH,
        "warning": Severity.MEDIUM,
        "note": Severity.LOW,
        "none": Severity.INFO,
    }

    def parse_file(self, sarif_path: Path) -> list[Finding]:
        """
        Parse SARIF file and extract findings.

        Args:
            sarif_path: Path to SARIF file

        Returns:
            List of Finding objects

        Raises:
            ParserError: If parsing fails
        """
        if not sarif_path.exists():
            raise ParserError(f"SARIF file does not exist: {sarif_path}")

        try:
            with open(sarif_path) as f:
                sarif_data = json.load(f)

            findings = self.parse(sarif_data)

            logger.info(
                "sarif_parsed",
                file=str(sarif_path),
                findings_count=len(findings),
            )

            return findings

        except json.JSONDecodeError as e:
            raise ParserError(f"Invalid JSON in SARIF file: {e}") from e
        except Exception as e:
            raise ParserError(f"Failed to parse SARIF file: {e}") from e

    def parse(self, sarif_data: dict[str, Any]) -> list[Finding]:
        """
        Parse SARIF data structure and extract findings.

        Args:
            sarif_data: Parsed SARIF JSON data

        Returns:
            List of Finding objects

        Raises:
            ParserError: If SARIF structure is invalid
        """
        findings: list[Finding] = []

        try:
            # SARIF can have multiple runs (from different tools)
            runs = sarif_data.get("runs", [])

            for run in runs:
                run_findings = self._parse_run(run)
                findings.extend(run_findings)

            return findings

        except KeyError as e:
            raise ParserError(f"Invalid SARIF structure, missing key: {e}") from e

    def _parse_run(self, run: dict[str, Any]) -> list[Finding]:
        """
        Parse a single SARIF run.

        Args:
            run: SARIF run object

        Returns:
            List of findings from this run
        """
        findings: list[Finding] = []

        # Get rules for this run (for metadata like severity, CWE)
        rules = self._extract_rules(run)

        # Get results (actual findings)
        results = run.get("results", [])

        for idx, result in enumerate(results):
            try:
                finding = self._parse_result(result, rules, idx)
                if finding:
                    findings.append(finding)
            except Exception as e:
                logger.warning(
                    "sarif_result_parse_failed",
                    result_index=idx,
                    error=str(e),
                )
                # Continue parsing other results

        return findings

    def _extract_rules(self, run: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """
        Extract rule metadata from run.

        Args:
            run: SARIF run object

        Returns:
            Dictionary mapping rule ID to rule metadata
        """
        rules_dict: dict[str, dict[str, Any]] = {}

        tool = run.get("tool", {})
        driver = tool.get("driver", {})
        rules_list = driver.get("rules", [])

        for rule in rules_list:
            rule_id = rule.get("id")
            if rule_id:
                rules_dict[rule_id] = rule

        return rules_dict

    def _parse_result(
        self,
        result: dict[str, Any],
        rules: dict[str, dict[str, Any]],
        index: int,
    ) -> Optional[Finding]:
        """
        Parse a single SARIF result into a Finding.

        Args:
            result: SARIF result object
            rules: Rule metadata dictionary
            index: Result index (for generating ID)

        Returns:
            Finding object or None if parsing fails
        """
        # Get rule ID
        rule_id = result.get("ruleId")
        if not rule_id:
            logger.warning("sarif_result_missing_rule_id", index=index)
            return None

        # Get location information
        locations = result.get("locations", [])
        if not locations:
            logger.warning(
                "sarif_result_no_locations",
                rule_id=rule_id,
                index=index,
            )
            return None

        location = locations[0]  # Use first location
        physical_location = location.get("physicalLocation", {})
        artifact_location = physical_location.get("artifactLocation", {})
        region = physical_location.get("region", {})

        # Extract file path
        file_uri = artifact_location.get("uri", "")
        file_path = Path(file_uri)

        # Extract line numbers
        start_line = region.get("startLine", 1)
        end_line = region.get("endLine", start_line)

        # Get message
        message_obj = result.get("message", {})
        message = message_obj.get("text", "No description available")

        # Get code snippet (if available)
        snippet_obj = region.get("snippet", {})
        snippet = snippet_obj.get("text")

        # Get severity from result or rule
        severity = self._extract_severity(result, rules.get(rule_id, {}))

        # Get CWE information
        cwe = self._extract_cwe(rules.get(rule_id, {}))

        # Generate finding ID
        finding_id = f"{rule_id}_{file_path.name}_{start_line}"

        return Finding(
            id=finding_id,
            rule_id=rule_id,
            severity=severity,
            cwe=cwe,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            message=message,
            snippet=snippet,
            false_positive_score=None,  # Will be set later by FalsePositiveFilterAgent
        )

    def _extract_severity(
        self,
        result: dict[str, Any],
        rule: dict[str, Any],
    ) -> Severity:
        """
        Extract severity from result or rule metadata.

        Args:
            result: SARIF result object
            rule: Rule metadata

        Returns:
            Severity enum value
        """
        # Try result level first
        level = result.get("level")
        if level:
            return self.SEVERITY_MAP.get(level, Severity.MEDIUM)

        # Try rule default configuration
        default_config = rule.get("defaultConfiguration", {})
        level = default_config.get("level")
        if level:
            return self.SEVERITY_MAP.get(level, Severity.MEDIUM)

        # Try rule properties (CodeQL specific)
        properties = rule.get("properties", {})
        severity_str = properties.get("problem.severity", "").lower()

        # Map CodeQL severity strings
        if severity_str in ["error", "high"]:
            return Severity.HIGH
        elif severity_str in ["warning", "medium"]:
            return Severity.MEDIUM
        elif severity_str in ["recommendation", "low"]:
            return Severity.LOW

        # Default
        return Severity.MEDIUM

    def _extract_cwe(self, rule: dict[str, Any]) -> Optional[CWE]:
        """
        Extract CWE information from rule metadata.

        Args:
            rule: Rule metadata

        Returns:
            CWE object or None
        """
        properties = rule.get("properties", {})

        # Try CodeQL-specific CWE tags
        tags = properties.get("tags", [])
        for tag in tags:
            if tag.startswith("external/cwe/cwe-"):
                cwe_id = tag.replace("external/cwe/cwe-", "CWE-")
                return CWE(id=cwe_id, name=None)

        # Try security-severity (sometimes contains CWE reference)
        # This is less reliable but worth checking
        precision = properties.get("precision")
        if precision:  # If security-related, try to infer common CWEs
            # This is a fallback - actual CWE should come from tags
            pass

        return None


class CSVParser:
    """Parser for CodeQL CSV output format."""

    def parse_file(self, csv_path: Path) -> list[Finding]:
        """
        Parse CSV file and extract findings.

        Args:
            csv_path: Path to CSV file

        Returns:
            List of Finding objects

        Raises:
            ParserError: If parsing fails
        """
        if not csv_path.exists():
            raise ParserError(f"CSV file does not exist: {csv_path}")

        try:
            with open(csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                findings = self.parse(list(reader))

            logger.info(
                "csv_parsed",
                file=str(csv_path),
                findings_count=len(findings),
            )

            return findings

        except csv.Error as e:
            raise ParserError(f"Invalid CSV format: {e}") from e
        except Exception as e:
            raise ParserError(f"Failed to parse CSV file: {e}") from e

    def parse(self, rows: list[dict[str, str]]) -> list[Finding]:
        """
        Parse CSV rows and extract findings.

        Args:
            rows: List of CSV row dictionaries

        Returns:
            List of Finding objects
        """
        findings: list[Finding] = []

        for idx, row in enumerate(rows):
            try:
                finding = self._parse_row(row, idx)
                if finding:
                    findings.append(finding)
            except Exception as e:
                logger.warning(
                    "csv_row_parse_failed",
                    row_index=idx,
                    error=str(e),
                )
                # Continue parsing other rows

        return findings

    def _parse_row(self, row: dict[str, str], index: int) -> Optional[Finding]:
        """
        Parse a single CSV row into a Finding.

        CodeQL CSV format typically has columns like:
        - name: Rule name/ID
        - description: Finding message
        - severity: Severity level
        - message: Detailed message
        - path: File path
        - start line: Start line number
        - end line: End line number

        Args:
            row: CSV row dictionary
            index: Row index (for generating ID)

        Returns:
            Finding object or None if parsing fails
        """
        # Extract rule ID (try multiple column names)
        rule_id = (
            row.get("name")
            or row.get("Rule")
            or row.get("rule")
            or row.get("query")
            or f"unknown-rule-{index}"
        )

        # Extract file path (try multiple column names)
        file_path_str = (
            row.get("path") or row.get("file") or row.get("File") or ""
        )
        if not file_path_str:
            logger.warning("csv_row_missing_path", row_index=index, rule=rule_id)
            return None

        file_path = Path(file_path_str)

        # Extract line numbers (try multiple column names)
        try:
            start_line = int(
                row.get("start line")
                or row.get("startLine")
                or row.get("line")
                or row.get("Line")
                or "1"
            )
            end_line = int(
                row.get("end line")
                or row.get("endLine")
                or row.get("start line")
                or row.get("startLine")
                or row.get("line")
                or row.get("Line")
                or str(start_line)
            )
        except ValueError:
            logger.warning(
                "csv_row_invalid_line_numbers", row_index=index, rule=rule_id
            )
            start_line = 1
            end_line = 1

        # Extract message (try multiple column names)
        message = (
            row.get("message")
            or row.get("description")
            or row.get("Description")
            or row.get("Message")
            or "No description available"
        )

        # Extract severity (try multiple column names)
        severity_str = (
            row.get("severity")
            or row.get("Severity")
            or row.get("level")
            or "medium"
        ).lower()

        # Map severity
        severity = self._parse_severity(severity_str)

        # Generate finding ID
        finding_id = f"{rule_id}_{file_path.name}_{start_line}"

        return Finding(
            id=finding_id,
            rule_id=rule_id,
            severity=severity,
            cwe=None,  # CSV format typically doesn't include CWE
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            message=message,
            snippet=None,  # CSV format typically doesn't include snippets
            false_positive_score=None,
        )

    def _parse_severity(self, severity_str: str) -> Severity:
        """
        Parse severity string to Severity enum.

        Args:
            severity_str: Severity string from CSV

        Returns:
            Severity enum value
        """
        severity_lower = severity_str.lower()

        if severity_lower in ["error", "high", "critical"]:
            return Severity.HIGH
        elif severity_lower in ["warning", "medium", "moderate"]:
            return Severity.MEDIUM
        elif severity_lower in ["note", "low", "recommendation"]:
            return Severity.LOW
        elif severity_lower in ["info", "information"]:
            return Severity.INFO
        else:
            # Default to medium for unknown severities
            return Severity.MEDIUM
