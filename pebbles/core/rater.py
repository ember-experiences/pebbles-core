"""Rater Protocol — score items against a rubric, blind to drafter self-assessment.

The blindness contract is structural: RaterInput is a dataclass with explicit
fields. Drafter self-scores, confidence, and engagement_reason are NOT fields
— so they cannot leak in via the typed boundary.

Reference impls:
- KeywordRater: deterministic, no LLM. For tests + dev.
- LLMJudgeRater: generic LLM-as-judge using any LLMAdapter.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

from pebbles.core.llm import LLMAdapter

logger = logging.getLogger(__name__)


@dataclass
class RaterInput:
    """What the rater sees.

    Deliberately minimal — no self-scores, no internal reasoning from the drafter.
    The structural absence of those fields IS the blindness contract; tests
    verify by serializing this dataclass and asserting forbidden keys absent.
    """

    candidate: dict
    """The thing being scored (e.g. {"draft_text": "...", "type": "reply"})."""

    rubric: dict
    """The rubric to score against (positive criteria, hard disqualifiers, etc.)."""

    target_context: Optional[dict] = None
    """What's being engaged with, if any (e.g. the post being replied to)."""

    voice_corpus_excerpts: list[str] = field(default_factory=list)
    """Voice anchors — last N blog posts, SOUL excerpts, etc."""


@dataclass
class RaterOutput:
    """The rater's verdict."""

    score: float  # 0.0 to 1.0
    notes: str = ""  # one-line rationale, ≤200 chars
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"Rater score must be in [0.0, 1.0], got {self.score}")
        if len(self.notes) > 200:
            self.notes = self.notes[:197] + "..."


@runtime_checkable
class Rater(Protocol):
    """Protocol for blind voice/quality raters."""

    def rate(self, input: RaterInput) -> RaterOutput:
        ...


class KeywordRater:
    """Deterministic rater — no LLM. Scores based on rubric positive_criteria
    keyword presence in candidate text. For tests + dev.

    Rubric shape expected:
        {
            "positive_criteria": [
                {"id": "ai_perspective", "text": "...", "keywords": ["...", "..."]},
                ...
            ],
            "hard_disqualifiers": [
                {"id": "sycophancy", "keywords": ["totally agree", "great point"]},
                ...
            ],
        }

    Score = (matched positive criteria) / (total positive criteria). Hard
    disqualifier match → score 0.0.
    """

    def __init__(self, rubric: dict):
        self.rubric = rubric

    def rate(self, input: RaterInput) -> RaterOutput:
        text_parts = []
        # Try common candidate field names
        for key in ("draft_text", "text", "content", "draft_content"):
            if key in input.candidate:
                text_parts.append(str(input.candidate[key]))
        text = " ".join(text_parts).lower()

        if not text:
            return RaterOutput(score=0.0, notes="empty candidate text")

        # Hard disqualifier check
        for dq in self.rubric.get("hard_disqualifiers", []):
            for kw in dq.get("keywords", []):
                if kw.lower() in text:
                    return RaterOutput(
                        score=0.0,
                        notes=f"hard disqualifier hit: {dq.get('id', kw)}",
                        metadata={"disqualifier": dq.get("id")},
                    )

        # Positive criteria
        criteria = self.rubric.get("positive_criteria", [])
        if not criteria:
            return RaterOutput(score=0.5, notes="no positive criteria defined; neutral score")

        matched_ids = []
        for crit in criteria:
            kws = crit.get("keywords", [])
            if any(kw.lower() in text for kw in kws):
                matched_ids.append(crit.get("id", "?"))

        score = len(matched_ids) / len(criteria)
        notes = f"matched {len(matched_ids)}/{len(criteria)}: {', '.join(matched_ids) or 'none'}"
        return RaterOutput(
            score=score,
            notes=notes,
            metadata={"matched_criteria": matched_ids},
        )


class LLMJudgeRater:
    """Generic LLM-as-judge rater. Accepts any LLMAdapter.

    The system prompt is configurable so downstream packages can specialize
    (e.g. pebbles-presence's ReefRater will pre-fill the system prompt with
    Reef's identity excerpt).
    """

    DEFAULT_SYSTEM_PROMPT = (
        "You rate candidate text against a voice rubric. Score from 0.0 to 1.0 "
        "(0=poor match, 1=excellent match). Your output is JSON: "
        '{"score": float, "notes": "one line, max 200 chars"}. '
        "You receive only the candidate, the rubric, and voice corpus excerpts — "
        "no self-scores from the drafter, no internal reasoning. Score blind."
    )

    def __init__(
        self,
        llm: LLMAdapter,
        system_prompt: Optional[str] = None,
    ):
        self.llm = llm
        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT

    def rate(self, input: RaterInput) -> RaterOutput:
        user_msg_parts = []
        if input.target_context:
            user_msg_parts.append(f"Target context:\n{input.target_context}")
        user_msg_parts.append(f"Candidate:\n{input.candidate}")
        user_msg_parts.append(f"Rubric:\n{input.rubric}")
        if input.voice_corpus_excerpts:
            joined = "\n---\n".join(input.voice_corpus_excerpts[:10])
            user_msg_parts.append(f"Voice corpus excerpts:\n{joined}")

        user_msg = "\n\n".join(user_msg_parts)

        try:
            data = self.llm.complete_json(
                system=self.system_prompt,
                messages=[{"role": "user", "content": user_msg}],
                schema={"score": "number 0-1", "notes": "string max 200 chars"},
            )
        except Exception as e:
            logger.error(f"LLMJudgeRater call failed: {e}")
            raise

        score = float(data.get("score", 0.0))
        notes = str(data.get("notes", ""))
        return RaterOutput(score=score, notes=notes, metadata={"raw": data})
