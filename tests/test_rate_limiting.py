from rate_limiter import RateLimiter

def test_rate_limiting():
    limiter = RateLimiter(requests_per_minute=2)
    ip = "192.168.1.1"
    
    assert limiter.is_allowed(ip)  # First request
    assert limiter.is_allowed(ip)  # Second request
    assert not limiter.is_allowed(ip)  # Third request 