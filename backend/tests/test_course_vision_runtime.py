from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from services.course_vision_runtime import recover, error_code


class ProviderError(Exception):
    def __init__(self,status,code,headers=None):
        self.status_code=status;self.code=code;self.response=SimpleNamespace(headers=headers or {})


@pytest.mark.asyncio
async def test_respects_retry_after_for_temporary_rate_limit_and_succeeds():
    operation=AsyncMock(side_effect=[ProviderError(429,'rate_limit_exceeded',{'retry-after':'42'}),'read'])
    sleep=AsyncMock();gate=AsyncMock()
    assert await recover(operation,sleep=sleep,gate=gate)=='read'
    sleep.assert_awaited_once_with(42)
    assert gate.await_count==2


@pytest.mark.asyncio
@pytest.mark.parametrize('code',['insufficient_quota','credit_balance_exhausted','billing_hard_limit_reached'])
async def test_no_blind_retry_when_billing_is_exhausted(code):
    operation=AsyncMock(side_effect=ProviderError(429,code));sleep=AsyncMock()
    with pytest.raises(ProviderError):await recover(operation,sleep=sleep,gate=AsyncMock())
    assert operation.await_count==1 and error_code(operation.side_effect)=='quota_exhausted'
    sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_limits_retry_count_and_never_retries_before_large_upstream_delay():
    operation=AsyncMock(side_effect=ProviderError(429,'rate_limit_exceeded',{'retry-after':'200'}));sleep=AsyncMock()
    with pytest.raises(ProviderError):await recover(operation,sleep=sleep,gate=AsyncMock())
    assert operation.await_count==1
    sleep.assert_not_awaited()
    operation=AsyncMock(side_effect=ProviderError(429,'rate_limit_exceeded',{'retry-after':'1'}));sleep=AsyncMock()
    with pytest.raises(ProviderError):await recover(operation,sleep=sleep,gate=AsyncMock())
    assert operation.await_count==4 and sleep.await_count==3


@pytest.mark.asyncio
async def test_pacing_reserves_separate_slots_for_requests(monkeypatch):
    import services.course_vision_runtime as runtime
    monkeypatch.setenv('OPENAI_COURSE_VISION_MIN_INTERVAL','20')
    monkeypatch.setattr(runtime,'_next_request',0)
    monkeypatch.setattr(runtime.time,'monotonic',lambda:100)
    sleep=AsyncMock()
    await runtime.pace(sleep);await runtime.pace(sleep);await runtime.pace(sleep)
    assert [call.args[0] for call in sleep.await_args_list]==[20,40]
