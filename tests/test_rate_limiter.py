import time

from genai_platform.domain.rate_limiting import RateLimiter, TokenBucket


class TestTokenBucket:
    def test_init(self) -> None:
        bucket = TokenBucket(rpm=100, tpm=1000)
        assert bucket.rpm == 100
        assert bucket.tpm == 1000

    def test_check_allows_within_limit(self) -> None:
        bucket = TokenBucket(rpm=100, tpm=1000)
        assert bucket.check() is True

    def test_check_blocks_exceeded_rpm(self) -> None:
        bucket = TokenBucket(rpm=2, tpm=1000)
        assert bucket.check() is True
        bucket.consume()
        assert bucket.check() is True
        bucket.consume()
        assert bucket.check() is False

    def test_check_blocks_exceeded_tpm(self) -> None:
        bucket = TokenBucket(rpm=1000, tpm=10)
        assert bucket.check(tokens=8) is True
        bucket.consume(tokens=8)
        assert bucket.check(tokens=5) is False

    def test_window_expires_requests(self) -> None:
        bucket = TokenBucket(rpm=1, tpm=1000)
        assert bucket.check() is True
        bucket.consume()
        assert bucket.check() is False
        old_time = time.time() - 120
        bucket._request_times = [old_time]
        assert bucket.check() is True


class TestRateLimiter:
    def test_init(self) -> None:
        rl = RateLimiter(rpm=500, tpm=50000)
        assert rl.rpm == 500
        assert rl.tpm == 50000

    def test_check_creates_bucket_per_key(self) -> None:
        rl = RateLimiter(rpm=1, tpm=1000)
        assert rl.check("user_a") is True
        rl.consume("user_a")
        assert rl.check("user_a") is False
        assert rl.check("user_b") is True

    def test_check_with_tokens(self) -> None:
        rl = RateLimiter(rpm=1000, tpm=10)
        assert rl.check("user", tokens=8) is True
        rl.consume("user", tokens=8)
        assert rl.check("user", tokens=5) is False
