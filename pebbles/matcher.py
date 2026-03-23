"""Interest matching with keyword and optional semantic modes."""

import logging
from typing import Optional

from pebbles.models import Pebble, Interest

logger = logging.getLogger(__name__)


class InterestMatcher:
    """Matches pebbles to interests using keyword or semantic similarity."""
    
    def __init__(
        self,
        use_semantic: bool = False,
        semantic_threshold: float = 0.35
    ):
        """
        Initialize matcher.
        
        Args:
            use_semantic: Enable semantic matching (requires sentence-transformers)
            semantic_threshold: Minimum cosine similarity for semantic match (0-1)
        """
        self.use_semantic = use_semantic
        self.semantic_threshold = semantic_threshold
        self.model = None
        
        if use_semantic:
            try:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer('all-MiniLM-L6-v2')
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
        """
        Score how well a pebble matches an interest.
        
        Args:
            pebble: The pebble to score
            interest: The interest to match against
            
        Returns:
            Score from 0.0 (no match) to 1.0 (perfect match)
        """
        # Check negative keywords first (hard exclusion)
        pebble_text = f"{pebble.title} {pebble.description}".lower()
        for neg in interest.negative_keywords:
            if neg.lower() in pebble_text:
                return 0.0
        
        if self.use_semantic and self.model:
            return self._semantic_score(pebble, interest)
        else:
            return self._keyword_score(pebble, interest)
    
    def is_match(self, pebble: Pebble, interest: Interest) -> bool:
        """
        Check if a pebble matches an interest.
        
        Args:
            pebble: The pebble to check
            interest: The interest to match against
            
        Returns:
            True if the pebble matches the interest
        """
        score = self.score(pebble, interest)
        
        if self.use_semantic:
            # Semantic: threshold-based
            return score >= self.semantic_threshold
        else:
            # Keyword: any match (score > 0)
            return score > 0.0
    
    def _keyword_score(self, pebble: Pebble, interest: Interest) -> float:
        """Score using keyword matching."""
        pebble_text = f"{pebble.title} {pebble.description}".lower()
        
        # Check tags first (exact match)
        for tag in interest.tags:
            if tag.lower() in pebble_text:
                return 1.0
        
        # Check keywords (any match gets 0.7)
        for keyword in interest.keywords:
            if keyword.lower() in pebble_text:
                return 0.7
        
        return 0.0
    
    def _semantic_score(self, pebble: Pebble, interest: Interest) -> float:
        """Score using semantic similarity."""
        if not self.model:
            return self._keyword_score(pebble, interest)
        
        try:
            # Build interest query from tags and keywords
            interest_text = " ".join(interest.tags + interest.keywords)
            pebble_text = f"{pebble.title} {pebble.description}"
            
            # Encode and compute cosine similarity
            embeddings = self.model.encode([interest_text, pebble_text])
            
            # Cosine similarity
            from numpy import dot
            from numpy.linalg import norm
            
            similarity = dot(embeddings[0], embeddings[1]) / (
                norm(embeddings[0]) * norm(embeddings[1])
            )
            
            # Clamp to 0-1
            return max(0.0, min(1.0, float(similarity)))
            
        except Exception as e:
            logger.warning(f"Semantic scoring failed, falling back to keyword: {e}")
            return self._keyword_score(pebble, interest)"""Smart matching engine for Pebbles.

Supports two modes:
- Keyword matching (default, no dependencies)
- Semantic matching (opt-in, requires sentence-transformers)
"""

import logging
from typing import Optional

from pebbles.models import Interest, Pebble

logger = logging.getLogger(__name__)


class InterestMatcher:
    """Matches Pebbles to Interests using keyword or semantic similarity."""
    
    def __init__(
        self,
        use_semantic: bool = False,
        semantic_threshold: float = 0.35
    ):
        self.use_semantic = use_semantic
        self.semantic_threshold = semantic_threshold
        self.model = None
        
        if use_semantic:
            try:
                from sentence_transformers import SentenceTransformer
                import numpy as np
                self.model = SentenceTransformer('all-MiniLM-L6-v2')
                self.np = np
                logger.info("Semantic matching enabled with all-MiniLM-L6-v2")
            except ImportError:
                logger.warning(
                    "sentence-transformers not available, falling back to keyword matching"
                )
                self.use_semantic = False
    
    def score(self, pebble: Pebble, interest: Interest) -> float:
        """Score how well a pebble matches an interest (0.0–1.0)."""
        if self.use_semantic and self.model:
            return self._semantic_score(pebble, interest)
        return self._keyword_score(pebble, interest)
    
    def is_match(self, pebble: Pebble, interest: Interest) -> bool:
        """Check if pebble matches interest, respecting negative keywords."""
        # Check negative keywords first (fast reject)
        text = f"{pebble.title} {pebble.content or ''}".lower()
        for neg in interest.negative_keywords:
            if neg.lower() in text:
                logger.debug(f"Rejected '{pebble.title}' for '{interest.name}' (negative: {neg})")
                return False
        
        # Check positive match
        score = self.score(pebble, interest)
        threshold = self.semantic_threshold if self.use_semantic else 0.0
        return score > threshold
    
    def _keyword_score(self, pebble: Pebble, interest: Interest) -> float:
        """Simple keyword matching — returns 1.0 if any keyword matches, else 0.0."""
        text = f"{pebble.title} {pebble.content or ''}".lower()
        
        # Check tags first
        for tag in interest.tags:
            if tag.lower() in text:
                return 1.0
        
        # Check keywords
        for keyword in interest.keywords:
            if keyword.lower() in text:
                return 1.0
        
        return 0.0
    
    def _semantic_score(self, pebble: Pebble, interest: Interest) -> float:
        """Semantic similarity using sentence transformers."""
        if not self.model:
            return self._keyword_score(pebble, interest)
        
        pebble_text = f"{pebble.title} {pebble.content or ''}"
        interest_text = " ".join(interest.tags + interest.keywords)
        
        embeddings = self.model.encode([pebble_text, interest_text])
        similarity = self.np.dot(embeddings[0], embeddings[1]) / (
            self.np.linalg.norm(embeddings[0]) * self.np.linalg.norm(embeddings[1])
        )
        
        return float(similarity)