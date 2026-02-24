"""Tests for the live responder — verifies question detection and response generation."""

import yaml
from pathlib import Path

from integration_tests.agents.responder_agent import LiveResponder, detect_question


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "synthetic"


def test_detect_question_with_question_mark():
    assert detect_question("What is the target variable?\n")


def test_detect_question_with_numbered_options():
    text = "Choose an option:\n1. Option A\n2. Option B\n3. Option C\n"
    assert detect_question(text)


def test_detect_question_plain_statement():
    assert not detect_question("Processing data profiles...\n")


def test_responder_generates_answer():
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        context = yaml.safe_load(f)
    responder = LiveResponder(context)
    answer = responder.respond("What is the target variable for this dataset?")
    assert answer is not None
    assert len(answer) > 0


def test_responder_returns_none_for_non_question():
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        context = yaml.safe_load(f)
    responder = LiveResponder(context)
    answer = responder.respond("Creating data profile... done.")
    assert answer is None


def test_responder_tracks_response_count():
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        context = yaml.safe_load(f)
    responder = LiveResponder(context, max_responses=2)
    responder.respond("Question 1?")
    responder.respond("Question 2?")
    answer = responder.respond("Question 3?")
    assert answer is None  # Exceeded max
