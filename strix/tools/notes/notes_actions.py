import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from strix.tools.registry import register_tool


_notes_storage: dict[str, dict[str, Any]] = {}

# Knowledge base for structured learning and attack patterns
_knowledge_base: dict[str, dict[str, Any]] = {
    "attack_patterns": {},    # Learned attack patterns
    "vulnerability_db": {},   # Discovered vulnerabilities database
    "tool_configs": {},       # Tool configurations and optimal settings
    "target_profiles": {},    # Target reconnaissance profiles
    "payload_library": {},    # Effective payloads and bypasses
    "methodology_notes": {},  # Testing methodology learnings
}

# Workspace path for persistent storage
_WORKSPACE_PATH = Path("/workspace/.strix_knowledge")


def _filter_notes(
    category: str | None = None,
    tags: list[str] | None = None,
    priority: str | None = None,
    search_query: str | None = None,
) -> list[dict[str, Any]]:
    filtered_notes = []

    for note_id, note in _notes_storage.items():
        if category and note.get("category") != category:
            continue

        if priority and note.get("priority") != priority:
            continue

        if tags:
            note_tags = note.get("tags", [])
            if not any(tag in note_tags for tag in tags):
                continue

        if search_query:
            search_lower = search_query.lower()
            title_match = search_lower in note.get("title", "").lower()
            content_match = search_lower in note.get("content", "").lower()
            if not (title_match or content_match):
                continue

        note_with_id = note.copy()
        note_with_id["note_id"] = note_id
        filtered_notes.append(note_with_id)

    filtered_notes.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return filtered_notes


@register_tool
def create_note(
    title: str,
    content: str,
    category: str = "general",
    tags: list[str] | None = None,
    priority: str = "normal",
) -> dict[str, Any]:
    try:
        if not title or not title.strip():
            return {"success": False, "error": "Title cannot be empty", "note_id": None}

        if not content or not content.strip():
            return {"success": False, "error": "Content cannot be empty", "note_id": None}

        valid_categories = ["general", "findings", "methodology", "todo", "questions", "plan"]
        if category not in valid_categories:
            return {
                "success": False,
                "error": f"Invalid category. Must be one of: {', '.join(valid_categories)}",
                "note_id": None,
            }

        valid_priorities = ["low", "normal", "high", "urgent"]
        if priority not in valid_priorities:
            return {
                "success": False,
                "error": f"Invalid priority. Must be one of: {', '.join(valid_priorities)}",
                "note_id": None,
            }

        note_id = str(uuid.uuid4())[:5]
        timestamp = datetime.now(UTC).isoformat()

        note = {
            "title": title.strip(),
            "content": content.strip(),
            "category": category,
            "tags": tags or [],
            "priority": priority,
            "created_at": timestamp,
            "updated_at": timestamp,
        }

        _notes_storage[note_id] = note

    except (ValueError, TypeError) as e:
        return {"success": False, "error": f"Failed to create note: {e}", "note_id": None}
    else:
        return {
            "success": True,
            "note_id": note_id,
            "message": f"Note '{title}' created successfully",
        }


@register_tool
def list_notes(
    category: str | None = None,
    tags: list[str] | None = None,
    priority: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    try:
        filtered_notes = _filter_notes(
            category=category, tags=tags, priority=priority, search_query=search
        )

        return {
            "success": True,
            "notes": filtered_notes,
            "total_count": len(filtered_notes),
        }

    except (ValueError, TypeError) as e:
        return {
            "success": False,
            "error": f"Failed to list notes: {e}",
            "notes": [],
            "total_count": 0,
        }


@register_tool
def update_note(
    note_id: str,
    title: str | None = None,
    content: str | None = None,
    tags: list[str] | None = None,
    priority: str | None = None,
) -> dict[str, Any]:
    try:
        if note_id not in _notes_storage:
            return {"success": False, "error": f"Note with ID '{note_id}' not found"}

        note = _notes_storage[note_id]

        if title is not None:
            if not title.strip():
                return {"success": False, "error": "Title cannot be empty"}
            note["title"] = title.strip()

        if content is not None:
            if not content.strip():
                return {"success": False, "error": "Content cannot be empty"}
            note["content"] = content.strip()

        if tags is not None:
            note["tags"] = tags

        if priority is not None:
            valid_priorities = ["low", "normal", "high", "urgent"]
            if priority not in valid_priorities:
                return {
                    "success": False,
                    "error": f"Invalid priority. Must be one of: {', '.join(valid_priorities)}",
                }
            note["priority"] = priority

        note["updated_at"] = datetime.now(UTC).isoformat()

        return {
            "success": True,
            "message": f"Note '{note['title']}' updated successfully",
        }

    except (ValueError, TypeError) as e:
        return {"success": False, "error": f"Failed to update note: {e}"}


@register_tool
def delete_note(note_id: str) -> dict[str, Any]:
    try:
        if note_id not in _notes_storage:
            return {"success": False, "error": f"Note with ID '{note_id}' not found"}

        note_title = _notes_storage[note_id]["title"]
        del _notes_storage[note_id]

    except (ValueError, TypeError) as e:
        return {"success": False, "error": f"Failed to delete note: {e}"}
    else:
        return {
            "success": True,
            "message": f"Note '{note_title}' deleted successfully",
        }


# ============================================================================
# Enhanced Knowledge Management Tools
# ============================================================================

@register_tool
def save_knowledge(
    knowledge_type: str,
    key: str,
    data: dict[str, Any],
    description: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """
    Save knowledge to the persistent knowledge base.
    
    Use this to store and build up knowledge during testing:
    - Attack patterns that work on specific targets
    - Vulnerability findings with technical details
    - Tool configurations that are effective
    - Target profiles and reconnaissance data
    - Effective payloads and bypass techniques
    - Methodology learnings and insights
    
    Args:
        knowledge_type: Type of knowledge. Options:
            - attack_patterns: Successful attack techniques
            - vulnerability_db: Vulnerability database entries
            - tool_configs: Tool configurations and settings
            - target_profiles: Target reconnaissance data
            - payload_library: Effective payloads and bypasses
            - methodology_notes: Testing methodology learnings
        key: Unique key to identify this knowledge entry
        data: The knowledge data as a dictionary
        description: Human-readable description
        tags: List of tags for categorization
    
    Returns:
        Success status and knowledge entry ID
    """
    try:
        valid_types = list(_knowledge_base.keys())
        if knowledge_type not in valid_types:
            return {
                "success": False,
                "error": f"Invalid knowledge_type. Must be one of: {', '.join(valid_types)}",
            }
        
        if not key or not key.strip():
            return {"success": False, "error": "Key cannot be empty"}
        
        key = key.strip().lower().replace(" ", "_")
        timestamp = datetime.now(UTC).isoformat()
        
        entry = {
            "key": key,
            "data": data,
            "description": description,
            "tags": tags or [],
            "created_at": timestamp,
            "updated_at": timestamp,
            "access_count": 0,
        }
        
        _knowledge_base[knowledge_type][key] = entry
        
        # Persist to disk for cross-agent sharing
        _persist_knowledge()
        
        return {
            "success": True,
            "knowledge_type": knowledge_type,
            "key": key,
            "message": f"Knowledge saved: {knowledge_type}/{key}",
        }
        
    except Exception as e:  # noqa: BLE001
        return {"success": False, "error": f"Failed to save knowledge: {e}"}


@register_tool
def get_knowledge(
    knowledge_type: str,
    key: str | None = None,
    tags: list[str] | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    """
    Retrieve knowledge from the knowledge base.
    
    Use this to recall previously learned information during testing:
    - What attack patterns worked before
    - Previous vulnerability findings
    - Effective tool configurations
    - Target reconnaissance data
    - Working payloads and bypasses
    
    Args:
        knowledge_type: Type of knowledge to retrieve
        key: Specific key to retrieve (optional)
        tags: Filter by tags (optional)
        search: Search in descriptions and data (optional)
    
    Returns:
        Retrieved knowledge entries
    """
    try:
        # Load from disk first to get cross-agent knowledge
        _load_knowledge()
        
        valid_types = list(_knowledge_base.keys())
        if knowledge_type not in valid_types:
            return {
                "success": False,
                "error": f"Invalid knowledge_type. Must be one of: {', '.join(valid_types)}",
            }
        
        kb = _knowledge_base[knowledge_type]
        
        # If specific key requested
        if key:
            key = key.strip().lower().replace(" ", "_")
            if key in kb:
                entry = kb[key]
                entry["access_count"] += 1
                return {
                    "success": True,
                    "entry": entry,
                    "knowledge_type": knowledge_type,
                }
            return {
                "success": False,
                "error": f"Key '{key}' not found in {knowledge_type}",
            }
        
        # Filter entries
        entries = []
        for entry_key, entry in kb.items():
            # Filter by tags
            if tags:
                entry_tags = entry.get("tags", [])
                if not any(tag in entry_tags for tag in tags):
                    continue
            
            # Search in description and data
            if search:
                search_lower = search.lower()
                desc_match = search_lower in entry.get("description", "").lower()
                data_match = search_lower in json.dumps(entry.get("data", {})).lower()
                if not (desc_match or data_match):
                    continue
            
            entries.append({"key": entry_key, **entry})
        
        return {
            "success": True,
            "entries": entries,
            "count": len(entries),
            "knowledge_type": knowledge_type,
        }
        
    except Exception as e:  # noqa: BLE001
        return {"success": False, "error": f"Failed to get knowledge: {e}"}


@register_tool
def list_knowledge_summary() -> dict[str, Any]:
    """
    Get a summary of all knowledge stored in the knowledge base.
    
    Use this to understand what knowledge has been accumulated during testing.
    
    Returns:
        Summary of knowledge base contents by type
    """
    try:
        _load_knowledge()
        
        summary = {}
        total_entries = 0
        
        for kb_type, entries in _knowledge_base.items():
            entry_count = len(entries)
            total_entries += entry_count
            
            # Get recent entries
            recent = []
            for key, entry in list(entries.items())[:5]:
                recent.append({
                    "key": key,
                    "description": entry.get("description", "")[:100],
                    "tags": entry.get("tags", []),
                })
            
            summary[kb_type] = {
                "count": entry_count,
                "recent_entries": recent,
            }
        
        return {
            "success": True,
            "summary": summary,
            "total_entries": total_entries,
            "knowledge_types": list(_knowledge_base.keys()),
        }
        
    except Exception as e:  # noqa: BLE001
        return {"success": False, "error": f"Failed to get knowledge summary: {e}"}


@register_tool
def save_attack_chain(
    name: str,
    steps: list[dict[str, Any]],
    target_type: str,
    vulnerability_class: str,
    success_rate: str = "unknown",
    notes: str = "",
) -> dict[str, Any]:
    """
    Save a successful attack chain for future reference.
    
    Use this to document multi-step attack sequences that successfully
    exploited vulnerabilities. This helps build a library of attack
    chains that can be referenced and adapted for future targets.
    
    Args:
        name: Name of the attack chain
        steps: List of attack steps, each with:
            - step_number: Sequential step number
            - action: What was done
            - tool_used: Tool or method used
            - payload: Payload or input used (if applicable)
            - result: What happened
        target_type: Type of target (web_app, api, network, etc.)
        vulnerability_class: Class of vulnerability exploited (SQLi, XSS, IDOR, etc.)
        success_rate: Estimated success rate (high, medium, low, unknown)
        notes: Additional notes about the attack chain
    
    Returns:
        Success status and chain ID
    """
    try:
        if not name or not steps:
            return {"success": False, "error": "Name and steps are required"}
        
        chain_data = {
            "name": name,
            "steps": steps,
            "target_type": target_type,
            "vulnerability_class": vulnerability_class,
            "success_rate": success_rate,
            "notes": notes,
            "step_count": len(steps),
        }
        
        key = f"{vulnerability_class}_{name}".lower().replace(" ", "_")
        
        return save_knowledge(
            knowledge_type="attack_patterns",
            key=key,
            data=chain_data,
            description=f"Attack chain for {vulnerability_class}: {name}",
            tags=[target_type, vulnerability_class, f"steps_{len(steps)}"],
        )
        
    except Exception as e:  # noqa: BLE001
        return {"success": False, "error": f"Failed to save attack chain: {e}"}


@register_tool
def save_payload(
    name: str,
    payload: str,
    payload_type: str,
    target_context: str,
    bypass_notes: str = "",
    encoding: str | None = None,
    success_conditions: str = "",
) -> dict[str, Any]:
    """
    Save an effective payload to the payload library.
    
    Use this to build a library of working payloads that can be
    referenced and adapted for future testing.
    
    Args:
        name: Name/identifier for the payload
        payload: The actual payload string
        payload_type: Type of payload (sqli, xss, ssrf, rce, xxe, etc.)
        target_context: Where this payload works (input field, URL param, header, etc.)
        bypass_notes: Notes on what security measures this bypasses
        encoding: Any encoding applied (url, base64, unicode, etc.)
        success_conditions: What indicates successful exploitation
    
    Returns:
        Success status and payload ID
    """
    try:
        if not name or not payload:
            return {"success": False, "error": "Name and payload are required"}
        
        payload_data = {
            "name": name,
            "payload": payload,
            "payload_type": payload_type,
            "target_context": target_context,
            "bypass_notes": bypass_notes,
            "encoding": encoding,
            "success_conditions": success_conditions,
            "payload_length": len(payload),
        }
        
        key = f"{payload_type}_{name}".lower().replace(" ", "_")
        
        return save_knowledge(
            knowledge_type="payload_library",
            key=key,
            data=payload_data,
            description=f"{payload_type.upper()} payload: {name}",
            tags=[payload_type, target_context] + ([encoding] if encoding else []),
        )
        
    except Exception as e:  # noqa: BLE001
        return {"success": False, "error": f"Failed to save payload: {e}"}


@register_tool
def get_payloads(
    payload_type: str | None = None,
    target_context: str | None = None,
) -> dict[str, Any]:
    """
    Retrieve payloads from the payload library.
    
    Args:
        payload_type: Filter by payload type (sqli, xss, ssrf, etc.)
        target_context: Filter by target context (url, header, body, etc.)
    
    Returns:
        List of matching payloads
    """
    try:
        _load_knowledge()
        
        payloads = []
        for key, entry in _knowledge_base["payload_library"].items():
            data = entry.get("data", {})
            
            if payload_type and data.get("payload_type") != payload_type:
                continue
            
            if target_context and data.get("target_context") != target_context:
                continue
            
            payloads.append({
                "key": key,
                "name": data.get("name"),
                "payload": data.get("payload"),
                "payload_type": data.get("payload_type"),
                "target_context": data.get("target_context"),
                "bypass_notes": data.get("bypass_notes"),
            })
        
        return {
            "success": True,
            "payloads": payloads,
            "count": len(payloads),
        }
        
    except Exception as e:  # noqa: BLE001
        return {"success": False, "error": f"Failed to get payloads: {e}"}


def _persist_knowledge() -> None:
    """Persist knowledge base to disk for cross-agent sharing."""
    try:
        _WORKSPACE_PATH.mkdir(parents=True, exist_ok=True)
        kb_file = _WORKSPACE_PATH / "knowledge_base.json"
        with open(kb_file, "w", encoding="utf-8") as f:
            json.dump(_knowledge_base, f, indent=2)
    except (OSError, IOError):
        pass  # Silently fail if can't persist


def _load_knowledge() -> None:
    """Load knowledge base from disk."""
    global _knowledge_base
    try:
        kb_file = _WORKSPACE_PATH / "knowledge_base.json"
        if kb_file.exists():
            with open(kb_file, encoding="utf-8") as f:
                loaded = json.load(f)
                # Merge with existing (don't overwrite)
                for kb_type, entries in loaded.items():
                    if kb_type in _knowledge_base:
                        for key, entry in entries.items():
                            if key not in _knowledge_base[kb_type]:
                                _knowledge_base[kb_type][key] = entry
    except (OSError, IOError, json.JSONDecodeError):
        pass  # Silently fail if can't load
