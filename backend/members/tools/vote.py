class VoteBox:
    """Simple helper that stores votes and can be exposed as an agent tool."""

    def __init__(self) -> None:
        self._scores: list[float] = []

    def reset(self) -> None:
        """Clear any prior votes."""
        self._scores.clear()

    def vote(self, name: str, score: float) -> str:
        """Vote (0-1) and provide your name."""
        print(f"Vote recorded for {name} with score: {score}")
        self._scores.append(score)
        return "Vote recorded."

    def result(self) -> float:
        """Return trimmed-average confidence across all collected votes."""
        if not self._scores:
            return 0.0

        if len(self._scores) <= 2:
            return sum(self._scores) / len(self._scores)

        trimmed_scores = sorted(self._scores)[1:-1]
        return sum(trimmed_scores) / len(trimmed_scores)


vote_box = VoteBox()


def prepare_vote_tool() -> None:
    """Initialize/reset the shared vote box."""
    vote_box.reset()


def vote(identifier: str, score: float) -> str:
    """Record a vote using the shared vote box."""
    return vote_box.vote(identifier, score)


def get_vote_result() -> float:
    """Fetch the trimmed-average score from the shared vote box."""
    return vote_box.result()
