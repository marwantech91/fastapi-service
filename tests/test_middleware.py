import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.middleware import RateLimitMiddleware, RequestTimingMiddleware


class TestRateLimitMiddleware:
    def setup_method(self):
        self.app = MagicMock()
        self.middleware = RateLimitMiddleware(self.app, max_requests=3, window_seconds=60)

    def _make_request(self, path="/api/test", ip="127.0.0.1"):
        request = MagicMock()
        request.url.path = path
        request.client.host = ip
        return request

    @pytest.mark.asyncio
    async def test_allows_requests_under_limit(self):
        request = self._make_request()
        response = MagicMock()
        response.headers = {}
        call_next = AsyncMock(return_value=response)

        result = await self.middleware.dispatch(request, call_next)

        assert call_next.called
        assert result.headers["X-RateLimit-Limit"] == "3"
        assert result.headers["X-RateLimit-Remaining"] == "2"

    @pytest.mark.asyncio
    async def test_blocks_requests_over_limit(self):
        request = self._make_request()
        response = MagicMock()
        response.headers = {}
        call_next = AsyncMock(return_value=response)

        # Use up all tokens
        for _ in range(3):
            await self.middleware.dispatch(request, call_next)

        # Next request should be blocked
        result = await self.middleware.dispatch(request, call_next)
        assert result.status_code == 429

    @pytest.mark.asyncio
    async def test_health_endpoint_bypasses_rate_limit(self):
        request = self._make_request(path="/health")
        response = MagicMock()
        call_next = AsyncMock(return_value=response)

        result = await self.middleware.dispatch(request, call_next)

        assert call_next.called

    @pytest.mark.asyncio
    async def test_tracks_clients_separately(self):
        response = MagicMock()
        response.headers = {}
        call_next = AsyncMock(return_value=response)

        # Exhaust limit for client A
        req_a = self._make_request(ip="10.0.0.1")
        for _ in range(3):
            await self.middleware.dispatch(req_a, call_next)

        # Client B should still be allowed
        req_b = self._make_request(ip="10.0.0.2")
        result = await self.middleware.dispatch(req_b, call_next)
        assert result.headers["X-RateLimit-Remaining"] == "2"


class TestRequestTimingMiddleware:
    def setup_method(self):
        self.app = MagicMock()
        self.middleware = RequestTimingMiddleware(self.app)

    @pytest.mark.asyncio
    async def test_adds_process_time_header(self):
        request = MagicMock()
        response = MagicMock()
        response.headers = {}
        call_next = AsyncMock(return_value=response)

        result = await self.middleware.dispatch(request, call_next)

        assert "X-Process-Time" in result.headers
        elapsed = float(result.headers["X-Process-Time"])
        assert elapsed >= 0
