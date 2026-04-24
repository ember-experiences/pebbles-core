"""Lightweight entity extraction for RecentContext keying.

Two modes:
  - fast: regex heuristics (no API call, works offline, good for names/places)
  - rich: Claude-backed extraction (better recall, costs a token call)

For the drive-home → photo failure specifically, 'fast' mode would have caught
"Robert" and "Doheny" without any API call.
"""

import re
from typing import Optional


# Common words that look like proper nouns but aren't useful entities
_STOPWORDS = {
    "I", "The", "A", "An", "It", "He", "She", "They", "We", "You",
    "This", "That", "There", "Here", "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday", "Sunday", "January", "February",
    "March", "April", "May", "June", "July", "August", "September",
    "October", "November", "December",
}


def extract_entities_fast(text: str) -> list[str]:
    """Heuristic entity extraction — no API needed.

    Finds capitalized tokens (likely names/places). Returns lowercase deduplicated list.
    Names at sentence-start are included — we'd rather over-extract than miss "Robert".
    """
    # All capitalized words (3+ chars) — includes sentence-initial
    tokens = re.findall(r'\b([A-Z][a-z]{2,})\b', text)
    # Also catch ALL-CAPS short tokens (beach/break names like "OB", "PB")
    tokens += re.findall(r'\b([A-Z]{2,5})\b', text)

    entities = set()
    for tok in tokens:
        if tok not in _STOPWORDS and len(tok) >= 2:
            entities.add(tok.lower())

    return sorted(entities)


async def extract_entities_rich(text: str, api_key: str) -> list[str]:
    """Claude-backed entity extraction for higher recall.

    Use this when you want to catch entities mentioned indirectly,
    e.g. "he got a great wave" in a context where 'he' = Robert.
    """
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=api_key)

    message = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": (
                "Extract all named entities (people, places, activities) from this text. "
                "Return only a JSON array of lowercase strings, nothing else.\n\n"
                f"Text: {text}"
            ),
        }],
    )

    import json
    raw = message.content[0].text.strip()
    # Strip markdown fences if present
    raw = re.sub(r'^```json\s*|\s*```$', '', raw, flags=re.MULTILINE).strip()
    entities = json.loads(raw)
    return [str(e).lower() for e in entities if isinstance(e, str)]
