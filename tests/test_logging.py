"""Redaction must not break uvicorn's structured access formatter."""
import logging

from uvicorn.logging import AccessFormatter

from backend.core.logging import RedactingFilter, redact


def _access_record(path: str, status: int = 200) -> logging.LogRecord:
    return logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:12345", "GET", path, "1.1", status),
        None,
    )


def test_uvicorn_access_args_are_preserved_for_formatter():
    record = _access_record("/api/v1/demo/chat?token=AIzaNotARealKey")
    RedactingFilter().filter(record)

    assert isinstance(record.args, tuple)
    assert len(record.args) == 5
    assert record.args[0] == "127.0.0.1:12345"
    assert record.args[3] == "1.1"
    assert record.args[4] == 200
    assert "AIzaNotARealKey" not in record.args[2]
    assert "[query redacted]" in record.args[2]

    output = AccessFormatter(
        fmt='%(client_addr)s - "%(request_line)s" %(status_code)s'
    ).format(record)
    assert "127.0.0.1:12345" in output
    assert "200 OK" in output
    assert "AIzaNotARealKey" not in output


def test_standard_records_are_redacted_without_args():
    record = logging.LogRecord(
        "backend.test", logging.ERROR, __file__, 1,
        "request failed with key AIzaNotARealKey", (), None,
    )
    RedactingFilter().filter(record)

    assert record.args == ()
    assert record.exc_info is None
    assert "AIzaNotARealKey" not in record.getMessage()


def test_redact_removes_bearer_tokens_and_urls():
    message = "Authorization Bearer abc.def https://example.test/path?key=value"
    cleaned = redact(message)
    assert "abc.def" not in cleaned
    assert "example.test" not in cleaned
