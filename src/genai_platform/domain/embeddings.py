import hashlib
import random


def mock_embedding(text: str) -> list[float]:
    seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    return [rng.random() for _ in range(1536)]
