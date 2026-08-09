"""Weekly challenges — templates across the 4 personas with accept/skip/
completed tracking (challenges table).

Pick is deterministic per week (stable hash), phase-filtered, and never
repeats within the same week (skip counts as used).
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass


@dataclass(frozen=True)
class ChallengeTemplate:
    persona: str
    phase: str  # any | base | build | peak | taper
    title: str
    description: str
    completion_note: str


TEMPLATES: tuple[ChallengeTemplate, ...] = (
    # runner
    ChallengeTemplate(
        "runner", "any", "Strides week",
        "3× after easy runs: 4×100m strides, smooth and fast, full recovery.",
        "strides done 3×",
    ),
    ChallengeTemplate(
        "runner", "base", "Consistency week",
        "Complete all 3 planned runs. No heroics — just showing up.",
        "3/3 runs completed",
    ),
    ChallengeTemplate(
        "runner", "build", "Negative-split long run",
        "Saturday long run: second half 5–10 s/km faster than the first.",
        "negative split done",
    ),
    ChallengeTemplate(
        "runner", "taper", "Trust the taper",
        "No extra miles, no pace heroics. The work is done.",
        "taper respected",
    ),
    # calisthenics
    ChallengeTemplate(
        "calisthenics", "any", "Plank hold ladder",
        "Plank 3×60s, plus one 20s bonus hold on Friday.",
        "plank ladder done",
    ),
    ChallengeTemplate(
        "calisthenics", "any", "Pull-up negatives",
        "3×5 slow negatives (3s lowering) on Monday.",
        "negatives done",
    ),
    ChallengeTemplate(
        "calisthenics", "base", "Tibial raise bank",
        "3×15 tibial raises every leg day — shin splint armor.",
        "tibial raises done",
    ),
    # mobility
    ChallengeTemplate(
        "mobility", "any", "Daily 10",
        "The 10-minute head-to-toe routine, 6 of 7 days.",
        "6/7 days done",
    ),
    ChallengeTemplate(
        "mobility", "any", "Quad stretch streak",
        "2×45s quad stretch after EVERY session this week.",
        "streak kept",
    ),
    # physio
    ChallengeTemplate(
        "physio", "any", "No-go zone check",
        "Daily honest self-check: sharp pain, swelling, night pain? Log it.",
        "7 days checked",
    ),
    ChallengeTemplate(
        "physio", "any", "Calf raise bank",
        "3×15 calf raises daily — tendon health maintenance.",
        "daily raises done",
    ),
)


def _stable_index(week_start: str, phase: str, size: int) -> int:
    return zlib.crc32(f"{week_start}:{phase}".encode()) % size


def pick_template(conn, week_start: str, phase: str) -> ChallengeTemplate | None:
    """Deterministic per-week pick, phase-filtered, skipping used titles."""
    used = {
        row["title"]
        for row in conn.execute(
            "SELECT title FROM challenges WHERE week_start = ?", (week_start,)
        )
    }
    pool = [
        t for t in TEMPLATES if (t.phase == "any" or t.phase == phase) and t.title not in used
    ]
    if not pool:
        return None
    return pool[_stable_index(week_start, phase, len(pool))]


def accept_challenge(conn, week_start: str, template: ChallengeTemplate) -> int:
    cursor = conn.execute(
        "INSERT INTO challenges (week_start, title, description, persona, accepted) "
        "VALUES (?, ?, ?, ?, 1)",
        (week_start, template.title, template.description, template.persona),
    )
    conn.commit()
    return int(cursor.lastrowid)


def skip_challenge(conn, week_start: str, title: str) -> None:
    """Record as used (accepted=0) so the week's pick won't repeat it."""
    conn.execute(
        "INSERT INTO challenges (week_start, title, accepted) VALUES (?, ?, 0)",
        (week_start, title),
    )
    conn.commit()


def mark_completed(conn, challenge_id: int) -> None:
    conn.execute(
        "UPDATE challenges SET completed = 1, completed_at = datetime('now') "
        "WHERE id = ?",
        (challenge_id,),
    )
    conn.commit()


def week_challenges(conn, week_start: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM challenges WHERE week_start = ? ORDER BY id", (week_start,)
    ).fetchall()
    return [dict(row) for row in rows]
