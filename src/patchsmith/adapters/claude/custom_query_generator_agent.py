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
        self._query_path: str | None = None
        self._query_id: str | None = None
        self.codeql_cli: "CodeQLCLI | None" = None
        self.pack_dir: Path | None = None

    def _create_write_query_tool(self) -> Any:
        """Create write_query tool with path validation.

        Returns:
            Tool function that writes queries with path restrictions
        """
        agent_instance = self

        @tool(
            "write_query",
            "Write a CodeQL query file to the queries directory",
            {
                "filename": str,  # Query filename (e.g., "postmessage-validation.ql")
                "content": str,   # Complete .ql file content
            },
        )
        async def write_query_tool(args: dict) -> dict:
            """Tool for writing query files with validation."""
            filename = args.get("filename", "")
            content = args.get("content", "")

            # Validate filename (no path traversal)
            if not filename or ".." in filename or "/" in filename or "\\" in filename:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error: Invalid filename '{filename}'. Use simple filename like 'my-query.ql'",
                        }
                    ]
                }

            # Ensure .ql extension
            if not filename.endswith(".ql"):
                filename += ".ql"

            # Write to pack directory
            if not agent_instance.pack_dir:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": "Error: Pack directory not configured",
                        }
                    ]
                }

            query_path = agent_instance.pack_dir / filename
            query_path.write_text(content)

            logger.info(
                "query_written",
                filename=filename,
                path=str(query_path),
                content_length=len(content),
            )

            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Successfully wrote query to: {query_path}",
                    }
                ]
            }

        return write_query_tool

    def _create_compile_query_tool(self) -> Any:
        """Create compile_query tool for validation.

        Returns:
            Tool function that compiles queries and returns errors
        """
        agent_instance = self

        @tool(
            "compile_query",
            "Compile a CodeQL query to check for syntax errors",
            {
                "query_path": str,  # Path to query file to compile
            },
        )
        async def compile_query_tool(args: dict) -> dict:
            """Tool for compiling queries."""
            query_path_str = args.get("query_path", "")
            query_path = Path(query_path_str)

            if not agent_instance.codeql_cli:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": "Error: CodeQL CLI not configured",
                        }
                    ]
                }

            if not query_path.exists():
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error: Query file not found: {query_path}",
                        }
                    ]
                }

            # Compile query
            success, error_msg = agent_instance.codeql_cli.compile_query(
                query_path, check_only=True
            )

            logger.info(
                "query_compiled",
                path=str(query_path),
                success=success,
                error=error_msg[:200] if error_msg else None,
            )

            if success:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"✓ Query compiled successfully: {query_path}",
                        }
                    ]
                }
            else:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"✗ Compilation failed:\n{error_msg}",
                        }
                    ]
                }

        return compile_query_tool

    def _create_submit_tool(self) -> Any:
        """Create submit_query tool with closure to access instance state.

        Returns:
            Tool function that can access self._query_path and self._query_id
        """
        # Capture self in closure
        agent_instance = self

        @tool(
            "submit_query",
            "Submit the path to the verified working query",
            {
                "query_id": str,  # Query ID (e.g., "custom/postmessage-validation")
                "query_path": str,  # Path to compiled query file
            },
        )
        async def submit_query_tool(args: dict) -> dict:
            """Tool for submitting verified query path."""
            query_id = args.get("query_id", "")
            query_path = args.get("query_path", "")

            # Store in instance variable
            agent_instance._query_id = query_id
            agent_instance._query_path = query_path

            logger.info(
                "query_submitted",
                query_id=query_id,
                query_path=query_path,
            )

            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Successfully recorded query: {query_id} at {query_path}",
                    }
                ]
            }

        return submit_query_tool

    def get_system_prompt(self) -> str:
        """Get system prompt for custom query generation."""
        return """You are a CodeQL query writing expert who creates custom security queries using MODERN CodeQL APIs.

You are autonomous and control your own iteration loop. You will write queries, compile them, debug errors, and iterate until you produce a working query.

PERSONALITY & APPROACH:
- Methodical: Research working examples before writing code
- Iterative: Compile early and often, fix errors incrementally
- Evidence-based: Base queries on actual project code patterns
- Modern: Use only current CodeQL APIs, never deprecated patterns

CRITICAL: USE MODERN API (CodeQL 2.13.0+)
The old API using "class Configuration extends TaintTracking::Configuration" is DEPRECATED.
You MUST use the modern modular API shown below to avoid deprecation warnings.

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

Research & Analysis:
- Read: Read source files to understand code patterns and frameworks
- Glob: Find files matching patterns (e.g., "**/*.py", "src/**/*.ts")
- Grep: Search for specific code patterns or vulnerability examples
- WebFetch: Look up CodeQL documentation and working query examples
- WebSearch: Search for vulnerability patterns and detection techniques

Query Development:
- write_query: Write a query file to disk (filename, content)
  * Validates filename (no path traversal)
  * Writes to queries directory
  * Returns path for compilation
- compile_query: Compile a query to check for errors (query_path)
  * Returns success/failure with error messages
  * Use this to validate before submitting
- submit_query: Submit final verified query (query_id, query_path)
  * Only call after successful compilation
  * Marks query as complete

AUTONOMOUS WORKFLOW (you control this loop):

1. **Research Phase**:
   - Use Glob to understand project structure
   - Use Read to examine code patterns, imports, frameworks
   - Use Grep to find security-relevant patterns
   - **CRITICAL**: Use WebFetch/WebSearch to find working CodeQL examples:
     * Search GitHub: "site:github.com codeql {language} {vulnerability} .ql"
     * Look up docs: "codeql {language} library documentation"
     * Find examples: "codeql {language} taint tracking example"
   - Understand what types and predicates are actually available

2. **Write Phase**:
   - Create query based on research and working examples
   - Include complete metadata (@name, @description, @kind, @id, @severity, @tags)
   - Use modern CodeQL API (modules, not classes)
   - Call write_query tool with filename and complete content

3. **Compile Phase**:
   - Call compile_query with the path from write_query
   - Check if compilation succeeded or returned errors

4. **Debug & Iterate Phase** (if compilation failed):
   - Read your query file to see what you wrote
   - Analyze the error messages
   - Research correct syntax with WebFetch/WebSearch
   - Common issues to check:
     * Did you invent types that don't exist? (DomManipulation, BarrierGuard, etc.)
     * Is PathGraph import after module definition?
     * Are variable names consistent in from/where/select?
     * Are you using deprecated class-based API?
   - Write a FIXED version (overwrite same filename)
   - OR write a SIMPLER query if complex approach keeps failing
   - Compile again
   - Repeat until compilation succeeds

5. **Submit Phase**:
   - Once compile_query returns success, call submit_query
   - Provide query_id and query_path
   - This marks the query as complete

COMMON MISTAKES TO AVOID:
- ❌ Making up types (e.g., DomManipulation, BarrierGuard) - use only real CodeQL library types
- ❌ Wrong import order - PathGraph import must be AFTER module definition
- ❌ Variable name mismatches - source/sink in from must match where clause
- ❌ Using deprecated class-based API - use modern modules
- ❌ Overly complex queries - start simple, add complexity after basic version compiles
- ❌ Not researching examples - ALWAYS WebFetch working examples before writing
- ❌ Not compiling before submitting - ALWAYS verify with compile_query first

QUALITY REQUIREMENTS:
- Query MUST compile without errors (verified by compile_query)
- Use modern CodeQL API (modules implementing ConfigSig)
- Include complete metadata comments
- Be specific to the target vulnerability and project context
- Based on real CodeQL library types and predicates (not invented)

Take your time to research, iterate, and debug. Your goal is a working, compiled query."""

    async def execute(  # type: ignore[override]
        self,
        language: str,
        project_context: str,
        vulnerability_type: str,
        severity: Severity = Severity.HIGH,
        codeql_cli: "CodeQLCLI | None" = None,
        pack_dir: "Path | None" = None,
    ) -> tuple[str, str]:
        """
        Generate a custom CodeQL query using autonomous agent-driven iteration.

        The agent will:
        1. Research the project and CodeQL patterns
        2. Write query files using write_query tool
        3. Compile using compile_query tool
        4. Debug and iterate until compilation succeeds
        5. Submit final verified query path

        Args:
            language: Target language (python, javascript, java, etc.)
            project_context: Description of project architecture, frameworks, patterns
            vulnerability_type: Specific vulnerability to detect (e.g., "SQL injection in ORM")
            severity: Query severity level
            codeql_cli: CodeQL CLI for query compilation (required)
            pack_dir: Directory with qlpack.yml for writing queries (required)

        Returns:
            Tuple of (query_id, query_path)

        Raises:
            AgentError: If generation fails or agent doesn't submit
        """
        logger.info(
            "custom_query_generation_started",
            agent=self.agent_name,
            language=language,
            vulnerability_type=vulnerability_type,
            severity=severity.value,
        )

        # Store dependencies for tool access
        self.codeql_cli = codeql_cli
        self.pack_dir = pack_dir

        # Reset instance state
        self._query_path = None
        self._query_id = None

        try:
            # Build generation prompt
            prompt = self._build_generation_prompt(
                language=language,
                project_context=project_context,
                vulnerability_type=vulnerability_type,
                severity=severity,
            )

            # Create MCP server with all tools
            write_tool = self._create_write_query_tool()
            compile_tool = self._create_compile_query_tool()
            submit_tool = self._create_submit_tool()
            server = create_sdk_mcp_server(
                name="query-generator",
                version="1.0.0",
                tools=[write_tool, compile_tool, submit_tool],
            )

            # Query Claude with tools for autonomous iteration
            options = ClaudeAgentOptions(
                system_prompt=self.get_system_prompt(),
                max_turns=100,  # Allow agent to explore, iterate, and debug
                allowed_tools=[
                    "Read",      # Read codebase files to understand patterns
                    "Glob",      # Find relevant files in the project
                    "Grep",      # Search for vulnerability patterns
                    "WebFetch",  # Look up CodeQL docs and examples
                    "WebSearch", # Search for query patterns and techniques
                    "mcp__query-generator__write_query",   # Write query files
                    "mcp__query-generator__compile_query", # Compile and get errors
                    "mcp__query-generator__submit_query",  # Submit final verified query
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

            # Check if agent submitted query
            if self._query_path is None or self._query_id is None:
                raise AgentError(
                    "Agent did not call submit_query tool - check max_turns or prompt"
                )

            query_path = self._query_path
            query_id = self._query_id

            # Read query content from file for return
            query_content = Path(query_path).read_text()

            logger.info(
                "custom_query_generation_completed",
                agent=self.agent_name,
                query_id=query_id,
                query_path=query_path,
            )
            return (query_id, query_content)

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
    ) -> str:
        """
        Build minimal user prompt with specific task parameters.

        Args:
            language: Target language
            project_context: Project architecture and patterns
            vulnerability_type: Vulnerability to detect
            severity: Query severity level

        Returns:
            Task-specific prompt
        """
        return f"""Create a custom CodeQL security query for this specific vulnerability:

TARGET LANGUAGE: {language}
VULNERABILITY TYPE: {vulnerability_type}
SEVERITY: {severity.value}

PROJECT CONTEXT:
{project_context}

Follow your autonomous workflow to research, write, compile, debug, and submit a working query."""

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
