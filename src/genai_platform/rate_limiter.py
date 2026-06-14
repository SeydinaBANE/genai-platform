import time


class TokenBucket:
    def __init__(self, rpm: int, tpm: int):
        self.rpm = rpm
        self.tpm = tpm
        self._request_times: list[float] = []
        self._token_usage: list[tuple[int, float]] = []

    def check(self, tokens: int = 0) -> bool:
        now = time.time()
        window = 60.0
        self._request_times = [t for t in self._request_times if now - t < window]
        if len(self._request_times) >= self.rpm:
            return False
        if self.tpm > 0 and tokens > 0:
            self._token_usage = [(c, t) for c, t in self._token_usage if now - t < window]
            total = sum(c for c, _ in self._token_usage)
            if total + tokens > self.tpm:
                return False
        return True

    def consume(self, tokens: int = 0) -> None:
        now = time.time()
        self._request_times.append(now)
        if tokens > 0:
            self._token_usage.append((tokens, now))


class RateLimiter:
    def __init__(self, rpm: int = 1000, tpm: int = 100000):
        self._buckets: dict[str, TokenBucket] = {}
        self.rpm = rpm
        self.tpm = tpm

    def _get_bucket(self, key: str) -> TokenBucket:
        if key not in self._buckets:
            self._buckets[key] = TokenBucket(self.rpm, self.tpm)
        return self._buckets[key]

    def check(self, key: str, tokens: int = 0) -> bool:
        return self._get_bucket(key).check(tokens)

    def consume(self, key: str, tokens: int = 0) -> None:
        self._get_bucket(key).consume(tokens)
