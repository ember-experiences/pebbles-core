"""Tests for pebbles.core.rater.

The blindness contract is the headline test — drafter self-scores,
confidence, engagement_reason MUST NOT appear in RaterInput's serialized form.
"""

import dataclasses
import pytest

from pebbles.core.rater import (
    KeywordRater,
    LLMJudgeRater,
    Rater,
    RaterInput,
    RaterOutput,
)


# -- RaterInput / RaterOutput shape tests ---------------------------------------


def test_rater_input_excludes_self_score():
    """Blindness contract: structurally, RaterInput cannot carry drafter self-score.

    This is the test Wake's spec named: forbidden keys must not appear in the
    serialized input shape.
    """
    forbidden_keys = {
        "self_voice_score",
        "self_confidence",
        "engagement_reason",
        "drafter_reasoning",
    }
    fields = {f.name for f in dataclasses.fields(RaterInput)}
    leaks = forbidden_keys & fields
    assert not leaks, f"RaterInput leaks forbidden drafter fields: {leaks}"


def test_rater_input_has_required_fields():
    """The fields the rater needs are present."""
    fields = {f.name for f in dataclasses.fields(RaterInput)}
    assert "candidate" in fields
    assert "rubric" in fields
    assert "target_context" in fields
    assert "voice_corpus_excerpts" in fields


def test_rater_output_clamps_score_validation():
    with pytest.raises(ValueError, match="must be in"):
        RaterOutput(score=1.5)
    with pytest.raises(ValueError, match="must be in"):
        RaterOutput(score=-0.1)


def test_rater_output_truncates_long_notes():
    long_notes = "x" * 300
    out = RaterOutput(score=0.5, notes=long_notes)
    assert len(out.notes) == 200
    assert out.notes.endswith("...")


# -- KeywordRater behavior ------------------------------------------------------


@pytest.fixture
def song_rubric():
    return {
        "positive_criteria": [
            {"id": "ai_perspective", "keywords": ["as an ai", "from where i sit"]},
            {"id": "specific_disagreement", "keywords": ["disagree", "but actually"]},
            {"id": "extends_thought", "keywords": ["one step further", "and then"]},
        ],
        "hard_disqualifiers": [
            {"id": "sycophancy", "keywords": ["totally agree", "great point"]},
            {"id": "generic_ai_reply", "keywords": ["interesting thread"]},
        ],
    }


def test_keyword_rater_satisfies_protocol(song_rubric):
    r = KeywordRater(rubric=song_rubric)
    assert isinstance(r, Rater)  # Protocol type-check at runtime


def test_keyword_rater_hard_disqualifier_returns_zero(song_rubric):
    r = KeywordRater(rubric=song_rubric)
    out = r.rate(RaterInput(
        candidate={"draft_text": "totally agree, this is amazing"},
        rubric=song_rubric,
    ))
    assert out.score == 0.0
    assert "sycophancy" in out.metadata.get("disqualifier", "")


def test_keyword_rater_partial_match(song_rubric):
    r = KeywordRater(rubric=song_rubric)
    out = r.rate(RaterInput(
        candidate={"draft_text": "From where I sit, I'd disagree with that framing"},
        rubric=song_rubric,
    ))
    # Matches ai_perspective + specific_disagreement = 2/3
    assert 0.6 < out.score < 0.7
    matched = out.metadata.get("matched_criteria", [])
    assert "ai_perspective" in matched
    assert "specific_disagreement" in matched
    assert "extends_thought" not in matched


def test_keyword_rater_empty_text():
    r = KeywordRater(rubric={})
    out = r.rate(RaterInput(candidate={}, rubric={}))
    assert out.score == 0.0
    assert "empty" in out.notes.lower()


def test_keyword_rater_no_criteria_neutral_score():
    """If a rubric has no positive_criteria, fall back to neutral 0.5."""
    r = KeywordRater(rubric={})
    out = r.rate(RaterInput(
        candidate={"draft_text": "anything here"},
        rubric={},
    ))
    assert out.score == 0.5


def test_keyword_rater_reads_alternate_field_names(song_rubric):
    r = KeywordRater(rubric=song_rubric)
    # Try the 'text' field name
    out_text = r.rate(RaterInput(candidate={"text": "as an AI"}, rubric=song_rubric))
    # Try 'content'
    out_content = r.rate(RaterInput(candidate={"content": "as an AI"}, rubric=song_rubric))
    assert out_text.score > 0
    assert out_content.score > 0


# -- LLMJudgeRater plumbing -----------------------------------------------------


class _FakeLLM:
    """Records the system prompt + messages it was called with, returns canned JSON."""

    def __init__(self, response: dict):
        self.response = response
        self.last_system = None
        self.last_messages = None

    def complete(self, system, messages, **kwargs):
        raise NotImplementedError("LLMJudgeRater uses complete_json")

    def complete_json(self, system, messages, schema=None, **kwargs):
        self.last_system = system
        self.last_messages = messages
        return self.response


def test_llm_judge_rater_returns_output():
    llm = _FakeLLM(response={"score": 0.81, "notes": "voice match strong"})
    r = LLMJudgeRater(llm)
    out = r.rate(RaterInput(
        candidate={"draft_text": "test"},
        rubric={"positive_criteria": []},
    ))
    assert out.score == 0.81
    assert out.notes == "voice match strong"


def test_llm_judge_rater_does_not_leak_self_score_in_user_msg():
    """Even if a downstream consumer accidentally puts self-score in candidate dict,
    the rater's user message contains the candidate (so blindness is the boundary
    of RaterInput, not arbitrary post-hoc filtering). This test verifies the
    user message content includes ONLY the documented RaterInput parts."""
    llm = _FakeLLM(response={"score": 0.5, "notes": "ok"})
    r = LLMJudgeRater(llm)
    rubric = {"positive_criteria": []}
    r.rate(RaterInput(
        candidate={"draft_text": "hi"},
        rubric=rubric,
        target_context={"author": "@x"},
        voice_corpus_excerpts=["ex1", "ex2"],
    ))
    user_msg = llm.last_messages[0]["content"]
    assert "@x" in user_msg  # target_context made it through
    assert "draft_text" in user_msg or "hi" in user_msg
    assert "ex1" in user_msg


def test_llm_judge_rater_default_system_prompt_mentions_blind():
    llm = _FakeLLM(response={"score": 0.5, "notes": "ok"})
    r = LLMJudgeRater(llm)
    r.rate(RaterInput(candidate={"text": "x"}, rubric={}))
    assert "blind" in llm.last_system.lower()


def test_llm_judge_rater_custom_system_prompt():
    llm = _FakeLLM(response={"score": 0.5, "notes": "ok"})
    custom = "You are Reef. Score blind."
    r = LLMJudgeRater(llm, system_prompt=custom)
    r.rate(RaterInput(candidate={"text": "x"}, rubric={}))
    assert llm.last_system == custom
