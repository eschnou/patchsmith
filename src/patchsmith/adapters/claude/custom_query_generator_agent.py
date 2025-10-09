"""Custom CodeQL query generator agent for project-specific queries."""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, create_sdk_mcp_server, tool

from patchsmith.adapters.claude.agent import AgentError, BaseAgent
from patchsmith.models.finding import Severity
from patchsmith.utils.logging import get_logger

if TYPE_CHECKING:
    from patchsmith.adapters.codeql.cli import CodeQLCLI

logger = get_logger()


class CustomQueryGeneratorAgent(BaseAgent):
    """Agent for generating custom CodeQL queries using Claude AI.

    This agent creates project-specific CodeQL queries based on:
    - Programming language and frameworks
    - Architectural patterns
    - Specific vulnerability types or risks
    - Project context and domain

    Unlike QueryGeneratorAgent (which recommends standard queries),
    this agent generates complete .ql file content from scratch.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize query generator agent with result storage."""
        super().__init__(*args, **kwargs)
        self._query_content: str | None = None
        self._query_id: str | None = None

    def _create_submit_tool(self) -> Any:
        """Create submit_query tool with closure to access instance state.

        Returns:
            Tool function that can access self._query_content and self._query_id
        """
        # Capture self in closure
        agent_instance = self

        @tool(
            "submit_query",
            "Submit the generated CodeQL query",
            {
                "query_id": str,  # Query ID (e.g., "custom/postmessage-validation")
                "query_content": str,  # Complete .ql file content
            },
        )
        async def submit_query_tool(args: dict) -> dict:
            """Tool for submitting generated query."""
            query_id = args.get("query_id", "")
            query_content = args.get("query_content", "")

            # Store in instance variable
            agent_instance._query_id = query_id
            agent_instance._query_content = query_content

            logger.info(
                "query_submitted",
                query_id=query_id,
                content_length=len(query_content),
            )

            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Successfully recorded query: {query_id} ({len(query_content)} bytes)",
                    }
                ]
            }

        return submit_query_tool

    def get_system_prompt(self) -> str:
        """Get system prompt for custom query generation."""
        return """You are a CodeQL query writing expert who creates custom security queries using MODERN CodeQL APIs.

CRITICAL: USE MODERN API (CodeQL 2.13.0+)
The old API using "class Configuration extends TaintTracking::Configuration" is DEPRECATED.
You MUST use the modern modular API shown below to avoid deprecation warnings.

Your expertise includes:
- Modern CodeQL API (ConfigSig, Global modules)
- Security vulnerability patterns across languages
- Project-specific architectural risks
- Writing queries that compile without warnings

MODERN API PATTERN (Path/Taint-Tracking Problems):
```ql
/**
 * @name SQL injection
 * @description User input flows to SQL query without sanitization
 * @kind path-problem
 * @id custom/sql-injection
 * @problem.severity error
 * @tags security external/cwe/cwe-089
 */

import javascript

module SqlInjectionConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) {
    // Sources: HTTP request parameters
    exists(HTTP::RequestInputAccess input |
      source = input.getANode()
    )
  }

  predicate isSink(DataFlow::Node sink) {
    // Sinks: SQL query strings
    exists(SQL::SqlString sql |
      sink = sql.getAnArgument()
    )
  }
}

module SqlInjectionFlow = TaintTracking::Global<SqlInjectionConfig>;
import SqlInjectionFlow::PathGraph

from SqlInjectionFlow::PathNode source, SqlInjectionFlow::PathNode sink
where SqlInjectionFlow::flowPath(source, sink)
select sink.getNode(), source, sink,
  "SQL query depends on $@.", source.getNode(), "user input"
```

MODERN API PATTERN (Simple Problems - use when data flow is too complex):
```ql
/**
 * @name Dangerous eval usage
 * @description Direct use of eval with string concatenation
 * @kind problem
 * @id custom/dangerous-eval
 * @problem.severity warning
 * @tags security
 */

import javascript

from CallExpr call
where
  call.getCalleeName() = "eval" and
  call.getNumArgument() > 0
select call, "Dangerous use of eval() detected"
```

KEY DIFFERENCES FROM OLD API:
❌ OLD: class MyConfig extends TaintTracking::Configuration
✅ NEW: module MyConfig implements DataFlow::ConfigSig

❌ OLD: import DataFlow::PathGraph
✅ NEW: import MyFlow::PathGraph

❌ OLD: override predicate isSanitizer
✅ NEW: predicate isBarrier

❌ OLD: DataFlow::PathNode
✅ NEW: MyFlow::PathNode

❌ OLD: cfg.hasFlowPath(source, sink)
✅ NEW: MyFlow::flowPath(source, sink)

AVAILABLE TOOLS:
You have access to tools to research and understand the project:
- Read: Read source files to understand code patterns and frameworks used
- Glob: Find files in the project (e.g., "**/*.py", "src/**/*.ts")
- Grep: Search for specific code patterns or vulnerability examples
- WebFetch: Look up CodeQL documentation and example queries
- WebSearch: Search for vulnerability patterns and detection techniques
- submit_query: Submit your generated query (YOU MUST call this with query_id and query_content)

RECOMMENDED WORKFLOW:
1. Use Glob to understand project structure and identify key files
2. Use Read to examine actual code patterns, imports, and frameworks
3. **IMPORTANT**: Use WebFetch/WebSearch to find working CodeQL examples:
   - Search GitHub: "site:github.com codeql {language} {vulnerability-type} .ql"
   - Look up official docs: "codeql {language} library documentation"
   - Find similar queries: "codeql {language} taint tracking example"
4. Design sources, sinks, and barriers based on actual project code AND working examples
5. Generate the query using PROVEN syntax from examples
6. Call submit_query with query_id and complete query_content

COMMON MISTAKES TO AVOID:
- ❌ Making up types (e.g., DomManipulation, BarrierGuard) - use only types from CodeQL libraries
- ❌ Wrong import order - PathGraph import must be AFTER module definition
- ❌ Variable name mismatches - source/sink in from must match where clause
- ❌ Overly complex queries - start simple, add complexity only after compilation succeeds
- ❌ Not researching working examples - ALWAYS WebFetch examples before writing

SUBMISSION FORMAT:
Call submit_query tool with:
- query_id: Unique ID like "custom/postmessage-validation" or "custom/js-xss-dom"
- query_content: Complete .ql file content (including metadata comments, imports, query)

Example:
```
submit_query({
  "query_id": "custom/postmessage-validation",
  "query_content": "/**\\n * @name Insufficient postMessage origin validation\\n * @description...\\n */\\n\\nimport javascript\\n..."
})
```

REQUIREMENTS:
1. Use MODERN API (modules, not classes)
2. Include complete metadata comments (@name, @description, @kind, @id, @severity, @tags)
3. Ensure query compiles without errors
4. Target specific security issues relevant to the project
5. Submit via submit_query tool (NOT as text output)"""

    async def execute(  # type: ignore[override]
        self,
        language: str,
        project_context: str,
        vulnerability_type: str,
        severity: Severity = Severity.HIGH,
        codeql_cli: "CodeQLCLI | None" = None,
        pack_dir: "Path | None" = None,
        max_retries: int = 3,
    ) -> tuple[str, str]:
        """
        Generate a custom CodeQL query.

        Args:
            language: Target language (python, javascript, java, etc.)
            project_context: Description of project architecture, frameworks, patterns
            vulnerability_type: Specific vulnerability to detect (e.g., "SQL injection in ORM")
            severity: Query severity level
            codeql_cli: CodeQL CLI for query compilation validation (optional)
            pack_dir: Directory with qlpack.yml for compilation (optional, uses temp if None)
            max_retries: Maximum compilation retry attempts

        Returns:
            Tuple of (query_id, query_content)

        Raises:
            AgentError: If generation fails
        """
        logger.info(
            "custom_query_generation_started",
            agent=self.agent_name,
            language=language,
            vulnerability_type=vulnerability_type,
            severity=severity.value,
        )

        compilation_errors: str | None = None
        failed_query_path: Path | None = None
        attempt = 0

        try:
            while attempt <= max_retries:
                # Reset instance state
                self._query_content = None
                self._query_id = None

                # Build generation prompt
                prompt = self._build_generation_prompt(
                    language=language,
                    project_context=project_context,
                    vulnerability_type=vulnerability_type,
                    severity=severity,
                    compilation_errors=compilation_errors,
                    failed_query_path=failed_query_path,
                )

                # Create MCP server with custom tool
                submit_tool = self._create_submit_tool()
                server = create_sdk_mcp_server(
                    name="query-generator",
                    version="1.0.0",
                    tools=[submit_tool],
                )

                # Query Claude with tools for research and exploration
                options = ClaudeAgentOptions(
                    system_prompt=self.get_system_prompt(),
                    max_turns=50,  # Allow agent to explore and iterate
                    allowed_tools=[
                        "Read",      # Read codebase files to understand patterns
                        "Glob",      # Find relevant files in the project
                        "Grep",      # Search for vulnerability patterns
                        "WebFetch",  # Look up CodeQL docs and examples
                        "WebSearch", # Search for query patterns and techniques
                        "mcp__query-generator__submit_query",  # Submit generated query
                    ],
                    mcp_servers={"query-generator": server},
                    cwd=str(self.working_dir),
                )

                turn_count = 0

                async with ClaudeSDKClient(options=options) as client:
                    await client.query(prompt)

                    async for message in client.receive_response():
                        message_type = type(message).__name__

                        # Track turns for progress
                        if message_type == "AssistantMessage":
                            turn_count += 1
                            if self.progress_callback:
                                self.progress_callback(turn_count, options.max_turns)

                        # Extract and emit thinking updates
                        thinking = self._extract_thinking_from_message(message)
                        if thinking:
                            self._emit_thinking(thinking)

                # Check if tool was called
                if self._query_content is None or self._query_id is None:
                    raise AgentError(
                        "Agent did not call submit_query tool - check max_turns or prompt"
                    )

                query_content = self._query_content
                query_id = self._query_id

                # Validate with CodeQL if CLI provided
                if codeql_cli and attempt <= max_retries:
                    # Save query for compilation
                    if pack_dir:
                        # Save to pack directory (proper QL pack)
                        query_filename = (
                            query_id.replace("custom/", "")
                            .replace(f"{language}/", "")
                            .replace("/", "_")
                            + ".ql"
                        )
                        query_path = pack_dir / query_filename
                        query_path.write_text(query_content)
                    else:
                        # Use temp directory with qlpack.yml (for testing)
                        import tempfile

                        temp_dir = Path(tempfile.mkdtemp())
                        try:
                            # Create minimal QL pack structure
                            codeql_cli.create_ql_pack(temp_dir, language)
                            codeql_cli.install_pack_dependencies(temp_dir)
                        except Exception as pack_error:
                            logger.warning(
                                "temp_pack_setup_failed",
                                error=str(pack_error),
                            )
                            # Continue without pack structure

                        query_path = temp_dir / "query.ql"
                        query_path.write_text(query_content)

                    try:
                        success, error_msg = codeql_cli.compile_query(
                            query_path, check_only=True
                        )

                        if not success:
                            logger.warning(
                                "custom_query_compilation_failed",
                                agent=self.agent_name,
                                attempt=attempt + 1,
                                error=error_msg[:300],
                            )
                            compilation_errors = error_msg
                            failed_query_path = query_path  # Store path for retry
                            attempt += 1

                            if attempt <= max_retries:
                                logger.info(
                                    "custom_query_generation_retry",
                                    agent=self.agent_name,
                                    attempt=attempt,
                                )
                                continue
                            else:
                                # Max retries exceeded
                                logger.error(
                                    "custom_query_max_retries",
                                    agent=self.agent_name,
                                    attempts=attempt,
                                )
                                raise AgentError(
                                    f"Query generation failed after {attempt} attempts. "
                                    f"Last compilation error: {error_msg[:200]}"
                                )
                    finally:
                        # Only clean up if we're done with all retries
                        if attempt > max_retries or success:
                            # Clean up temp file/directory if not using pack_dir
                            if not pack_dir:
                                import shutil

                                if query_path.parent.name and query_path.parent != Path(
                                    "/"
                                ):
                                    shutil.rmtree(query_path.parent, ignore_errors=True)
                            # If using pack_dir and compilation failed, remove the failed query
                            elif not success:
                                query_path.unlink(missing_ok=True)

                # Success - validation passed or disabled
                logger.info(
                    "custom_query_generation_completed",
                    agent=self.agent_name,
                    query_id=query_id,
                    attempts=attempt + 1,
                )
                return (query_id, query_content)

            # Should not reach here, but just in case
            raise AgentError(
                f"Query generation failed after {attempt} attempts"
            )

        except AgentError:
            raise
        except Exception as e:
            logger.error(
                "custom_query_generation_failed",
                agent=self.agent_name,
                error=str(e),
            )
            raise AgentError(f"Custom query generation failed: {e}") from e

    def _build_generation_prompt(
        self,
        language: str,
        project_context: str,
        vulnerability_type: str,
        severity: Severity,
        compilation_errors: str | None = None,
        failed_query_path: Path | None = None,
    ) -> str:
        """
        Build prompt for custom query generation.

        Args:
            language: Target language
            project_context: Project architecture and patterns
            vulnerability_type: Vulnerability to detect
            severity: Query severity level
            compilation_errors: Previous compilation errors (for retries)
            failed_query_path: Path to failed query file (for retries)

        Returns:
            Generation prompt
        """
        error_text = ""
        if compilation_errors and failed_query_path:
            error_text = f"""

⚠️ PREVIOUS COMPILATION FAILED WITH ERRORS:
{compilation_errors}

FAILED QUERY LOCATION: {failed_query_path}

INSTRUCTIONS FOR FIXING:
1. Use the Read tool to read the failed query at: {failed_query_path}
2. Use WebFetch to look up the correct CodeQL API for {language}
   - Search for "codeql {language} data flow configuration"
   - Look for working examples on GitHub: "site:github.com codeql {language} taint tracking"
3. Common issues to check in the failed query:
   - Are you using modern API (module implements ConfigSig) not deprecated classes?
   - Are import statements correct? (e.g., "import javascript" not "import Javascript")
   - Do the types exist? (e.g., DataFlow::Node, not made-up types)
   - Is the PathGraph import after module definition?
   - Are variable names consistent in from/where/select?
4. Generate a SIMPLER query if the complex one keeps failing
   - Start with basic pattern matching (kind: problem) not data flow
   - Add complexity only after basic query compiles

Read the failed query, research the correct syntax, then regenerate and submit via submit_query tool.
"""

        return f"""Generate a custom CodeQL security query with the following requirements:

TARGET LANGUAGE: {language}
VULNERABILITY TYPE: {vulnerability_type}
SEVERITY: {severity.value}

PROJECT CONTEXT:
{project_context}

TASK:
1. Research the project to understand relevant code patterns and frameworks
2. Generate a complete, compilable CodeQL query (.ql file) that detects this specific vulnerability
3. Submit the query using the submit_query tool

The query should:
1. Include all required metadata (@name, @description, @kind, @id, @severity, @tags)
2. Import appropriate CodeQL libraries for {language}
3. Use MODERN API (modules, not classes)
4. Define predicates or modules as needed
5. Implement the detection logic (from/where/select)
6. Be syntactically correct and ready to compile
7. Be specific to the project context provided

After generating the query, call submit_query with:
- query_id: A unique ID like "custom/{language}-postmessage-validation"
- query_content: The complete .ql file content (as a string)

{error_text}"""

    def _parse_response(self, response: str) -> str:
        """DEPRECATED: Parse response to extract query content.

        This method is no longer used since we now use the submit_query MCP tool.
        Kept for backward compatibility only.

        Args:
            response: Claude's response text

        Returns:
            Query content (.ql file text)

        Raises:
            AgentError: If parsing fails
        """
        # Remove markdown code fences if present
        content = response.strip()

        # Remove ```ql or ``` fences
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first line (```ql or ```)
            lines = lines[1:]
            # Remove last line if it's ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)

        # Validate it looks like a CodeQL query
        if "/**" not in content or "@name" not in content:
            raise AgentError(
                "Generated content does not appear to be a valid CodeQL query "
                "(missing metadata)"
            )

        if "select" not in content.lower():
            raise AgentError(
                "Generated content does not appear to be a valid CodeQL query "
                "(missing select statement)"
            )

        return content.strip()

    def _extract_query_id(self, query_content: str, language: str) -> str:
        """DEPRECATED: Extract query ID from query content.

        This method is no longer used since we now get query_id directly
        from the submit_query MCP tool. Kept for backward compatibility only.

        Args:
            query_content: Query content
            language: Target language

        Returns:
            Query ID (e.g., "custom/sql-injection-orm")
        """
        # Try to find @id in metadata
        for line in query_content.split("\n"):
            line = line.strip()
            if line.startswith("* @id"):
                # Extract ID after @id
                parts = line.split("@id", 1)
                if len(parts) == 2:
                    query_id = parts[1].strip()
                    return query_id

        # Fallback: generate ID from content
        # Look for @name as fallback
        for line in query_content.split("\n"):
            line = line.strip()
            if line.startswith("* @name"):
                parts = line.split("@name", 1)
                if len(parts) == 2:
                    name = parts[1].strip()
                    # Convert name to ID format
                    query_id = name.lower().replace(" ", "-").replace("/", "-")
                    return f"custom/{language}/{query_id}"

        # Last resort: generate generic ID
        import hashlib

        hash_short = hashlib.md5(query_content.encode()).hexdigest()[:8]
        return f"custom/{language}/query-{hash_short}"
