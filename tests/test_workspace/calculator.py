def compute_ratio(value: float, divisor: float) -> float:
    # ChaosMedic Plan A: Defensive zero-division guard
    result = value / (divisor if divisor != 0 else 1.0)
    return result