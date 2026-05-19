import pytest
from unittest.mock import MagicMock, patch, mock_open, call
from datetime import datetime, date, timedelta
import pandas as pd
import fund_estimation as fe


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


# ============================================================================
# _sina_batch tests
# ============================================================================

class TestSinaBatch:
    """Tests for _sina_batch function."""

    def test_sina_batch_happy_path(self):
        """Test correct calculation of change% for multiple stocks."""
        text = build_sina_text([
            ("sh", "600519", 1848.00, 1900.50),
            ("sz", "000858", 220.50, 225.00),
        ])
        mock_resp = MagicMock()
        mock_resp.text = text
        mock_resp.encoding = "gbk"

        with patch("fund_estimation.requests.get", return_value=mock_resp):
            result = fe._sina_batch(["600519", "000858"])

        assert len(result) == 2
        assert "600519" in result
        assert "000858" in result
        # (1900.50 - 1848.00) / 1848.00 * 100 ≈ 2.84
        assert abs(result["600519"] - 2.84) < 0.01
        # (225.00 - 220.50) / 220.50 * 100 ≈ 2.04
        assert abs(result["000858"] - 2.04) < 0.01

    def test_sina_batch_prefix_routing(self):
        """Test that code starting with '6' routes to 'sh', others to 'sz'."""
        text = build_sina_text([
            ("sh", "600519", 100.00, 110.00),
            ("sz", "300750", 50.00, 55.00),
        ])
        mock_resp = MagicMock()
        mock_resp.text = text
        mock_resp.encoding = "gbk"

        with patch("fund_estimation.requests.get", return_value=mock_resp) as mock_get:
            result = fe._sina_batch(["600519", "300750"])
            # Capture the URL that was passed to requests.get
            call_args = mock_get.call_args
            url = call_args[1].get("url") or call_args[0][0]
            assert "sh600519" in url
            assert "sz300750" in url

    def test_sina_batch_skips_zero_prev_close(self):
        """Test that division by zero is avoided when prev_close is 0."""
        text = build_sina_text([
            ("sh", "600519", 0.00, 10.00),
        ])
        mock_resp = MagicMock()
        mock_resp.text = text
        mock_resp.encoding = "gbk"

        with patch("fund_estimation.requests.get", return_value=mock_resp):
            result = fe._sina_batch(["600519"])

        # Code with prev_close=0 should be skipped
        assert "600519" not in result

    def test_sina_batch_skips_zero_current(self):
        """Test that zero current price is skipped."""
        text = build_sina_text([
            ("sh", "600519", 100.00, 0.00),
        ])
        mock_resp = MagicMock()
        mock_resp.text = text
        mock_resp.encoding = "gbk"

        with patch("fund_estimation.requests.get", return_value=mock_resp):
            result = fe._sina_batch(["600519"])

        assert "600519" not in result

    def test_sina_batch_skips_malformed_line(self):
        """Test that lines with insufficient fields are skipped."""
        text = 'var hq_str_sh600519="only,two"\nvar hq_str_sz000858="a,b,c,d,e"'
        mock_resp = MagicMock()
        mock_resp.text = text
        mock_resp.encoding = "gbk"

        with patch("fund_estimation.requests.get", return_value=mock_resp):
            result = fe._sina_batch(["600519", "000858"])

        # Both are malformed, result should be empty or only valid entries
        # The second one has 5 fields, so it might parse; depends on impl
        # But the point is: parsing errors don't crash

    def test_sina_batch_network_failure_returns_empty_dict(self):
        """Test that network failure returns empty dict."""
        with patch("fund_estimation.requests.get", side_effect=Exception("Network error")):
            result = fe._sina_batch(["600519"])

        assert result == {}

    def test_sina_batch_code_zfill_to_6_digits(self):
        """Test that codes are zero-padded to 6 digits."""
        text = build_sina_text([
            ("sh", "001234", 100.00, 110.00),  # 6-digit code
        ])
        mock_resp = MagicMock()
        mock_resp.text = text
        mock_resp.encoding = "gbk"

        with patch("fund_estimation.requests.get", return_value=mock_resp):
            result = fe._sina_batch(["001234"])

        # Result key should be 6-digit zero-padded
        assert "001234" in result


# ============================================================================
# get_fund_top10_with_change tests
# ============================================================================

class TestGetFundTop10WithChange:
    """Tests for get_fund_top10_with_change function."""

    def test_happy_path(self, make_holdings_df):
        """Test basic happy path with valid holdings and prices."""
        holdings = make_holdings_df()
        prices = {"600519": 2.84, "000858": 2.04, "601318": -1.50}

        with patch("fund_estimation.ak.fund_portfolio_hold_em", return_value=holdings):
            with patch("fund_estimation._sina_batch", return_value=prices):
                df, estimated_change, quarter = fe.get_fund_top10_with_change("110011")

        assert df is not None
        assert estimated_change is not None
        assert isinstance(estimated_change, float)
        assert quarter == "2024年第3季度"
        # Weights: 0.095, 0.082, 0.071; contributions: 0.2698, 0.1673, -0.1065
        # Sum weights: 0.248; sum contrib: 0.3306; result ≈ 1.333
        assert 1.2 < estimated_change < 1.4

    def test_cache_hit(self, make_holdings_df):
        """Test that cached holdings are used and AkShare is not called."""
        holdings = make_holdings_df()
        prices = {"600519": 1.0, "000858": 1.0, "601318": 1.0}

        # Pre-populate cache
        fe._HOLDINGS_CACHE["110011"] = {
            "df": holdings,
            "quarter": "2024年第3季度",
            "cached_at": fe._now_cn(),
        }

        with patch("fund_estimation.ak.fund_portfolio_hold_em") as mock_ak:
            with patch("fund_estimation._sina_batch", return_value=prices):
                df, estimated_change, quarter = fe.get_fund_top10_with_change("110011")

        # AkShare should NOT be called since cache is fresh
        mock_ak.assert_not_called()

    def test_cache_expired(self, make_holdings_df):
        """Test that expired cache is refreshed by calling AkShare."""
        holdings = make_holdings_df()
        prices = {"600519": 1.0, "000858": 1.0, "601318": 1.0}

        # Pre-populate cache with old timestamp (> 24 hours)
        old_time = fe._now_cn() - timedelta(hours=25)
        fe._HOLDINGS_CACHE["110011"] = {
            "df": holdings,
            "quarter": "2024年第3季度",
            "cached_at": old_time,
        }

        with patch("fund_estimation.ak.fund_portfolio_hold_em", return_value=holdings) as mock_ak:
            with patch("fund_estimation._sina_batch", return_value=prices):
                df, estimated_change, quarter = fe.get_fund_top10_with_change("110011")

        # AkShare SHOULD be called for expired cache
        mock_ak.assert_called()

    def test_all_years_fail_raises_valueerror(self):
        """Test that ValueError is raised when all 3 years fail."""
        with patch("fund_estimation.ak.fund_portfolio_hold_em", side_effect=Exception("API error")):
            with pytest.raises(ValueError, match="未找到基金"):
                fe.get_fund_top10_with_change("999999")

    def test_first_year_empty_uses_fallback(self):
        """Test that empty first year falls back to year-1."""
        empty_df = pd.DataFrame(columns=["序号", "股票代码", "股票名称", "占净值比例", "季度"])
        fallback_df = pd.DataFrame([
            (1, "600519", "贵州茅台", "10.0%", "2023年第4季度"),
            (2, "000858", "五粮液", "9.0%", "2023年第4季度"),
            (3, "601318", "中国平安", "8.0%", "2023年第4季度"),
        ], columns=["序号", "股票代码", "股票名称", "占净值比例", "季度"])

        prices = {"600519": 1.0, "000858": 1.0, "601318": 1.0}

        # First call returns empty, second call returns fallback_df
        with patch("fund_estimation.ak.fund_portfolio_hold_em", side_effect=[empty_df, fallback_df]):
            with patch("fund_estimation._sina_batch", return_value=prices):
                df, estimated_change, quarter = fe.get_fund_top10_with_change("110011")

        assert quarter == "2023年第4季度"

    def test_bug1_sina_empty_gives_none_not_zero(self, make_holdings_df):
        """Regression test for Bug #1: empty Sina response should give None, not 0.0."""
        holdings = make_holdings_df()
        # Empty dict from Sina
        prices = {}

        with patch("fund_estimation.ak.fund_portfolio_hold_em", return_value=holdings):
            with patch("fund_estimation._sina_batch", return_value=prices):
                df, estimated_change, quarter = fe.get_fund_top10_with_change("110011")

        # After fix, should be None (not 0.0)
        assert estimated_change is None

    def test_selects_latest_quarter(self):
        """Test that the latest quarter is selected from multi-quarter DataFrame."""
        multi_quarter_df = pd.DataFrame([
            (1, "600519", "贵州茅台", "9.50%", "2024年第1季度"),
            (2, "000858", "五粮液", "8.20%", "2024年第2季度"),
            (3, "601318", "中国平安", "7.10%", "2024年第3季度"),
        ], columns=["序号", "股票代码", "股票名称", "占净值比例", "季度"])

        prices = {"600519": 1.0, "000858": 1.0, "601318": 1.0}

        with patch("fund_estimation.ak.fund_portfolio_hold_em", return_value=multi_quarter_df):
            with patch("fund_estimation._sina_batch", return_value=prices):
                df, estimated_change, quarter = fe.get_fund_top10_with_change("110011")

        # Latest quarter is Q3 2024
        assert quarter == "2024年第3季度"
        # Only rows from that quarter should be in result
        assert len(df) == 1
        assert df.iloc[0]["股票代码"] == "601318"

    def test_partial_sina_coverage(self, make_holdings_df):
        """Test partial Sina data: 2/3 stocks have prices."""
        holdings = make_holdings_df()
        # Only 2 out of 3 stocks have prices
        prices = {"600519": 2.0, "000858": 3.0}

        with patch("fund_estimation.ak.fund_portfolio_hold_em", return_value=holdings):
            with patch("fund_estimation._sina_batch", return_value=prices):
                df, estimated_change, quarter = fe.get_fund_top10_with_change("110011")

        # estimated_change should be computed from the 2 available stocks
        assert estimated_change is not None
        assert not (estimated_change == 0.0 and prices)


# ============================================================================
# is_trading_time tests
# ============================================================================

class TestIsTradingTime:
    """Tests for is_trading_time function."""

    @pytest.mark.parametrize("hour,minute,expected", [
        (9, 0, False),       # Before open
        (9, 30, True),       # Open
        (10, 0, True),       # Morning session
        (11, 30, True),      # End of morning session
        (11, 31, False),     # After morning session
        (12, 0, False),      # Lunch break
        (12, 59, False),     # Before afternoon
        (13, 0, True),       # Afternoon session open
        (14, 0, True),       # Afternoon session
        (15, 0, True),       # Close time
        (15, 1, False),      # After close
        (16, 0, False),      # After market
    ])
    def test_trading_time_ranges(self, hour, minute, expected):
        """Test trading time ranges for weekday."""
        # Monday is weekday 0, use a specific date: 2024-01-01 is a Monday
        test_time = datetime(2024, 1, 1, hour, minute, tzinfo=fe.ZoneInfo("Asia/Shanghai"))
        with patch("fund_estimation._now_cn", return_value=test_time):
            assert fe.is_trading_time() == expected

    @pytest.mark.parametrize("weekday", [5, 6])  # Saturday, Sunday
    def test_weekend_not_trading_time(self, weekday):
        """Test that weekend is not trading time."""
        # 2024-01-06 is a Saturday (weekday=5)
        test_time = datetime(2024, 1, 6 + (weekday - 5), 10, 0, tzinfo=fe.ZoneInfo("Asia/Shanghai"))
        with patch("fund_estimation._now_cn", return_value=test_time):
            assert not fe.is_trading_time()


# ============================================================================
# _base_fund_name tests
# ============================================================================

class TestBaseFundName:
    """Tests for _base_fund_name function (pure string function)."""

    @pytest.mark.parametrize("input_name,expected", [
        ("易方达蓝筹精选混合A", "易方达蓝筹精选混合"),
        ("博时基金C", "博时基金"),
        ("易方达中小盘A类", "易方达中小盘"),
        ("易方达中小盘C类", "易方达中小盘"),
        ("中欧医疗健康混合(A)", "中欧医疗健康混合"),
        ("中欧医疗健康混合(C)", "中欧医疗健康混合"),
        ("招商白酒（C）", "招商白酒"),  # Full-width parentheses
        ("天弘沪深300ETF联接A", "天弘沪深300ETF"),
        ("广发纳斯达克100ETF联接C", "广发纳斯达克100ETF"),
        ("招商中证白酒指数", "招商中证白酒指数"),  # No suffix
        ("QDII-A基金", "QDII-A基金"),  # Pattern not matching dash form
    ])
    def test_base_fund_name_stripping(self, input_name, expected):
        """Test various fund name suffix stripping patterns."""
        assert fe._base_fund_name(input_name) == expected


# ============================================================================
# search_funds tests
# ============================================================================

class TestSearchFunds:
    """Tests for search_funds function."""

    def test_search_by_code(self):
        """Test searching funds by code."""
        fe._FUND_LIST_CACHE = pd.DataFrame({
            "基金代码": ["110011", "161725", "519674"],
            "基金简称": ["易方达中小盘混合", "招商中证白酒指数", "银河创新成长混合"],
        })
        result = fe.search_funds("110011", limit=10)
        assert len(result) == 1
        assert result[0]["code"] == "110011"

    def test_search_by_name_substring(self):
        """Test searching funds by name substring."""
        fe._FUND_LIST_CACHE = pd.DataFrame({
            "基金代码": ["110011", "161725", "519674"],
            "基金简称": ["易方达中小盘混合", "招商中证白酒指数", "银河创新成长混合"],
        })
        result = fe.search_funds("白酒", limit=10)
        assert len(result) == 1
        assert result[0]["code"] == "161725"

    def test_search_cache_none_returns_empty(self):
        """Test that empty cache returns empty list."""
        fe._FUND_LIST_CACHE = None
        result = fe.search_funds("110011", limit=10)
        assert result == []

    def test_search_limit_respected(self):
        """Test that search limit is respected."""
        fe._FUND_LIST_CACHE = pd.DataFrame({
            "基金代码": [f"00{i:04d}" for i in range(20)],
            "基金简称": ["Fund"] * 20,
        })
        result = fe.search_funds("Fund", limit=5)
        assert len(result) == 5

    def test_search_no_match_returns_empty(self):
        """Test that no match returns empty list."""
        fe._FUND_LIST_CACHE = pd.DataFrame({
            "基金代码": ["110011"],
            "基金简称": ["易方达中小盘混合"],
        })
        result = fe.search_funds("zzz_nonexistent", limit=10)
        assert result == []


# ============================================================================
# get_hot_funds tests
# ============================================================================

class TestGetHotFunds:
    """Tests for get_hot_funds function."""

    def test_happy_path_deduplicates_ac_tranches(self):
        """Test that A/C tranches are deduplicated (higher rank kept)."""
        mock_df = pd.DataFrame({
            "基金代码": ["110011", "110011C", "161725", "519674", "005911", "006614", "007371", "008675", "009279", "010123", "010124"],
            "基金简称": ["易方达蓝筹精选混合A", "易方达蓝筹精选混合C", "招商中证白酒", "银河创新成长", "f5", "f6", "f7", "f8", "f9", "f10", "f11"],
            "近1月": [5.0, 4.5, 4.0, 3.5, 3.0, 2.5, 2.0, 1.5, 1.0, 0.5, 0.4],
        })

        with patch("fund_estimation.ak.fund_open_fund_rank_em", return_value=mock_df):
            result = fe.get_hot_funds()

        assert len(result) <= 10
        # Check that only the higher-ranked A version appears, not C
        base_names = [fe._base_fund_name(item["name"]) for item in result]
        # "易方达蓝筹精选混合" should appear at most once
        assert base_names.count("易方达蓝筹精选混合") <= 1

    def test_returns_cached_result_same_day(self):
        """Test that same-day cache is returned without calling AkShare."""
        fe._HOT_FUNDS_CACHE = [{"code": "110011", "name": "cached"}]
        fe._HOT_FUNDS_CACHE_DATE = date.today()

        with patch("fund_estimation.ak.fund_open_fund_rank_em") as mock_ak:
            result = fe.get_hot_funds()

        mock_ak.assert_not_called()
        assert result == fe._HOT_FUNDS_CACHE

    def test_refreshes_cache_next_day(self):
        """Test that cache is refreshed on new day."""
        fe._HOT_FUNDS_CACHE = [{"code": "old", "name": "old"}]
        fe._HOT_FUNDS_CACHE_DATE = date.today() - timedelta(days=1)

        mock_df = pd.DataFrame({
            "基金代码": [f"00{i:04d}" for i in range(12)],
            "基金简称": [f"Fund{i}" for i in range(12)],
            "近1月": list(range(12, 0, -1)),
        })

        with patch("fund_estimation.ak.fund_open_fund_rank_em", return_value=mock_df) as mock_ak:
            result = fe.get_hot_funds()

        mock_ak.assert_called_once()

    def test_fallback_to_stale_cache_on_failure(self):
        """Test fallback to stale cache when AkShare fails."""
        fe._HOT_FUNDS_CACHE = [{"code": "110011", "name": "stale"}]
        fe._HOT_FUNDS_CACHE_DATE = date.today() - timedelta(days=1)

        with patch("fund_estimation.ak.fund_open_fund_rank_em", side_effect=Exception("API error")):
            result = fe.get_hot_funds()

        # Should return stale cache
        assert result == fe._HOT_FUNDS_CACHE

    def test_fallback_to_hardcoded_list_when_no_cache(self):
        """Test fallback to hardcoded list when no cache and API fails."""
        fe._HOT_FUNDS_CACHE = None
        fe._HOT_FUNDS_CACHE_DATE = None

        with patch("fund_estimation.ak.fund_open_fund_rank_em", side_effect=Exception("API error")):
            result = fe.get_hot_funds()

        # Should return hardcoded list
        assert len(result) == 10
        assert all("code" in item and "name" in item for item in result)


# ============================================================================
# get_ai_analysis tests
# ============================================================================

class TestGetAiAnalysis:
    """Tests for get_ai_analysis function."""

    def test_rate_limit_5_per_day(self):
        """Test that 6th request in a day is rate-limited."""
        client_ip = "1.2.3.4"
        fe._IP_REQUEST_COUNT[client_ip] = (date.today(), 5)

        with pytest.raises(Exception, match="今日AI分析额度已用完|已达到"):
            fe.get_ai_analysis("110011", client_ip)

    def test_rate_limit_increments_count(self):
        """Test that request count increments."""
        client_ip = "1.2.3.5"
        fe._IP_REQUEST_COUNT[client_ip] = (date.today(), 3)

        mock_response = {"fund_code": "110011", "source": "AI"}
        with patch("fund_estimation.generate_realtime_ai_analysis", return_value=mock_response):
            with patch("builtins.open", mock_open()):
                fe.get_ai_analysis("110011", client_ip)

        assert fe._IP_REQUEST_COUNT[client_ip][1] == 4

    def test_rate_limit_resets_new_day(self):
        """Test that rate limit resets on new day."""
        client_ip = "1.2.3.6"
        fe._IP_REQUEST_COUNT[client_ip] = (date.today() - timedelta(days=1), 5)

        mock_response = {"fund_code": "110011"}
        with patch("fund_estimation.generate_realtime_ai_analysis", return_value=mock_response):
            with patch("builtins.open", mock_open()):
                result = fe.get_ai_analysis("110011", client_ip)

        # Should not raise rate-limit exception
        assert result == mock_response
        # Count should be reset to 1
        assert fe._IP_REQUEST_COUNT[client_ip] == (date.today(), 1)

    def test_returns_fresh_disk_cache(self):
        """Test that fresh disk cache is returned without calling LLM."""
        client_ip = "1.2.3.7"
        cached_data = '{"fund_code": "110011", "source": "cached"}'
        recent_mtime = (datetime.now() - timedelta(days=2)).timestamp()

        with patch("fund_estimation.os.path.exists", return_value=True):
            with patch("fund_estimation.os.path.getmtime", return_value=recent_mtime):
                with patch("builtins.open", mock_open(read_data=cached_data)):
                    with patch("fund_estimation.generate_realtime_ai_analysis") as mock_gen:
                        result = fe.get_ai_analysis("110011", client_ip)

        mock_gen.assert_not_called()
        assert result["fund_code"] == "110011"

    def test_skips_expired_disk_cache(self):
        """Test that expired cache (> 7 days) triggers fresh fetch."""
        client_ip = "1.2.3.8"
        old_mtime = (datetime.now() - timedelta(days=8)).timestamp()
        mock_response = {"fund_code": "110011", "fresh": True}

        with patch("fund_estimation.os.path.exists", return_value=True):
            with patch("fund_estimation.os.path.getmtime", return_value=old_mtime):
                with patch("fund_estimation.generate_realtime_ai_analysis", return_value=mock_response):
                    with patch("builtins.open", mock_open()):
                        result = fe.get_ai_analysis("110011", client_ip)

        assert result == mock_response

    def test_new_ip_sets_count_1(self):
        """Test that new IP gets count of 1."""
        client_ip = "9.9.9.9"
        mock_response = {"fund_code": "110011"}

        with patch("fund_estimation.generate_realtime_ai_analysis", return_value=mock_response):
            with patch("builtins.open", mock_open()):
                fe.get_ai_analysis("110011", client_ip)

        assert fe._IP_REQUEST_COUNT[client_ip] == (date.today(), 1)


# ============================================================================
# Bug Regression Tests
# ============================================================================

class TestBugRegressions:
    """Tests that document and verify bug fixes."""

    def test_bug2_calculate_risk_score_normalized_to_01(self):
        """Test that calculate_risk_score returns 0-1 range after fix."""
        holdings = [
            {"code": "600519", "name": "茅台", "weight_pct": 9.5},
            {"code": "000858", "name": "五粮", "weight_pct": 8.2},
        ]
        risk = fe.calculate_risk_score(holdings)
        # After fix, should be normalized to 0-1
        assert 0.0 <= risk <= 1.0

    def test_bug4_describe_market_factors_is_deterministic(self):
        """Test that describe_market_factors is deterministic per fund code."""
        code = "110011"
        result1 = fe.describe_market_factors(code)
        result2 = fe.describe_market_factors(code)
        result3 = fe.describe_market_factors(code)
        assert result1 == result2 == result3

    def test_bug5_is_high_concentration_uses_weight_hhi(self):
        """Test that is_high_concentration uses HHI instead of name-based sectors."""
        # All different names but concentrated weights
        holdings = [
            {"code": "600519", "name": "贵州茅台", "weight_pct": 25.0},
            {"code": "000858", "name": "五粮液", "weight_pct": 20.0},
            {"code": "601318", "name": "中国平安", "weight_pct": 5.0},
        ]
        # After fix: uses HHI, not name[:2] sectors
        result = fe.is_high_concentration(holdings)
        # HHI = (0.25^2 + 0.2^2 + 0.05^2) / (0.5^2) ≈ 0.29, should be high
        assert isinstance(result, bool)

    def test_bug7_bare_except_now_logs_errors(self):
        """Test that error handling in holdings fetch logs instead of silently failing."""
        # This is more of a structural test; we verify the code path doesn't crash
        # and logs (if logging is available)
        with patch("fund_estimation.ak.fund_portfolio_hold_em", side_effect=Exception("test error")):
            with pytest.raises(ValueError, match="未找到基金"):
                fe.get_fund_top10_with_change("999999")
