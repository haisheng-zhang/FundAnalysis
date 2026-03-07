import akshare as ak
import pandas as pd
import re
import time
import threading
from datetime import date, datetime
from typing import Optional, Tuple, List

# --------------------------------------------------------------------------------
# 全局缓存与锁 (内存存储，不落库)
# --------------------------------------------------------------------------------

# 1. 市场情绪缓存（涨跌家数摘要，极其轻量）
_SENTIMENT_CACHE: Optional[dict] = None
_SENTIMENT_CACHE_TIME: float = 0
_SENTIMENT_LOCK = threading.Lock()

# 2. 全市场行情缓存：应用内内存，后台线程定期用 akshare 刷新
_SPOT_CACHE: Optional[pd.DataFrame] = None
_SPOT_CACHE_TIME: float = 0
SPOT_REFRESH_INTERVAL = 45  # 秒，全市场拉取较重，设为 45s 以平衡实时性与稳定性
_SPOT_CACHE_LOCK = threading.Lock()

# 3. 基金名称列表缓存（启动时全量加载一次）
_FUND_LIST_CACHE: Optional[pd.DataFrame] = None
_FUND_LIST_LOCK = threading.Lock()


# --------------------------------------------------------------------------------
# 辅助函数：交易时间判断与重试机制
# --------------------------------------------------------------------------------

def is_trading_time():
    """判断当前是否在 A 股交易时间内 (周一至周五 9:30-11:30, 13:00-15:00)"""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.time()
    morning = datetime.strptime("09:30", "%H:%M").time() <= t <= datetime.strptime("11:30", "%H:%M").time()
    afternoon = datetime.strptime("13:00", "%H:%M").time() <= t <= datetime.strptime("15:00", "%H:%M").time()
    return morning or afternoon


def get_trading_time_reason():
    """返回非交易时间的友好描述，用于日志输出"""
    now = datetime.now()
    if now.weekday() >= 5:
        return f"今天是{'周六' if now.weekday() == 5 else '周日'}，非交易日"
    elif now.time() < datetime.strptime("09:30", "%H:%M").time():
        return f"当前时间 {now.strftime('%H:%M')}，尚未开盘（09:30开盘）"
    elif datetime.strptime("11:30", "%H:%M").time() < now.time() < datetime.strptime("13:00", "%H:%M").time():
        return f"当前时间 {now.strftime('%H:%M')}，午间休市中（13:00复盘）"
    else:
        return f"当前时间 {now.strftime('%H:%M')}，已收盘（15:00收盘）"


def fetch_with_retry(func, retries: int = 3, delay: int = 5):
    """通用 API 请求重试封装，应对不稳定的网络环境"""
    for attempt in range(1, retries + 1):
        try:
            return func()
        except Exception as e:
            if attempt < retries:
                time.sleep(delay)
            else:
                raise RuntimeError(f"请求失败，已重试 {retries} 次，放弃") from e


# --------------------------------------------------------------------------------
# 核心数据抓取与缓存逻辑 (由后台线程调用)
# --------------------------------------------------------------------------------

def refresh_spot_cache(force: bool = False) -> bool:
    """拉取全市场实时行情并更新内存缓存。"""
    global _SPOT_CACHE, _SPOT_CACHE_TIME
    if not force and not is_trading_time():
        return False
    try:
        # 使用东方财富接口获取全市场 A 股行情，包含代码、名称、最新涨跌幅
        df_all = fetch_with_retry(lambda: ak.stock_zh_a_spot_em()[["代码", "名称", "涨跌幅"]])
        if df_all is not None and not df_all.empty:
            df_all["涨跌幅"] = pd.to_numeric(df_all["涨跌幅"], errors="coerce")
            with _SPOT_CACHE_LOCK:
                _SPOT_CACHE = df_all.copy()
                _SPOT_CACHE_TIME = time.time()
            return True
    except Exception as e:
        print(f"  ❌ [refresh_spot_cache] 失败: {e}")
    return False


def refresh_sentiment_cache(force: bool = False) -> bool:
    """拉取市场情绪摘要（涨跌家数），速度极快。"""
    global _SENTIMENT_CACHE, _SENTIMENT_CACHE_TIME
    
    # 优化：非交易时段且已有缓存时，不再重复请求
    if not force and not is_trading_time() and _SENTIMENT_CACHE is not None:
        return False
        
    try:
        # 使用乐咕接口获取大盘摘要统计
        df = ak.stock_market_activity_legu()
        if df is not None and not df.empty:
            try:
                up = int(df[df["item"] == "上涨"]["value"].iloc[0])
                down = int(df[df["item"] == "下跌"]["value"].iloc[0])
                flat = int(df[df["item"] == "平盘"]["value"].iloc[0])
                
                # 获取接口返回的真实统计日期
                stat_time_val = df[df["item"] == "统计日期"]["value"].iloc[0]
                stat_time = str(stat_time_val) if pd.notna(stat_time_val) else datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                res = {
                    "up": up,
                    "down": down,
                    "flat": flat,
                    "total": up + down + flat,
                    "limit_up": int(df[df["item"] == "涨停"]["value"].iloc[0]),
                    "limit_down": int(df[df["item"] == "跌停"]["value"].iloc[0]),
                    "time": stat_time,
                    "trading": is_trading_time()
                }
                with _SENTIMENT_LOCK:
                    _SENTIMENT_CACHE = res
                    _SENTIMENT_CACHE_TIME = time.time()
                return True
            except Exception as e:
                print(f"  ⚠️ 解析市场情绪数据失败: {e}")
        else:
            print("  ⚠️ 市场情绪数据为空")
    except Exception as e:
        print(f"  ❌ [refresh_sentiment_cache] 联网请求失败: {e}")
    return False


def refresh_fund_list_cache():
    """初始化/刷新全市场基金基本信息（代码 + 名称）"""
    global _FUND_LIST_CACHE
    try:
        df = fetch_with_retry(lambda: ak.fund_name_em())
        if df is not None and not df.empty:
            df = df[["基金代码", "基金简称"]]
            with _FUND_LIST_LOCK:
                _FUND_LIST_CACHE = df
            print(f"  ✅ 基金列表加载完成，共 {len(df)} 只基金")
    except Exception as e:
        print(f"  ❌ [refresh_fund_list_cache] 失败: {e}")


def _spot_background_loop():
    """常驻后台线程：定时刷新行情与情绪缓存。"""
    # 启动预热：尝试拉取初始数据
    for _ in range(3):
        if refresh_sentiment_cache(force=True): break
        time.sleep(5)
    refresh_spot_cache(force=True)

    while True:
        refresh_sentiment_cache()
        
        # 行情缓存过期判断
        with _SPOT_CACHE_LOCK:
            stale = (time.time() - _SPOT_CACHE_TIME) > SPOT_REFRESH_INTERVAL
        
        if stale:
            refresh_spot_cache()
            
        time.sleep(10)


def start_spot_refresh_background():
    """启动后台服务进程。"""
    threading.Thread(target=_spot_background_loop, daemon=True).start()
    threading.Thread(target=refresh_fund_list_cache, daemon=True).start()
    print("  🚀 行情缓存后台刷新服务已启动")


# --------------------------------------------------------------------------------
# 业务查询逻辑 (供 API 调用)
# --------------------------------------------------------------------------------

def search_funds(query: str, limit: int = 10) -> list:
    """模糊搜索基金代码或名称。"""
    global _FUND_LIST_CACHE
    with _FUND_LIST_LOCK:
        df = _FUND_LIST_CACHE
    
    if df is None: return []
    
    query = str(query).strip()
    mask = df["基金代码"].str.contains(query, case=False) | df["基金简称"].str.contains(query, case=False)
    results = df[mask].head(limit)
    
    return [{"code": row["基金代码"], "name": row["基金简称"]} for _, row in results.iterrows()]


def get_market_sentiment() -> dict:
    """获取大盘实时情绪统计。"""
    global _SENTIMENT_CACHE, _SPOT_CACHE
    
    with _SENTIMENT_LOCK:
        fast_cache = _SENTIMENT_CACHE
    if fast_cache: return {"status": "ok", **fast_cache}
    
    # 兜底降级：从全市场行情缓存中即时统计
    with _SPOT_CACHE_LOCK:
        df = _SPOT_CACHE
    
    trading = is_trading_time()
    if df is None:
        return {"status": "loading", "reason": "数据初始化中", "up": 0, "down": 0, "flat": 0, "total": 0, "trading": trading}
    
    df = df[pd.to_numeric(df["涨跌幅"], errors= "coerce").notna()].copy()
    return {
        "status": "ok",
        "up": int((df["涨跌幅"] > 0).sum()),
        "down": int((df["涨跌幅"] < 0).sum()),
        "flat": int((df["涨跌幅"] == 0).sum()),
        "limit_up": int((df["涨跌幅"] >= 9.8).sum()),
        "limit_down": int((df["涨跌幅"] <= -9.8).sum()),
        "total": len(df),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "trading": trading
    }


def get_stock_spot(stock_codes: List[str], api_mode: bool = False) -> Tuple[Optional[pd.DataFrame], bool]:
    """获取指定股票集合的实时行情。API 模式下仅读取内存缓存，绝不发起同步请求。"""
    global _SPOT_CACHE, _SPOT_CACHE_TIME
    
    with _SPOT_CACHE_LOCK:
        cache = _SPOT_CACHE
        cache_time = _SPOT_CACHE_TIME
    
    if api_mode:
        if cache is not None:
            df_spot = cache[cache["代码"].isin(stock_codes)].copy()
            return df_spot, not df_spot.empty
        return None, False

    # 命令行/同步调用逻辑
    if is_trading_time() or cache is None:
        refresh_spot_cache(force=True)
        with _SPOT_CACHE_LOCK: cache = _SPOT_CACHE
            
    if cache is not None:
        df_spot = cache[cache["代码"].isin(stock_codes)].copy()
        return df_spot, not df_spot.empty
    return None, False


def get_fund_top10_with_change(fund_code: str, api_mode: bool = False):
    """
    核心算法：获取最新持仓 -> 匹配实时行情 -> 估算基金涨幅。
    """
    today = date.today()
    years_to_try = [str(today.year - i) for i in range(3)]

    df_hold = None
    found_quarter = None

    for year in years_to_try:
        try:
            df = fetch_with_retry(lambda y=year: ak.fund_portfolio_hold_em(symbol=fund_code, date=y))
            if df is None or df.empty: continue

            df.columns = df.columns.str.strip()
            actual_quarters = df["季度"].unique().tolist()
            
            # 排序逻辑：寻找最新季度的持仓数据
            def parse_q(label):
                nums = re.findall(r'\d+', label)
                return (int(nums[0]), int(nums[1])) if len(nums) >= 2 else (0, 0)

            latest_quarter = max(actual_quarters, key=parse_q)
            df_q = df[df["季度"] == latest_quarter]

            if not df_q.empty:
                df_hold = df_q.copy()
                found_quarter = latest_quarter
                break
        except: continue

    if df_hold is None or df_hold.empty:
        raise ValueError(f"❌ 未找到基金 {fund_code} 的任何持仓数据")

    df_hold["股票代码"] = df_hold["股票代码"].astype(str).str.zfill(6)
    stock_codes = df_hold["股票代码"].tolist()

    # 获取行情 (API 模式下不发起请求)
    df_spot, is_live = get_stock_spot(stock_codes, api_mode=api_mode)
    
    if not is_live:
        return df_hold[["序号", "股票代码", "股票名称", "占净值比例"]].copy(), None, found_quarter

    # 数据合并与估算计算
    df_result = df_hold[["序号", "股票代码", "股票名称", "占净值比例"]].merge(
        df_spot[["代码", "涨跌幅"]], left_on="股票代码", right_on="代码", how="left"
    ).drop(columns=["代码"])

    df_result.rename(columns={"涨跌幅": "实时涨跌幅(%)"}, inplace=True)
    df_result["权重"] = pd.to_numeric(df_result["占净值比例"].astype(str).str.replace("%", "").str.strip(), errors="coerce") / 100
    df_result["贡献涨跌幅(%)"] = (df_result["实时涨跌幅(%)"] * df_result["权重"]).round(4)

    estimated_change = df_result["贡献涨跌幅(%)"].sum()
    return df_result, estimated_change, found_quarter


def get_fund_top10_json(fund_code: str) -> dict:
    """包装业务逻辑，返回前端友好的 JSON 结构。"""
    df_result, estimated_change, found_quarter = get_fund_top10_with_change(fund_code, api_mode=True)
    
    # 匹配基金简称
    fund_name = "未知基金"
    with _FUND_LIST_LOCK:
        if _FUND_LIST_CACHE is not None:
            name_match = _FUND_LIST_CACHE[_FUND_LIST_CACHE["基金代码"] == fund_code]["基金简称"]
            if not name_match.empty: fund_name = name_match.iloc[0]

    top10_weight = None
    holdings = []
    if df_result is not None and not df_result.empty:
        if "权重" in df_result.columns:
            top10_weight = float(df_result["权重"].sum())
        for _, row in df_result.iterrows():
            h = {
                "index": int(row.get("序号", 0)),
                "code": str(row.get("股票代码", "")),
                "name": str(row.get("股票名称", "")),
                "weight_pct": float(str(row.get("占净值比例", "0")).replace("%", "").strip()) if pd.notna(row.get("占净值比例")) else 0,
                "change_pct": float(row.get("实时涨跌幅(%)")) if pd.notna(row.get("实时涨跌幅(%)")) else None,
                "contribution": float(row.get("贡献涨跌幅(%)")) if pd.notna(row.get("贡献涨跌幅(%)")) else None,
            }
            holdings.append(h)

    return {
        "fund_code": fund_code,
        "fund_name": fund_name,
        "quarter": found_quarter,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "estimated_change": float(estimated_change) if estimated_change is not None else None,
        "top10_weight_pct": round(top10_weight * 100, 2) if top10_weight is not None else None,
        "holdings": holdings,
    }
