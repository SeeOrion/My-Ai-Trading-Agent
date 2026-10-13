"""Separate confirmed sleep, suspected pauses and genuine permission failures."""

from ai_trading_agent.domain.enums.market import Market


def simulation_failure_message(
    error: str, market: Market, *, resume_delay: float = 0, confirmed_sleep: bool = False
) -> tuple[str, tuple[str, ...]]:
    network_failure = any(
        marker in error.lower()
        for marker in (
            "name or service not known",
            "nodename nor servname",
            "temporary failure in name resolution",
            "network is unreachable",
            "handshake operation timed out",
        )
    )
    if market is Market.A_SHARE and network_failure and (confirmed_sleep or resume_delay >= 60):
        message = "电脑休眠中，A股权限获取失败"
        if not confirmed_sleep:
            message = "疑似" + message
        return message, (
            "这是休眠或运行暂停后的网络访问问题提示，不表示同花顺或 Tushare 授权已失效。",
            f"检测到定时唤醒延迟 {resume_delay:.0f} 秒；容器无法独立确认宿主机睡眠原因。"
            if not confirmed_sleep
            else "已通过宿主机休眠/唤醒记录核对。",
            "原始错误：" + error,
        )
    return error, ()
