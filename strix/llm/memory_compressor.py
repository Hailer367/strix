"""
Memory Compressor for Strix Agent

Handles conversation history compression to stay within LLM token limits.
Designed for GitHub Actions CI/CD environment where memory efficiency is critical.

Key Features:
- Smart token counting with fallback estimation
- Priority-based message retention (findings > tool outputs > general)
- Incremental compression to avoid losing critical security context
- Image handling to reduce token usage
- Security-context aware summarization
- Adaptive compression strategies based on memory_strategy setting
"""

import hashlib
import logging
import os
import re
from typing import Any

import litellm


logger = logging.getLogger(__name__)


# Token limits - configurable via environment
MAX_TOTAL_TOKENS = int(os.getenv("STRIX_MAX_TOKENS", "100000"))
MIN_RECENT_MESSAGES = int(os.getenv("STRIX_MIN_RECENT_MESSAGES", "15"))

# Compression thresholds
COMPRESSION_TRIGGER_RATIO = float(os.getenv("STRIX_COMPRESSION_TRIGGER", "0.85"))  # Trigger at 85%
AGGRESSIVE_COMPRESSION_RATIO = float(os.getenv("STRIX_AGGRESSIVE_COMPRESS", "0.95"))  # Emergency at 95%

# Priority patterns for message retention (higher priority = kept longer)
HIGH_PRIORITY_PATTERNS = [
    r"vulnerability|vuln|exploit|CVE-\d+",
    r"injection|sqli|xss|ssrf|rce|idor",
    r"password|token|credential|secret|api.?key",
    r"critical|high.?severity|security.?issue",
    r"<vulnerability|<finding|<exploit",
    r"authentication.?bypass|privilege.?escalation",
    r"remote.?code.?execution|command.?injection",
    r"confirmed|verified|exploited|successful",
]

MEDIUM_PRIORITY_PATTERNS = [
    r"discovered|found|detected|identified",
    r"endpoint|parameter|header|cookie",
    r"response.?code|status.?\d{3}",
    r"authenticated|session|login",
    r"403|401|500|403|bypass",
    r"error|exception|stack.?trace",
    r"payload|poc|proof.?of.?concept",
]

LOW_PRIORITY_PATTERNS = [
    r"scanning|checking|testing",
    r"no.?vulnerabilit|not.?vulnerable|safe",
    r"finished|completed|done",
    r"starting|beginning|initializing",
]

# Summary templates for different compression strategies
SUMMARY_TEMPLATES = {
    "minimal": """Compress this security testing log to ESSENTIAL findings only.

OUTPUT ONLY:
- Confirmed vulnerabilities (type, URL, payload, severity)
- Valid credentials or tokens discovered
- Working attack payloads

DISCARD ALL:
- Status updates, progress messages
- Failed attempts (unless instructive)
- Verbose tool output

CONVERSATION:
{conversation}

Return a bullet-point list of essential security intelligence ONLY.""",

    "adaptive": """Compress this security testing conversation while preserving critical findings.

MUST PRESERVE:
- Vulnerabilities found (type, location, severity, PoC)
- Credentials, tokens, API keys discovered
- Attack vectors and successful payloads
- Failed approaches (to avoid repeating)
- Target architecture insights

COMPRESS/SUMMARIZE:
- Verbose tool output (keep key findings only)
- Repetitive status messages
- Similar scan results (consolidate)

CONVERSATION:
{conversation}

Output a concise summary preserving all actionable security intelligence.""",

    "full": """Analyze and organize this security testing conversation for comprehensive context.

ORGANIZE INTO SECTIONS:
1. **Confirmed Findings**: All verified vulnerabilities with details
2. **Potential Issues**: Unconfirmed but suspicious behaviors
3. **Target Profile**: Technologies, endpoints, behaviors discovered
4. **Attack Surface**: Identified entry points and parameters
5. **Tested Areas**: What has been checked (avoid repeating)
6. **Failed Approaches**: What didn't work and why

CONVERSATION:
{conversation}

Output a well-structured security assessment summary.""",
}


def _estimate_tokens(text: str) -> int:
    """Fast token estimation without API call."""
    # Average: 1 token ≈ 4 characters for English, 2-3 for code
    return max(len(text) // 3, 1)


def _count_tokens(text: str, model: str) -> int:
    """Count tokens with fast fallback."""
    try:
        count = litellm.token_counter(model=model, text=text)
        return int(count)
    except Exception:
        return _estimate_tokens(text)


def _get_message_tokens(msg: dict[str, Any], model: str) -> int:
    """Get token count for a message."""
    content = msg.get("content", "")
    if isinstance(content, str):
        return _count_tokens(content, model)
    if isinstance(content, list):
        return sum(
            _count_tokens(item.get("text", ""), model)
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        )
    return 0


def _extract_message_text(msg: dict[str, Any]) -> str:
    """Extract text content from a message."""
    content = msg.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
                elif item.get("type") == "image_url":
                    parts.append("[IMAGE]")
        return " ".join(parts)
    return str(content)


def _get_message_priority(msg: dict[str, Any]) -> int:
    """
    Score message priority for retention decisions.
    Higher score = more important to keep.
    """
    text = _extract_message_text(msg).lower()
    score = 0
    
    # High priority patterns (findings, vulns, creds)
    for pattern in HIGH_PRIORITY_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            score += 10
    
    # Medium priority patterns
    for pattern in MEDIUM_PRIORITY_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            score += 5
    
    # Low priority patterns (reduce score for mundane messages)
    for pattern in LOW_PRIORITY_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            score -= 2
    
    # Boost for tool results and assistant messages with findings
    if msg.get("role") == "assistant" and score > 0:
        score += 3
    
    # Boost for messages with specific technical indicators
    if re.search(r"http[s]?://|/api/|\.php|\.asp|\.jsp", text):
        score += 2
    
    # Boost for messages mentioning specific vulnerability types
    vuln_types = ["sqli", "xss", "csrf", "idor", "ssrf", "rce", "lfi", "xxe"]
    if any(vt in text for vt in vuln_types):
        score += 5
    
    return max(score, 0)  # Don't go negative


def _extract_security_context(msg: dict[str, Any]) -> dict[str, Any]:
    """Extract structured security context from a message."""
    text = _extract_message_text(msg)
    context = {
        "urls": [],
        "parameters": [],
        "vulnerabilities": [],
        "credentials": [],
        "status_codes": [],
    }
    
    # Extract URLs
    urls = re.findall(r'https?://[^\s<>"\']+', text)
    context["urls"] = list(set(urls))[:5]  # Keep top 5 unique
    
    # Extract potential parameters
    params = re.findall(r'[\?&](\w+)=', text)
    context["parameters"] = list(set(params))[:10]
    
    # Extract status codes
    status_codes = re.findall(r'\b[45]\d{2}\b', text)
    context["status_codes"] = list(set(status_codes))
    
    return context


def _create_context_summary(contexts: list[dict[str, Any]]) -> str:
    """Create a summary from extracted contexts."""
    all_urls = []
    all_params = []
    all_status = []
    
    for ctx in contexts:
        all_urls.extend(ctx.get("urls", []))
        all_params.extend(ctx.get("parameters", []))
        all_status.extend(ctx.get("status_codes", []))
    
    summary_parts = []
    
    unique_urls = list(set(all_urls))[:10]
    if unique_urls:
        summary_parts.append(f"URLs tested: {', '.join(unique_urls)}")
    
    unique_params = list(set(all_params))[:15]
    if unique_params:
        summary_parts.append(f"Parameters found: {', '.join(unique_params)}")
    
    unique_status = list(set(all_status))
    if unique_status:
        summary_parts.append(f"Status codes seen: {', '.join(unique_status)}")
    
    return " | ".join(summary_parts) if summary_parts else ""


def _get_litellm_model_config(model: str) -> tuple[str, str | None, str | None]:
    """
    Get LiteLLM compatible model configuration.
    
    Handles provider-specific model name conversions for Qwen Code and Roo Code.
    Returns (model_name, api_key, api_base) tuple.
    """
    api_key = None
    api_base = None
    
    # Handle Qwen Code provider
    if model.startswith("qwencode/"):
        try:
            from strix.llm.qwencode_provider import configure_qwencode_for_litellm
            return configure_qwencode_for_litellm(model)
        except RuntimeError as e:
            logger.warning(f"Qwen Code config failed: {e}, falling back to model name")
            # Fall back to using environment variables
            api_key = os.getenv("QWENCODE_ACCESS_TOKEN") or os.getenv("OPENAI_API_KEY")
            api_base = os.getenv("QWENCODE_API_BASE") or os.getenv("OPENAI_BASE_URL")
            clean_name = model.replace("qwencode/", "")
            return f"openai/{clean_name}", api_key, api_base
    
    # Handle Roo Code provider
    if model.startswith("roocode/"):
        try:
            from strix.llm.roocode_provider import configure_roocode_for_litellm
            return configure_roocode_for_litellm(model)
        except RuntimeError as e:
            logger.warning(f"Roo Code config failed: {e}, falling back to model name")
            api_key = os.getenv("ROOCODE_ACCESS_TOKEN") or os.getenv("OPENAI_API_KEY")
            api_base = os.getenv("ROOCODE_API_BASE") or os.getenv("OPENAI_BASE_URL")
            clean_name = model.replace("roocode/", "")
            return f"openai/{clean_name}", api_key, api_base
    
    # Standard model - use environment variables
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    api_base = (
        os.getenv("LLM_API_BASE")
        or os.getenv("OPENAI_API_BASE")
        or os.getenv("LITELLM_BASE_URL")
    )
    
    return model, api_key, api_base


def _summarize_messages(
    messages: list[dict[str, Any]],
    model: str,
    strategy: str = "adaptive",
    timeout: int = 300,
) -> dict[str, Any] | None:
    """
    Summarize a batch of messages into a single context summary.
    Uses strategy-specific prompts for different compression levels.
    Returns None if summarization fails (caller should handle).
    """
    if not messages:
        return None

    # Format messages for summarization
    formatted = []
    contexts = []
    for msg in messages:
        role = msg.get("role", "unknown")
        text = _extract_message_text(msg)
        
        # Extract structured context
        contexts.append(_extract_security_context(msg))
        
        # Truncate very long messages to avoid token overflow
        if len(text) > 2000:
            text = text[:2000] + "... [truncated]"
        formatted.append(f"[{role}]: {text}")

    conversation = "\n".join(formatted)
    
    # Get template based on strategy
    template = SUMMARY_TEMPLATES.get(strategy, SUMMARY_TEMPLATES["adaptive"])
    prompt = template.format(conversation=conversation)

    try:
        # Get proper LiteLLM model configuration (handles qwencode/roocode providers)
        litellm_model, api_key, api_base = _get_litellm_model_config(model)
        
        completion_kwargs: dict[str, Any] = {
            "model": litellm_model,
            "messages": [{"role": "user", "content": prompt}],
            "timeout": timeout,
            "max_tokens": 1500,  # Allow slightly longer summaries
            "temperature": 0.3,  # More deterministic summaries
        }
        if api_key:
            completion_kwargs["api_key"] = api_key
        if api_base:
            completion_kwargs["api_base"] = api_base
        
        response = litellm.completion(**completion_kwargs)
        summary = (response.choices[0].message.content or "").strip()
        
        if not summary:
            return None
        
        # Add context metadata
        context_summary = _create_context_summary(contexts)
        full_summary = summary
        if context_summary:
            full_summary = f"{summary}\n\n[Context: {context_summary}]"
        
        return {
            "role": "assistant",
            "content": f"<context_summary messages='{len(messages)}' strategy='{strategy}'>\n{full_summary}\n</context_summary>",
        }
    except Exception as e:
        logger.warning(f"Summarization failed: {e}")
        return None


def _handle_images(messages: list[dict[str, Any]], max_images: int) -> None:
    """Remove excess images from messages, keeping most recent."""
    image_count = 0
    for msg in reversed(messages):
        content = msg.get("content", [])
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "image_url":
                    if image_count >= max_images:
                        item.update({
                            "type": "text",
                            "text": "[Image removed to save context]",
                        })
                    else:
                        image_count += 1


def _smart_select_for_compression(
    messages: list[dict[str, Any]],
    target_count: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Select which messages to compress based on priority.
    Returns (messages_to_compress, messages_to_keep).
    """
    if len(messages) <= target_count:
        return [], messages
    
    # Score all messages
    scored = [(msg, _get_message_priority(msg), i) for i, msg in enumerate(messages)]
    
    # Sort by priority (keep high priority) but preserve some recency
    # Recent messages get a small boost
    for i, (msg, score, orig_idx) in enumerate(scored):
        recency_boost = i / len(scored) * 3  # 0 to 3 points for recency
        scored[i] = (msg, score + recency_boost, orig_idx)
    
    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)
    
    # Keep top target_count messages
    to_keep_indices = set(item[2] for item in scored[:target_count])
    
    to_compress = []
    to_keep = []
    for i, msg in enumerate(messages):
        if i in to_keep_indices:
            to_keep.append(msg)
        else:
            to_compress.append(msg)
    
    return to_compress, to_keep


def _deduplicate_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove near-duplicate messages based on content hash."""
    seen_hashes = set()
    deduplicated = []
    
    for msg in messages:
        text = _extract_message_text(msg)
        # Create a hash of first 500 chars (enough to identify duplicates)
        text_hash = hashlib.md5(text[:500].encode()).hexdigest()
        
        if text_hash not in seen_hashes:
            seen_hashes.add(text_hash)
            deduplicated.append(msg)
        else:
            logger.debug(f"Removed duplicate message: {text[:50]}...")
    
    return deduplicated


class MemoryCompressor:
    """
    Compresses conversation history for GitHub Actions environment.
    
    Strategy:
    1. Handle image limits first
    2. Keep all system messages
    3. Remove duplicates
    4. Use priority scoring to decide what to compress
    5. Keep recent messages for context continuity
    6. Summarize older low-priority messages using strategy-specific prompts
    
    Memory Strategies:
    - minimal: Aggressive compression, keeps only essential findings
    - adaptive: Balances context retention with compression (default)
    - full: Maximum context, least aggressive compression
    """
    
    def __init__(
        self,
        max_images: int = 3,
        model_name: str | None = None,
        timeout: int = 300,
        memory_strategy: str = "adaptive",
    ):
        self.max_images = max_images
        self.model_name = model_name or os.getenv("STRIX_LLM", "openai/gpt-4o")
        self.timeout = timeout
        self.memory_strategy = memory_strategy
        self._compression_count = 0
        self._total_messages_compressed = 0
        self._tokens_saved = 0
        self._duplicate_count = 0
        
        # Configure based on strategy
        if memory_strategy == "minimal":
            self._compression_ratio = 0.4  # Keep 40% of messages
            self._chunk_size = 12  # Larger chunks for more aggressive compression
        elif memory_strategy == "full":
            self._compression_ratio = 0.7  # Keep 70% of messages
            self._chunk_size = 5  # Smaller chunks for more detailed summaries
        else:  # adaptive
            self._compression_ratio = 0.5  # Keep 50% of messages
            self._chunk_size = 8  # Balanced

    def compress_history(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Compress conversation history to stay within token limits.
        
        Returns the compressed message list.
        """
        if not messages:
            return messages

        # Step 1: Handle image limits
        _handle_images(messages, self.max_images)

        # Step 2: Separate system and regular messages
        system_msgs = []
        regular_msgs = []
        for msg in messages:
            if msg.get("role") == "system":
                system_msgs.append(msg)
            else:
                regular_msgs.append(msg)

        # Step 3: Remove duplicates first (cheap operation)
        original_count = len(regular_msgs)
        regular_msgs = _deduplicate_messages(regular_msgs)
        self._duplicate_count += original_count - len(regular_msgs)

        # Step 4: Check if compression needed
        model = self.model_name or "openai/gpt-4o"
        total_tokens = sum(
            _get_message_tokens(msg, model) for msg in system_msgs + regular_msgs
        )

        # Determine compression need based on thresholds
        compression_needed = False
        aggressive_mode = False
        
        if total_tokens > MAX_TOTAL_TOKENS * AGGRESSIVE_COMPRESSION_RATIO:
            compression_needed = True
            aggressive_mode = True
            logger.warning(f"Aggressive compression triggered: {total_tokens} tokens (>{AGGRESSIVE_COMPRESSION_RATIO*100}%)")
        elif total_tokens > MAX_TOTAL_TOKENS * COMPRESSION_TRIGGER_RATIO:
            compression_needed = True
            logger.info(f"Standard compression triggered: {total_tokens} tokens (>{COMPRESSION_TRIGGER_RATIO*100}%)")

        if not compression_needed:
            return messages

        tokens_before = total_tokens
        logger.info(f"Compressing history: {total_tokens} tokens, {len(regular_msgs)} messages")

        # Step 5: Keep recent messages intact
        recent_count = MIN_RECENT_MESSAGES if not aggressive_mode else MIN_RECENT_MESSAGES // 2
        recent_msgs = regular_msgs[-recent_count:]
        older_msgs = regular_msgs[:-recent_count] if len(regular_msgs) > recent_count else []

        if not older_msgs:
            return messages  # Nothing to compress

        # Step 6: Smart selection - keep high priority, compress low priority
        keep_ratio = self._compression_ratio if not aggressive_mode else self._compression_ratio * 0.6
        to_compress, to_keep = _smart_select_for_compression(
            older_msgs,
            target_count=max(3, int(len(older_msgs) * keep_ratio))
        )

        # Step 7: Compress in chunks using strategy-specific summarization
        compressed = []
        chunk_size = self._chunk_size if not aggressive_mode else self._chunk_size * 2
        
        for i in range(0, len(to_compress), chunk_size):
            chunk = to_compress[i:i + chunk_size]
            summary = _summarize_messages(
                chunk, 
                model, 
                strategy=self.memory_strategy,
                timeout=self.timeout
            )
            if summary:
                compressed.append(summary)
            else:
                # Fallback: keep first message of chunk if summarization fails
                compressed.append(chunk[0])

        self._compression_count += 1
        self._total_messages_compressed += len(to_compress)
        
        # Calculate tokens saved
        result = system_msgs + compressed + to_keep + recent_msgs
        tokens_after = sum(_get_message_tokens(msg, model) for msg in result)
        self._tokens_saved += tokens_before - tokens_after
        
        logger.info(
            f"Compression #{self._compression_count}: "
            f"{len(to_compress)} messages → {len(compressed)} summaries, "
            f"saved {tokens_before - tokens_after} tokens"
        )

        # Return: system + compressed + kept_older + recent
        return result
    
    def get_memory_usage_ratio(self, messages: list[dict[str, Any]]) -> float:
        """Get current memory usage as a ratio of max tokens."""
        model = self.model_name or "openai/gpt-4o"
        total_tokens = sum(_get_message_tokens(msg, model) for msg in messages)
        return total_tokens / MAX_TOTAL_TOKENS
    
    def should_compress(self, messages: list[dict[str, Any]]) -> bool:
        """Check if compression is needed based on current usage."""
        ratio = self.get_memory_usage_ratio(messages)
        return ratio > COMPRESSION_TRIGGER_RATIO
    
    @property
    def compression_stats(self) -> dict[str, Any]:
        """Get comprehensive compression statistics."""
        return {
            "compression_count": self._compression_count,
            "total_messages_compressed": self._total_messages_compressed,
            "tokens_saved": self._tokens_saved,
            "duplicates_removed": self._duplicate_count,
            "max_tokens": MAX_TOTAL_TOKENS,
            "min_recent": MIN_RECENT_MESSAGES,
            "memory_strategy": self.memory_strategy,
            "compression_trigger": f"{COMPRESSION_TRIGGER_RATIO*100}%",
            "aggressive_trigger": f"{AGGRESSIVE_COMPRESSION_RATIO*100}%",
        }
    
    def reset_stats(self) -> None:
        """Reset compression statistics."""
        self._compression_count = 0
        self._total_messages_compressed = 0
        self._tokens_saved = 0
        self._duplicate_count = 0
