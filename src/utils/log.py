from __future__ import annotations
import json, logging, sys, time
from typing import Any, Dict
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        payload: Dict[str, Any] = {"ts": int(time.time()*1e3),"level": record.levelname,"name": record.name,"msg": record.getMessage()}
        if record.exc_info: payload["exc_info"]=self.formatException(record.exc_info)
        if hasattr(record, "extra"): payload.update(getattr(record, "extra"))
        return json.dumps(payload, separators=(",", ":"))

def get_logger(name: str, level: int = logging.INFO, path: str | None = None) -> logging.Logger:
    logger = logging.getLogger(name); logger.setLevel(level)
    handler = logging.FileHandler(path) if path else logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    if not logger.handlers: logger.addHandler(handler)
    logger.propagate=False
    return logger
