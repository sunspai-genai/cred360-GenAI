# api/middleware/request_logging.py
import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__) # Use logger from this module

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.time()
        # Log basic request info before processing
        log_str = f"Request: {request.method} {request.url.path}"
        if request.query_params:
            log_str += f"?{request.query_params}"
        client_host = request.client.host if request.client else "unknown"
        client_port = request.client.port if request.client else "unknown"
        log_str += f" | Client: {client_host}:{client_port}"
        logger.info(f"START {log_str}")

        try:
            response = await call_next(request)
            process_time = (time.time() - start_time) * 1000  # milliseconds
            logger.info(f"END   {log_str} | Status: {response.status_code} | Duration: {process_time:.2f}ms")
            response.headers["X-Process-Time"] = str(process_time / 1000) # Add header in seconds
            return response
        except Exception as e:
            process_time = (time.time() - start_time) * 1000
            logger.exception(f"FAIL  {log_str} | Duration: {process_time:.2f}ms | Error: {e}")
            # Re-raise the exception so FastAPI's error handling can take over
            raise e