"""Tests for query models."""

from pathlib import Path

import pytest
from patchsmith.models.finding import Severity
from patchsmith.models.query import Query, QuerySuite


class TestQuery:
    """Tests for Query model."""

    def test_create_query(self) -> None:
        """Test creating a basic query."""
        query = Query(
            id="py/sql-injection",
            name="SQL Injection",
            description="Detects SQL injection vulnerabilities",
            path=Path("queries/sql-injection.ql"),
            language="python",
        )

        assert query.id == "py/sql-injection"
        assert query.name == "SQL Injection"
        assert query.language == "python"
        assert query.severity == Severity.MEDIUM  # Default
        assert query.is_custom is False  # Default

    def test_create_query_with_custom_severity(self) -> None:
        """Test creating query with custom severity."""
        query = Query(
            id="py/critical-vuln",
            name="Critical Vulnerability",
            path=Path("queries/critical.ql"),
            language="python",
            severity=Severity.CRITICAL,
        )

        assert query.severity == Severity.CRITICAL

    def test_create_custom_query(self) -> None:
        """Test creating a custom query."""
        query = Query(
            id="custom/my-check",
            name="My Custom Check",
            path=Path("custom-queries/my-check.ql"),
            language="python",
            is_custom=True,
        )

        assert query.is_custom is True

    def test_query_with_tags(self) -> None:
        """Test query with tags."""
        query = Query(
            id="py/xss",
            name="Cross-Site Scripting",
            path=Path("queries/xss.ql"),
            language="python",
            tags=["security", "cwe-79", "injection"],
        )

        assert len(query.tags) == 3
        assert "security" in query.tags
        assert "cwe-79" in query.tags

    def test_query_string_representation(self) -> None:
        """Test query string representation."""
        query = Query(
            id="py/test",
            name="Test Query",
            path=Path("test.ql"),
            language="python",
        )

        assert str(query) == "Test Query (py/test)"


class TestQuerySuite:
    """Tests for QuerySuite model."""

    @pytest.fixture
    def sample_queries(self) -> list[Query]:
        """Create sample queries for testing."""
        return [
            Query(
                id="py/sql-injection",
                name="SQL Injection",
                path=Path("queries/sql-injection.ql"),
                language="python",
                severity=Severity.CRITICAL,
            ),
            Query(
                id="py/xss",
                name="XSS",
                path=Path("queries/xss.ql"),
                language="python",
                severity=Severity.HIGH,
            ),
            Query(
                id="py/weak-crypto",
                name="Weak Cryptography",
                path=Path("queries/weak-crypto.ql"),
                language="python",
                severity=Severity.MEDIUM,
            ),
            Query(
                id="custom/my-check",
                name="My Custom Check",
                path=Path("custom/my-check.ql"),
                language="python",
                severity=Severity.HIGH,
                is_custom=True,
            ),
        ]

    def test_create_query_suite(self) -> None:
        """Test creating a query suite."""
        suite = QuerySuite(
            name="Python Security Suite",
            description="Security queries for Python",
            language="python",
        )

        assert suite.name == "Python Security Suite"
        assert suite.language == "python"
        assert len(suite.queries) == 0

    def test_create_suite_with_queries(self, sample_queries: list[Query]) -> None:
        """Test creating suite with initial queries."""
        suite = QuerySuite(
            name="Test Suite",
            queries=sample_queries,
        )

        assert len(suite) == 4
        assert len(suite.queries) == 4

    def test_add_query(self) -> None:
        """Test adding a query to suite."""
        suite = QuerySuite(name="Test Suite")

        query = Query(
            id="py/test",
            name="Test",
            path=Path("test.ql"),
            language="python",
        )

        suite.add_query(query)

        assert len(suite) == 1
        assert suite.queries[0] == query

    def test_get_by_severity(self, sample_queries: list[Query]) -> None:
        """Test filtering queries by severity."""
        suite = QuerySuite(name="Test Suite", queries=sample_queries)

        critical = suite.get_by_severity(Severity.CRITICAL)
        assert len(critical) == 1
        assert critical[0].id == "py/sql-injection"

        high = suite.get_by_severity(Severity.HIGH)
        assert len(high) == 2  # py/xss and custom/my-check

        low = suite.get_by_severity(Severity.LOW)
        assert len(low) == 0

    def test_get_custom_queries(self, sample_queries: list[Query]) -> None:
        """Test getting only custom queries."""
        suite = QuerySuite(name="Test Suite", queries=sample_queries)

        custom = suite.get_custom_queries()

        assert len(custom) == 1
        assert custom[0].id == "custom/my-check"
        assert custom[0].is_custom is True

    def test_get_standard_queries(self, sample_queries: list[Query]) -> None:
        """Test getting only standard queries."""
        suite = QuerySuite(name="Test Suite", queries=sample_queries)

        standard = suite.get_standard_queries()

        assert len(standard) == 3
        assert all(not q.is_custom for q in standard)

    def test_suite_length(self, sample_queries: list[Query]) -> None:
        """Test suite length operator."""
        suite = QuerySuite(name="Test Suite", queries=sample_queries)

        assert len(suite) == 4

        suite.add_query(
            Query(
                id="py/new",
                name="New Query",
                path=Path("new.ql"),
                language="python",
            )
        )

        assert len(suite) == 5

    def test_empty_suite(self) -> None:
        """Test empty query suite."""
        suite = QuerySuite(name="Empty Suite")

        assert len(suite) == 0
        assert suite.get_custom_queries() == []
        assert suite.get_standard_queries() == []
        assert suite.get_by_severity(Severity.HIGH) == []

    def test_language_specific_suite(self) -> None:
        """Test language-specific suite."""
        suite = QuerySuite(
            name="JavaScript Suite",
            language="javascript",
            description="JavaScript security queries",
        )

        assert suite.language == "javascript"
        assert suite.description == "JavaScript security queries"

    def test_multi_language_suite(self) -> None:
        """Test suite with queries from multiple languages."""
        queries = [
            Query(
                id="py/test",
                name="Python Test",
                path=Path("py.ql"),
                language="python",
            ),
            Query(
                id="js/test",
                name="JavaScript Test",
                path=Path("js.ql"),
                language="javascript",
            ),
        ]

        suite = QuerySuite(
            name="Multi-Language Suite",
            queries=queries,
        )

        assert len(suite) == 2
        assert suite.queries[0].language == "python"
        assert suite.queries[1].language == "javascript"
