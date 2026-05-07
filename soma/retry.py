"""LLM 调用重试机制 — tenacity 封装，区分可重试/不可重试异常"""
import logging

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
    before_sleep_log,
)

logger = logging.getLogger(__name__)

# 不可重试的关键词（匹配异常类型名或消息）
_NON_RETRYABLE_PATTERNS = (
    "AuthenticationError",
    "BadRequestError",
    "InvalidRequestError",
    "invalid_request_error",
    "401",
    "403",
    "api key",
    "api_key",
    "incorrect api key",
    "invalid api key",
    "not found",
    "insufficient_quota",
    "rate_limit_exceeded",
    "context_length_exceeded",
    "content_filter",
    "safety",
)


def _is_retryable(exception: BaseException) -> bool:
    """判断异常是否可重试。

    可重试：网络超时、连接错误、5xx服务端错误、临时性故障
    不可重试：认证失败(401)、参数错误(400)、配额耗尽、内容过滤
    """
    exc_str = str(exception).lower()
    exc_type = type(exception).__name__

    # 检查不可重试模式
    for pattern in _NON_RETRYABLE_PATTERNS:
        if pattern.lower() in exc_str or pattern.lower() in exc_type.lower():
            return False
    return True


LLM_RETRY_CONFIG = {
    "stop": stop_after_attempt(3),
    "wait": wait_exponential(multiplier=1, min=2, max=30),
    "retry": retry_if_exception(_is_retryable),
    "before_sleep": before_sleep_log(logger, logging.WARNING),
    "reraise": True,
}


def llm_retry(func=None, *, max_attempts: int = 3, min_wait: int = 2, max_wait: int = 30):
    """LLM 调用重试装饰器。

    默认：3次重试，指数退避 2s→4s→8s（上限30s）。
    自动跳过不可重试异常（认证失败、参数错误等）。

    用法:
        @llm_retry
        def my_llm_call():
            return completion(...)
    """
    if func is not None:
        return retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception(_is_retryable),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )(func)

    def decorator(f):
        return retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception(_is_retryable),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )(f)

    return decorator
