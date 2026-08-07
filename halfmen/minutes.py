"""Minutes of league meetings, kept verbatim.

The rulebook is the formal record of what got decided. This is the other one,
and it is the one anybody will actually reread in three years. Transcribed
exactly as taken - the jokes are the point, so nothing here is tidied up,
paraphrased or improved.

Add a meeting by appending to MEETINGS, newest first.
"""
from __future__ import annotations

from typing import Any, Dict, List

# Each item is (line, [sub-items]); a sub-item is itself (line, [deeper]).
MEETINGS: List[Dict[str, Any]] = [
    {
        "date": "2026-08-06",
        "title": "Founding meeting",
        "minuted_by": "Thad Harter",
        "note": "The one where the rules were explained and both draft orders were drawn.",
        "items": [
            ("Hellos and Catching Up", []),
            ("Welcoming Statement by Brandon", [
                ("He couldn&rsquo;t remember when the league was formed. Very embarrassing.", []),
                ("Called out Austin a horrible person", []),
                ("Brandon said he touched Thad and Josh (about the league)", []),
            ]),
            ("Explanation of League Rules", [
                ("Brandon told everyone to stop him if they had questions", [
                    ("Lucas stopped him immediately", []),
                ]),
                ("Taxi system was explained", [
                    ("Brandon shared about how long different guys &ldquo;last&rdquo;", []),
                ]),
                ("Devin had no questions", []),
            ]),
            ("Explanation of Pot and the Lottery "
             "(Corey&rsquo;s two favorite Friday night activities)", [
                 ("Isaiah wanted to know if there was a live stream of our balls", []),
             ]),
            ("Rookie Lottery Selection", [
                ("Thad got screwed", []),
            ]),
            ("Veteran Lottery Selection", []),
            ("Discussion on Buy-In", [
                ("&ldquo;Ground Beef is our Gold Standard&rdquo;", []),
                ("Isaiah said he likes one-ways", []),
            ]),
            ("Meeting Abruptly Ended", [
                ("Very rude", []),
            ]),
        ],
    },
]


def count() -> int:
    return len(MEETINGS)


def latest() -> Dict[str, Any]:
    return MEETINGS[0] if MEETINGS else {}
