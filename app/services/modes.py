"""Mode registry — orthogonal to Persona (tone) and to each other: a Mode is
*how* the answer is shaped (depth, structure), not *who* is speaking. Same
data-driven registry pattern as personas.py, for the same reason: adding
mode N+1 later is one entry here, not a code change elsewhere."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Mode:
    id: str
    name: str
    description: str
    prompt: str


_REGISTRY: dict[str, Mode] = {}


def register(mode: Mode) -> None:
    _REGISTRY[mode.id] = mode


def get_mode(mode_id: str | None) -> Mode:
    return _REGISTRY.get(mode_id or DEFAULT_MODE_ID, _REGISTRY[DEFAULT_MODE_ID])


def list_modes() -> list[Mode]:
    return list(_REGISTRY.values())


DEFAULT_MODE_ID = "answering"

register(Mode(
    id="answering",
    name="Answering",
    description="Direct and concise — the default.",
    prompt="Mode: Answering. Lead with the direct answer, not a preamble. Be concise.",
))

register(Mode(
    id="explaining",
    name="Explaining",
    description="Walks through the reasoning behind the answer, briefly.",
    prompt=(
        "Mode: Explaining. Don't just state the answer — briefly walk through the "
        "reasoning or context behind it, so the user understands *why*, not just "
        "*what*. Still concise, just not bare."
    ),
))

register(Mode(
    id="teaching",
    name="Teaching",
    description="Breaks answers into steps and checks understanding.",
    prompt=(
        "Mode: Teaching. Break the answer into small steps if it has more than one "
        "part. Check understanding where it matters — a brief question back — "
        "rather than a one-way lecture."
    ),
))

register(Mode(
    id="review",
    name="Review",
    description="Critiques code or documents directly — for code/doc review.",
    prompt=(
        "Mode: Review. You're critiquing, not just describing. Point out issues, "
        "risks, or improvements directly — don't soften real problems into vague "
        "positivity. Still cite the specific passage/file the issue is in."
    ),
))

register(Mode(
    id="summary",
    name="Summary",
    description="Condenses into key points only.",
    prompt=(
        "Mode: Summary. Condense to the key points only — bullet-style is fine. "
        "Skip detail that doesn't change the takeaway."
    ),
))
