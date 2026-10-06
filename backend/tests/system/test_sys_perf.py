"""TC-PRF — hiệu năng các điểm cuối REST không phụ thuộc LLM (mục 5.4.6 báo cáo)."""
from __future__ import annotations

import statistics
import time

import pytest

pytestmark = pytest.mark.system


def _timed_requests(fn, n=10):
    samples = []
    for _ in range(n):
        start = time.perf_counter()
        r = fn()
        samples.append(time.perf_counter() - start)
        assert r.status_code == 200
    return samples


class TestPerf:
    def test_tc_prf_01_health_median_under_50ms(self, live):
        samples = _timed_requests(live.health)
        med = statistics.median(samples) * 1000
        assert med < 50, f"median={med:.1f}ms"

    def test_tc_prf_02_products_list_median_under_100ms(self, live):
        samples = _timed_requests(lambda: live.products(limit=20))
        med = statistics.median(samples) * 1000
        assert med < 100, f"median={med:.1f}ms"
        body = live.products(limit=20).json()
        assert body["total"] == 53
        assert len(body["items"]) == 20

    def test_tc_prf_03_param_validation_no_llm(self, live):
        """Tham số sai bị chặn ở tầng REST (422/404), không tốn lượt gọi LLM."""
        assert live.products(category="sách").status_code == 422
        assert live.products(min_price=10_000_000, max_price=1000).status_code == 422
        assert live.product("NOPE").status_code == 404
