"""Tests for the setup agent — verifies prompt generation from skill definitions."""

import yaml
from pathlib import Path

from integration_tests.agents.setup_agent import generate_prompt, PHASE_SKILL_MAP


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "synthetic"
PLUGIN_DIR = Path(__file__).parent.parent.parent  # one_shot_build repo root


def test_generate_prompt_for_init():
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        context = yaml.safe_load(f)
    prompt = generate_prompt("init", context, PLUGIN_DIR)
    assert "/init" in prompt
    assert context["project_name"] in prompt


def test_generate_prompt_for_profile_data():
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        context = yaml.safe_load(f)
    prompt = generate_prompt("profile-data", context, PLUGIN_DIR)
    assert "/profile-data" in prompt or "profile" in prompt.lower()
    assert context["target_variable"] in prompt


def test_generate_prompt_for_define_epics():
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        context = yaml.safe_load(f)
    prompt = generate_prompt("define-epics", context, PLUGIN_DIR)
    assert "epic" in prompt.lower()
    assert context["business_objective"] in prompt


def test_prompt_caching(tmp_path):
    """Generating twice with same skill hash returns cached result."""
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        context = yaml.safe_load(f)
    prompt1 = generate_prompt("init", context, PLUGIN_DIR, cache_dir=tmp_path)
    prompt2 = generate_prompt("init", context, PLUGIN_DIR, cache_dir=tmp_path)
    assert prompt1 == prompt2
