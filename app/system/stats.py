from typing import Callable


LengthCounter = Callable[[str], str]
LengthResult = Callable[[], int]


def create_length_counter() -> tuple[LengthCounter, LengthResult]:
    total = 0

    def length_counter(text: str) -> str:
        nonlocal total

        total += len(text)
        return text

    def length_result() -> int:
        return total

    return length_counter, length_result
