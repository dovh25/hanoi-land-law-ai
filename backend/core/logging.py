"""Never emit credentials, credential-bearing URLs, or provider exception bodies."""
import logging
import re


def redact(message: str) -> str:
    if re.search(r"authorization|api[_-]?key|jwt_secret|password", message, re.I):
        return "[sensitive log message redacted]"
    message = re.sub(r"https?://\S+", "[URL redacted]", message)
    message = re.sub(r"([^\s?]+\?)[^\s\"']+", r"\1[query redacted]", message)
    message = re.sub(r"Bearer\s+\S+", "Bearer [redacted]", message, flags=re.I)
    return re.sub(r"AIza[\w-]+", "[key redacted]", message)


class RedactingFilter(logging.Filter):
    def filter(self, record):
        # Uvicorn's access formatter unpacks record.args itself, so clearing them would
        # raise "not enough values to unpack". Redact each argument in place instead.
        if record.name == "uvicorn.access" and record.args:
            record.msg = redact(str(record.msg))
            record.args = tuple(
                redact(argument) if isinstance(argument, str) else argument
                for argument in record.args
            )
            return True
        record.msg = redact(record.getMessage())
        record.args = ()
        # Exception strings may contain remote request bodies or query-string keys.
        record.exc_info = None
        record.exc_text = None
        return True


def setup_logging(level="INFO"):
    if not getattr(logging.getLogRecordFactory(), "_redacts_credentials", False):
        original_factory = logging.getLogRecordFactory()

        def factory(*args, **kwargs):
            record = original_factory(*args, **kwargs)
            RedactingFilter().filter(record)
            return record

        factory._redacts_credentials = True
        logging.setLogRecordFactory(factory)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger().setLevel(level)
    for handler in logging.getLogger().handlers:
        handler.addFilter(RedactingFilter())
    for name in ("httpx", "httpcore", "google", "urllib3", "langsmith"):
        logging.getLogger(name).setLevel(logging.WARNING)
