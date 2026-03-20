import time
import uuid
from fastapi import Request, Response
from typing import Callable
from src.core.logger import logger, current_request_id
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from src.core.config import settings 


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_uuid  = str(uuid.uuid4())
        token = current_request_id.set(request_uuid )
        start = time.time()

        logger.info(
            f"[REQUEST]: {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )

        try:
            response = await call_next(request)
            duration = time.time() - start

            logger.info(
                f"[RESPONSE] Status {response.status_code} for {request.method} "
                f"{request.url.path} processed in {duration:.2f}s"
            )

            return response

        except Exception as exc:
            duration = time.time() - start
            logger.exception(
                f"[ERROR] Exception during {request.method} {request.url.path} "
                f"after  {duration:.2f}s"
            )
            raise
        finally:
            current_request_id.reset(token)


def init_cors(app):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_CREDENTIALS,
        allow_methods=settings.CORS_METHODS,
        allow_headers=settings.CORS_HEADERS,
    )
    logger.info("CORS middleware успешно настроен")
