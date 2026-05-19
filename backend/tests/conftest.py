import pytest
import pandas as pd
from datetime import datetime, date, timedelta
import fund_estimation as fe


@pytest.fixture(autouse=True)
def clear_caches():
    """Reset all module-level caches before each test."""
    fe._HOLDINGS_CACHE.clear()
    fe._HOT_FUNDS_CACHE = None
    fe._HOT_FUNDS_CACHE_DATE = None
    fe._FUND_LIST_CACHE = None
    fe._IP_REQUEST_COUNT.clear()
    yield


@pytest.fixture
def make_holdings_df():
    """Factory to create fake AkShare holdings DataFrames."""
    def _make(quarter="2024年第3季度", rows=None):
        if rows is None:
            rows = [
                (1, "600519", "贵州茅台", "9.50%", quarter),
                (2, "000858", "五粮液", "8.20%", quarter),
                (3, "601318", "中国平安", "7.10%", quarter),
            ]
        return pd.DataFrame(rows, columns=["序号", "股票代码", "股票名称", "占净值比例", "季度"])
    return _make


def build_sina_text(entries):
    """Build fake Sina Finance response text.

    Args:
        entries: List of (exchange_prefix, code_6d, prev_close, current)
                 e.g. [("sh", "600519", 1848.00, 1900.50), ...]
    """
    lines = []
    for prefix, code, prev, cur in entries:
        # Sina response format: var hq_str_{prefix}{code}="name,code,prev,current,..."
        fields = f"股票名称,{code},{prev},{cur},0,0,0,0,0,0" + ",0" * 20
        lines.append(f'var hq_str_{prefix}{code}="{fields}"')
    return "\n".join(lines)
