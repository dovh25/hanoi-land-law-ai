from concurrent.futures import ThreadPoolExecutor

from backend.services.lookup_service import LawDocumentService
from backend.services.mvp_corpus import DEFAULT_CORPUS_PATH
from backend.services.rate_limit import SlidingWindowLimiter


def test_limiter_reclaims_expired_visitors():
    limiter = SlidingWindowLimiter(2, 60)
    for number in range(2100):
        assert limiter.check(str(number), now=0).allowed
    assert limiter.check("new", now=61).allowed
    assert len(limiter._events) < 2048


def test_limiter_fails_closed_at_capacity():
    limiter = SlidingWindowLimiter(1, 60)
    for number in range(8192):
        assert limiter.check(str(number), now=0).allowed
    assert not limiter.check("new", now=1).allowed
    assert not limiter.check("0", now=1).allowed
    assert limiter.check("new", now=61).allowed


def test_concurrent_lookup_initialization_does_not_duplicate_documents(tmp_path):
    service = LawDocumentService(str(tmp_path), DEFAULT_CORPUS_PATH)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: service.startup(), range(4)))
    assert service.list_documents()["total"] == 2
