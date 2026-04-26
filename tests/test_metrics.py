"""Tests for pebbles.core.metrics."""

import json
from pathlib import Path

from pebbles.core.metrics import InMemoryMetrics, JsonFileMetrics


def test_in_memory_emit_records_event():
    m = InMemoryMetrics()
    m.emit("song", "draft_queued", value=1.0, metadata={"item_id": "abc"})
    assert len(m.events) == 1
    e = m.events[0]
    assert e["principal_id"] == "song"
    assert e["metric_type"] == "draft_queued"
    assert e["value"] == 1.0
    assert e["metadata"] == {"item_id": "abc"}
    assert "occurred_at" in e


def test_in_memory_emit_no_value_no_metadata():
    m = InMemoryMetrics()
    m.emit("song", "drafter_paused")
    assert m.events[0]["value"] is None
    assert m.events[0]["metadata"] == {}


def test_in_memory_filter_by_principal():
    m = InMemoryMetrics()
    m.emit("song", "x")
    m.emit("kai", "x")
    song_events = m.filter(principal_id="song")
    assert len(song_events) == 1
    assert song_events[0]["principal_id"] == "song"


def test_in_memory_filter_by_metric_type():
    m = InMemoryMetrics()
    m.emit("song", "draft_queued")
    m.emit("song", "draft_disqualified")
    queued = m.filter(metric_type="draft_queued")
    assert len(queued) == 1


def test_in_memory_filter_combined():
    m = InMemoryMetrics()
    m.emit("song", "x")
    m.emit("song", "y")
    m.emit("kai", "x")
    out = m.filter(principal_id="song", metric_type="x")
    assert len(out) == 1
    assert out[0]["principal_id"] == "song"
    assert out[0]["metric_type"] == "x"


def test_jsonfile_metrics_appends_jsonl(tmp_path: Path):
    path = tmp_path / "subdir" / "metrics.jsonl"
    m = JsonFileMetrics(path)
    m.emit("song", "draft_queued", value=1.0, metadata={"item_id": "abc"})
    m.emit("song", "draft_disqualified")

    assert path.exists()
    lines = path.read_text().strip().split("\n")
    assert len(lines) == 2
    e1 = json.loads(lines[0])
    e2 = json.loads(lines[1])
    assert e1["metric_type"] == "draft_queued"
    assert e1["value"] == 1.0
    assert e2["value"] is None


def test_jsonfile_metrics_creates_parent_dirs(tmp_path: Path):
    """Parent directories should be created automatically."""
    deep_path = tmp_path / "a" / "b" / "c" / "metrics.jsonl"
    m = JsonFileMetrics(deep_path)
    m.emit("song", "test_metric")
    assert deep_path.exists()
