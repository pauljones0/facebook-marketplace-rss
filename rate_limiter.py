from functools import wraps
from flask import request, Response
import time
from collections import defaultdict
import threading

class RateLimiter:
    def __init__(self, requests_per_minute: int):
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)
        self.lock = threading.Lock()

    def is_allowed(self, ip: str) -> bool:
        now = time.time()
        minute_ago = now - 60

        with self.lock:
            self.requests[ip] = [req_time for req_time in self.requests[ip] 
                               if req_time > minute_ago]
            
            if len(self.requests[ip]) >= self.requests_per_minute:
                return False
            
            self.requests[ip].append(now)
            return True

def rate_limit(limiter: RateLimiter):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not limiter.is_allowed(request.remote_addr):
                return Response('Rate limit exceeded', status=429)
            return f(*args, **kwargs)
        return decorated_function
    return decorator 