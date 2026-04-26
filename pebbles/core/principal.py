"""Principal — a speaking identity with hierarchy support."""

import os
import re
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field


class Principal(BaseModel):
    """A speaking identity — the agent or human-on-whose-behalf this work happens.

    Distinct from `pebbles.models.Recipient` (a *receiving* identity, used by the
    user-as-recipient v0.1 use case). A Principal is who the system is *acting as*.

    Supports hierarchy: a Principal can summon child Principals (e.g., Scout
    summons Presence). v0.2 lays the rails; full hierarchy use comes in v0.3+.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Identity
    id: str
    name: str
    mode: str  # free string — "ai_persona", "employer_representative", future modes

    # Hierarchy — agents summoning agents
    parent_id: Optional[str] = None
    children: list[str] = Field(default_factory=list)
    delegation_scope: dict = Field(default_factory=dict)
    # delegation_scope example:
    #   {"presence_v1": {"actions": ["draft", "rate"], "auto_approve": False}}
    # Per-child rules — what authority transfers when this Principal summons that child.
    # Core does not enforce these; downstream consumers (Presence, Scout) interpret.

    # Voice anchors
    voice_corpus: list[str] = Field(default_factory=list)  # URLs or local paths
    voice_anchors: dict = Field(default_factory=dict)
    # voice_anchors example: {"soul_file": "/Users/song/mysong/SOUL.md", "blog": "https://themeatfinger.com"}

    # Rubric — opaque dict at this layer; downstream interprets
    rubric: dict = Field(default_factory=dict)

    # Disclosure policy (load-bearing for Presence)
    disclosure: dict = Field(default_factory=dict)
    # disclosure example: {"when_directly_asked": "honest", "claim_human": "never"}

    # Free-form additional config — Scout uses for clusters, Presence for thresholds
    extra: dict = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: Path | str) -> "Principal":
        """Load a Principal from a YAML file.

        Expands ${VAR} references against os.environ so secrets / paths
        can live in env vars.
        """
        with open(path) as f:
            raw = f.read()
        raw = re.sub(r"\$\{([A-Z_][A-Z0-9_]*)\}", lambda m: os.environ.get(m.group(1), ""), raw)
        data = yaml.safe_load(raw) or {}
        return cls(**data)

    def load_child(
        self, child_id: str, search_paths: list[Path | str] | None = None
    ) -> "Principal":
        """Load a child Principal by id from sibling YAML files.

        Searches for `<child_id>.yaml` in each of `search_paths`. Sets the
        loaded child's `parent_id` to this Principal's id automatically.

        Raises FileNotFoundError if no matching file is found.
        Raises ValueError if `child_id` is not in `self.children`.
        """
        if child_id not in self.children:
            raise ValueError(
                f"Principal '{self.id}' did not declare '{child_id}' in its children list. "
                f"Declared children: {self.children}"
            )

        search_paths = search_paths or [Path.cwd()]
        for base in search_paths:
            candidate = Path(base) / f"{child_id}.yaml"
            if candidate.exists():
                child = Principal.from_yaml(candidate)
                # Auto-set parent_id; YAML doesn't need to specify it
                if child.parent_id is None:
                    child.parent_id = self.id
                return child

        raise FileNotFoundError(
            f"Could not find Principal '{child_id}' in any of: {search_paths}"
        )

    def authority_for(self, child_id: str) -> dict:
        """Return the delegation_scope dict for a given child, or empty if undefined."""
        return self.delegation_scope.get(child_id, {})
