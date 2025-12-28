import os

from .executor import (
    execute_tool,
    execute_tool_invocation,
    execute_tool_with_validation,
    extract_screenshot_from_result,
    process_tool_invocations,
    remove_screenshot_from_result,
    validate_tool_availability,
)
from .registry import (
    ImplementedInClientSideOnlyError,
    get_tool_by_name,
    get_tool_names,
    get_tools_prompt,
    needs_agent_state,
    register_tool,
    tools,
)


SANDBOX_MODE = os.getenv("STRIX_SANDBOX_MODE", "false").lower() == "true"

HAS_PERPLEXITY_API = bool(os.getenv("PERPLEXITY_API_KEY"))

DISABLE_BROWSER = os.getenv("STRIX_DISABLE_BROWSER", "false").lower() == "true"

if not SANDBOX_MODE:
    from .agents_graph import *  # noqa: F403

    if not DISABLE_BROWSER:
        from .browser import *  # noqa: F403
    from .file_edit import *  # noqa: F403
    from .finish import *  # noqa: F403
    from .notes import *  # noqa: F403
    from .proxy import *  # noqa: F403
    from .python import *  # noqa: F403
    from .reporting import *  # noqa: F403
    from .terminal import *  # noqa: F403
    from .thinking import *  # noqa: F403
    from .todo import *  # noqa: F403
    
    # New enhanced modules
    from .root_terminal import *  # noqa: F403
    from .custom_agents import *  # noqa: F403
    from .knowledge import *  # noqa: F403
    from .orchestration import *  # noqa: F403
    
    # CVE/Exploit Database Integration
    from .cve_database import *  # noqa: F403
    
    # Multi-Agent Collaboration Protocol
    from .collaboration import *  # noqa: F403
    
    # StrixDB - Permanent GitHub Knowledge Repository
    from .strixdb import *  # noqa: F403

    # Web Search - Multiple providers with automatic fallback
    # Always available (DuckDuckGo as free fallback, premium providers if API keys set)
    from .web_search import *  # noqa: F403
else:
    if not DISABLE_BROWSER:
        from .browser import *  # noqa: F403
    from .file_edit import *  # noqa: F403
    from .proxy import *  # noqa: F403
    from .python import *  # noqa: F403
    from .terminal import *  # noqa: F403
    from .root_terminal import *  # noqa: F403

__all__ = [
    "ImplementedInClientSideOnlyError",
    "execute_tool",
    "execute_tool_invocation",
    "execute_tool_with_validation",
    "extract_screenshot_from_result",
    "get_tool_by_name",
    "get_tool_names",
    "get_tools_prompt",
    "needs_agent_state",
    "process_tool_invocations",
    "register_tool",
    "remove_screenshot_from_result",
    "tools",
    "validate_tool_availability",
]
