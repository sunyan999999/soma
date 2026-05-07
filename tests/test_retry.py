"""LLM 重试机制测试"""
import time
import pytest
from unittest.mock import patch, MagicMock

from soma.retry import llm_retry, _is_retryable


class TestRetryableDetection:
    """可重试/不可重试异常判定"""

    def test_network_timeout_is_retryable(self):
        assert _is_retryable(TimeoutError("connection timed out"))

    def test_connection_error_is_retryable(self):
        assert _is_retryable(ConnectionError("Connection refused"))

    def test_503_service_unavailable_is_retryable(self):
        assert _is_retryable(RuntimeError("503 Service Unavailable"))

    def test_500_internal_error_is_retryable(self):
        assert _is_retryable(Exception("500 Internal Server Error"))

    def test_auth_error_not_retryable(self):
        assert not _is_retryable(Exception("AuthenticationError: invalid api key"))
        assert not _is_retryable(Exception("incorrect api key"))

    def test_400_bad_request_not_retryable(self):
        assert not _is_retryable(Exception("BadRequestError: invalid parameter"))

    def test_401_unauthorized_not_retryable(self):
        assert not _is_retryable(Exception("401 Unauthorized"))

    def test_403_forbidden_not_retryable(self):
        assert not _is_retryable(Exception("403 Forbidden"))

    def test_quota_exceeded_not_retryable(self):
        assert not _is_retryable(Exception("insufficient_quota"))

    def test_content_filter_not_retryable(self):
        assert not _is_retryable(Exception("content_filter triggered"))


class TestLLMRetryDecorator:
    """@llm_retry 装饰器行为"""

    def test_success_first_attempt_no_retry(self):
        call_count = [0]

        @llm_retry
        def succeed():
            call_count[0] += 1
            return "ok"

        result = succeed()
        assert result == "ok"
        assert call_count[0] == 1

    def test_retry_on_transient_error_then_succeed(self):
        call_count = [0]

        @llm_retry
        def flaky():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ConnectionError("temporary network error")
            return "recovered"

        result = flaky()
        assert result == "recovered"
        assert call_count[0] == 2

    def test_retry_max_times_then_raise(self):
        call_count = [0]

        @llm_retry
        def always_fails():
            call_count[0] += 1
            raise ConnectionError("persistent network error")

        with pytest.raises(ConnectionError):
            always_fails()
        assert call_count[0] == 3  # 1 original + 2 retries

    def test_auth_error_does_not_retry(self):
        call_count = [0]

        @llm_retry
        def auth_fail():
            call_count[0] += 1
            raise Exception("AuthenticationError: incorrect api key")

        with pytest.raises(Exception):
            auth_fail()
        assert call_count[0] == 1  # 不重试

    def test_custom_retry_params(self):
        call_count = [0]

        @llm_retry(max_attempts=5, min_wait=1, max_wait=60)
        def flaky_many():
            call_count[0] += 1
            if call_count[0] < 4:
                raise ConnectionError("flake")
            return "ok"

        result = flaky_many()
        assert result == "ok"
        assert call_count[0] == 4

    def test_retry_without_parentheses(self):
        """@llm_retry 无括号用法"""
        call_count = [0]

        @llm_retry
        def flaky():
            call_count[0] += 1
            if call_count[0] < 2:
                raise TimeoutError("slow")
            return "done"

        result = flaky()
        assert result == "done"
        assert call_count[0] == 2
