"""retrieval.py tests — hermetic via TfEmbedder, no model download."""

from db import init_db
from ingest_kb import chunk_markdown, ingest_kb
from retrieval import TfEmbedder, decode_blob, retrieve


def _make_corpus(tmp_path):
    """Small two-persona corpus with obvious token overlap for queries."""
    physio = tmp_path / "physio"
    runner = tmp_path / "runner"
    physio.mkdir()
    runner.mkdir()
    (physio / "shin_splints.md").write_text(
        "# Shin Splints\n\nShin pain after long runs. Reduce volume, calf "
        "raises daily, pain-monitored loading.\n\n"
        "## Return to run\n\nPain-free walking first, then easy running at "
        "50% volume."
    )
    (physio / "quad_tendonitis.md").write_text(
        "# Quad Tendonitis\n\nPain at the bottom of the kneecap. Isometric "
        "wall sits first, then slow decline squats."
    )
    (runner / "pacing.md").write_text(
        "# Pacing\n\nSELMAR target 2:30:00 at 7:06 per km. Negative split the "
        "race. Easy runs at 7:45 to 8:15."
    )
    return tmp_path


def _ingested(tmp_path):
    conn = init_db(":memory:")
    count = ingest_kb(conn, TfEmbedder(), _make_corpus(tmp_path))
    return conn, count


def test_ingest_populates_chunks(tmp_path) -> None:
    conn, count = _ingested(tmp_path)
    assert count >= 3
    rows = conn.execute("SELECT persona, count(*) AS n FROM kb_chunks GROUP BY persona").fetchall()
    personas = {r["persona"]: r["n"] for r in rows}
    assert personas["physio"] >= 2
    assert personas["runner"] >= 1


def test_retrieval_surfaces_physio_chunk_for_shin_pain(tmp_path) -> None:
    conn, _ = _ingested(tmp_path)
    hits = retrieve(
        conn, TfEmbedder(), "physio", "shin pain after long run",
        threshold=TfEmbedder.THRESHOLD,
    )
    assert hits, "expected a physio match"
    assert hits[0].score >= TfEmbedder.THRESHOLD
    assert "shin" in hits[0].content.lower()


def test_below_threshold_returns_empty(tmp_path) -> None:
    conn, _ = _ingested(tmp_path)
    # 0.8 is above any possible cosine here — deterministically no match.
    hits = retrieve(
        conn, TfEmbedder(), "physio", "quantum physics of tea brewing",
        threshold=0.8,
    )
    assert hits == []


def test_top_k_and_ordering(tmp_path) -> None:
    conn, _ = _ingested(tmp_path)
    hits = retrieve(
        conn, TfEmbedder(), "physio", "shin splints pain knee",
        top_k=1, threshold=TfEmbedder.THRESHOLD,
    )
    assert len(hits) == 1
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_persona_isolation(tmp_path) -> None:
    """runner corpus never matches physio queries and vice versa."""
    conn, _ = _ingested(tmp_path)
    threshold = TfEmbedder.THRESHOLD
    assert retrieve(conn, TfEmbedder(), "runner", "shin pain after long run", threshold=threshold) == []
    assert retrieve(conn, TfEmbedder(), "physio", "negative split pacing", threshold=threshold) == []


def test_embedding_blob_roundtrip() -> None:
    import numpy as np

    vec = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    assert np.array_equal(decode_blob(vec.tobytes()), vec)
