"""Setup agent — generates prompt templates for each phase by reading skill definitions.

Uses a fast/cheap Claude model (haiku) to generate prompts that pre-supply known answers,
minimizing back-and-forth during test runs.
"""

import hashlib
import json
import logging
from pathlib import Path

import anthropic
import yaml

logger = logging.getLogger(__name__)


PHASE_SKILL_MAP = {
    "init": "skills/harness-init/SKILL.md",
    "profile-data": "skills/profile-data/SKILL.md",
    "define-epics": "skills/define-epics/SKILL.md",
    "execute-plan": "skills/execute-plan/SKILL.md",
}

PHASE_COMMAND_MAP = {
    "init": "harness-init",
    "profile-data": "profile-data",
    "define-epics": "define-epics",
    "execute-plan": "execute-plan",
}


REQUIRED_CONTEXT_BY_PHASE = {
    "init": ("project_name",),
    "profile-data": ("target_variable",),
    "define-epics": ("business_objective",),
    "execute-plan": (),
}


def generate_prompt(
    phase: str,
    analyst_context: dict,
    plugin_dir: Path,
    cache_dir: Path | None = None,
) -> str:
    """Generate a prompt template for a phase test.

    Args:
        phase: One of "init", "profile-data", "define-epics", "execute-plan".
        analyst_context: Dict from analyst-context.yaml.
        plugin_dir: Path to the plugin repo root (to read skill definitions).
        cache_dir: Optional directory for caching prompts by skill file hash.

    Returns:
        A prompt string ready to pipe into the claude CLI.
    """
    skill_path = plugin_dir / PHASE_SKILL_MAP[phase]
    skill_content = skill_path.read_text()
    skill_hash = hashlib.sha256(skill_content.encode()).hexdigest()[:16]

    # Check cache
    if cache_dir:
        cache_file = cache_dir / f"{phase}-{skill_hash}.txt"
        if cache_file.exists():
            logger.info("Using cached prompt for %s", phase)
            return cache_file.read_text()

    # Generate via Claude API
    client = anthropic.Anthropic()
    context_yaml = yaml.dump(analyst_context, default_flow_style=False)

    system_prompt = (
        "You are generating a test prompt for a Claude Code plugin. "
        "The prompt will be sent as a user message to Claude Code with the plugin loaded. "
        "Your output should be ONLY the prompt text — no explanation, no markdown fences. "
        "The prompt must invoke the slash command and pre-supply all answers the skill will ask for, "
        "so the session can complete with minimal back-and-forth."
    )

    command_name = PHASE_COMMAND_MAP[phase]
    user_prompt = (
        f"Generate a prompt for the '/{command_name}' command.\n\n"
        f"## Skill definition\n\n{skill_content}\n\n"
        f"## Analyst context (known answers)\n\n```yaml\n{context_yaml}```\n\n"
        f"## Instructions\n\n"
        f"Write a single prompt that:\n"
        f"1. Invokes the /{command_name} command with appropriate arguments\n"
        f"2. Pre-supplies all known answers inline so Claude doesn't need to ask\n"
        f"3. Tells Claude to proceed without asking for confirmation where possible\n"
        f"4. Is concise but complete\n"
    )

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    prompt = response.content[0].text
    prompt = _enforce_required_context(phase, prompt, analyst_context)

    # Cache result
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{phase}-{skill_hash}.txt"
        cache_file.write_text(prompt)
        logger.info("Cached prompt for %s at %s", phase, cache_file)

    return prompt


def _enforce_required_context(phase: str, prompt: str, analyst_context: dict) -> str:
    """Append required analyst context fields when the model omits them."""
    required_keys = REQUIRED_CONTEXT_BY_PHASE.get(phase, ())
    missing_lines: list[str] = []
    lowered_prompt = prompt.lower()

    for key in required_keys:
        value = analyst_context.get(key)
        if not value or not isinstance(value, str):
            continue
        if value.lower() in lowered_prompt:
            continue
        pretty_key = key.replace("_", " ")
        missing_lines.append(f"{pretty_key}: {value}")

    if not missing_lines:
        return prompt

    suffix = "\n".join(missing_lines)
    if prompt.endswith("\n"):
        return f"{prompt}{suffix}\n"
    return f"{prompt}\n\n{suffix}\n"
