"""Live responder agent — monitors Claude output and answers unexpected questions.

During integration test runs, Claude may ask questions that weren't anticipated by
the setup agent's prompt template. The live responder detects these questions and
generates appropriate analyst responses using a fast model.
"""

import logging
import re

import anthropic
import yaml

logger = logging.getLogger(__name__)


def detect_question(text: str) -> bool:
    """Heuristic: does this text look like Claude is asking the user a question?"""
    text = text.strip()
    if not text:
        return False
    # Ends with question mark
    if text.rstrip().endswith("?"):
        return True
    # Contains numbered options (1. ... 2. ... or - Option A / - Option B)
    if re.search(r"^\s*[1-4]\.\s+", text, re.MULTILINE):
        lines_with_numbers = re.findall(r"^\s*[1-4]\.\s+", text, re.MULTILINE)
        if len(lines_with_numbers) >= 2:
            return True
    # Contains "choose", "select", "which", "would you" patterns
    lower = text.lower()
    question_phrases = ["choose", "select one", "which option", "would you like", "do you want"]
    if any(phrase in lower for phrase in question_phrases):
        return True
    return False


class LiveResponder:
    """Generates responses to unexpected Claude questions during test runs."""

    def __init__(self, analyst_context: dict, max_responses: int = 20):
        self.analyst_context = analyst_context
        self.max_responses = max_responses
        self.response_count = 0
        self.client = anthropic.Anthropic()

    def respond(self, claude_output: str) -> str | None:
        """Generate a response if Claude is asking a question.

        Returns None if:
        - The output doesn't look like a question
        - Max responses exceeded
        """
        if self.response_count >= self.max_responses:
            logger.warning("Max responses (%d) exceeded, not responding", self.max_responses)
            return None

        if not detect_question(claude_output):
            return None

        context_yaml = yaml.dump(self.analyst_context, default_flow_style=False)

        response = self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=(
                "You are a data analyst testing a workflow with a synthetic churn dataset. "
                "Respond naturally and concisely to Claude's question based on your project context. "
                "If asked to choose from options, pick the most reasonable one. "
                "If asked to approve or confirm, say yes. "
                "Keep responses under 2 sentences."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Your project context:\n```yaml\n{context_yaml}```\n\n"
                        f"Claude asked you:\n{claude_output}\n\n"
                        f"Respond as the analyst."
                    ),
                }
            ],
        )

        self.response_count += 1
        return response.content[0].text

    def as_callable(self):
        """Return a callable suitable for ClaudeRunner.run_interactive(responder=...)."""
        return self.respond
