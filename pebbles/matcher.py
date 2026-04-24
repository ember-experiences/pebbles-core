"""Interest matching with keyword and optional semantic modes."""

import logging

from pebbles.models import Pebble, Interest

logger = logging.getLogger(__name__)


class InterestMatcher:
    """Matches pebbles to interests using keyword or semantic similarity.

    Uses `pebble.title + pebble.description` as the text to match against,
    consistent with the Pebble model in pebbles.models.

    Priority-scored matching — pairs well with Scout's cluster watchlists
    when ranking candidates.
    """

    def __init__(
        self,
        use_semantic: bool = False,
        semantic_threshold: float = 0.35,
    ):
        self.use_semantic = use_semantic
        self.semantic_threshold = semantic_threshold
        self.model = None

        if use_semantic:
            try:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("Semantic matching enabled with all-MiniLM-L6-v2")
            except ImportError:
                logger.warning(
                    "sentence-transformers not available, falling back to keyword matching"
                )
                self.use_semantic = False
            except Exception as e:
                logger.warning(
                    f"Failed to load semantic model, falling back to keyword: {e}"
                )
                self.use_semantic = False

    def score(self, pebble: Pebble, interest: Interest) -> float:
        """Score how well a pebble matches an interest (0.0 to 1.0)."""
        pebble_text = f"{pebble.title} {pebble.description}".lower()
        for neg in interest.negative_keywords:
            if neg.lower() in pebble_text:
                return 0.0

        if self.use_semantic and self.model:
            return self._semantic_score(pebble, interest)
        return self._keyword_score(pebble, interest)

    def is_match(self, pebble: Pebble, interest: Interest) -> bool:
        """Check if a pebble matches an interest."""
        score = self.score(pebble, interest)
        if self.use_semantic:
            return score >= self.semantic_threshold
        return score > 0.0

    def _keyword_score(self, pebble: Pebble, interest: Interest) -> float:
        """Score using keyword matching. Tags match = 1.0, keywords = 0.7."""
        pebble_text = f"{pebble.title} {pebble.description}".lower()

        for tag in interest.tags:
            if tag.lower() in pebble_text:
                return 1.0

        for keyword in interest.keywords:
            if keyword.lower() in pebble_text:
                return 0.7

        return 0.0

    def _semantic_score(self, pebble: Pebble, interest: Interest) -> float:
        """Score using semantic similarity via sentence-transformers."""
        if not self.model:
            return self._keyword_score(pebble, interest)

        try:
            interest_text = " ".join(interest.tags + interest.keywords)
            pebble_text = f"{pebble.title} {pebble.description}"

            embeddings = self.model.encode([interest_text, pebble_text])

            from numpy import dot
            from numpy.linalg import norm

            similarity = dot(embeddings[0], embeddings[1]) / (
                norm(embeddings[0]) * norm(embeddings[1])
            )

            return max(0.0, min(1.0, float(similarity)))

        except Exception as e:
            logger.warning(f"Semantic scoring failed, falling back to keyword: {e}")
            return self._keyword_score(pebble, interest)
