"""Shared prompt-response parsing helpers.

The engine's prompt contracts (uptake.py, reframe.py, conductor.py) all use the
same `LABEL: value` format, and all need to tolerate a model bolding the label
(`**LABEL:**`, `**LABEL**:`, or plain) without that decoration leaking into, or
corrupting, the captured value.

The tolerance lives here, in one place, on purpose: it was previously done by
`raw_text.replace("*", "")` independently in all three modules, which stripped
*every* asterisk from the whole response, silently deleting in-content emphasis,
math (`price * volume`), and glob/footnote markers from the debater arguments and
the disagreement map the tool exists to report faithfully. Matching the bold only
around the label, and never touching the captured value, is the fix.
"""

from __future__ import annotations


def label(name: str) -> str:
    r"""Regex fragment matching `NAME:` with optional markdown-bold decoration
    plus trailing inline spaces, so it can be prepended to a value-capturing
    group. `name` is a literal word or words (e.g. "OPEN QUESTION").

    Known, accepted edge: a value beginning with a literal `*` *immediately*
    after the colon with no space (e.g. `TARGET:*nix`) may have up to two leading
    asterisks absorbed as a stray bold marker. Real responses put a space after
    the colon, and this is vastly narrower than the old strip-every-asterisk
    approach it replaces.
    """
    return rf"\*{{0,2}}{name}\*{{0,2}}:\*{{0,2}}[ \t]*"
