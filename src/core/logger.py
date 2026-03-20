from pathlib import Path
import sys
from loguru import logger
from contextvars import ContextVar
from src.core.config import settings 


current_request_id: ContextVar[str | None] = ContextVar("current_request_id", default=None)

logs_path = Path("app_logs")
logs_path .mkdir(exist_ok=True)

log_template = (
    "<green>{time:YYYY-MM-DD HH:mm:ss Z}</green> | "
    "<level>{level: <8}</level> | "
    "<yellow>RID:{extra[request_id]}</yellow> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)


def attach_request_id(record):
    record["extra"]["request_id"] = current_request_id.get()


logger = logger.patch(attach_request_id)

logger.remove()

logger.add(
    sys.stdout,
    format=log_template ,
    level=settings .LOG_LEVEL,
    colorize=True,
)

logger.add(
    logs_path  / "service.log",
    format=log_template ,
    level="INFO",
    rotation="15 MB",
    retention="7 days",
    encoding="utf-8",
    serialize=True,
)
