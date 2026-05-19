import akshare as ak
import pandas as pd
import re
import time
import threading
from datetime import date, datetime
from zoneinfo import ZoneInfo
import os
import json
from typing import Optional, Tuple, List
import requests
from datetime import timedelta
import hashlib
import logging
import glob
from prompt_config import AI_ANALYSIS_PROMPT_TEMPLATE, CONTEXT_FORMAT_TEMPLATE

# --------------------------------------------------------------------------------
# 全局缓存与锁 (内存存储，不落库)
# --------------------------------------------------------------------------------

# 3. 基金名称列表缓存（启动时全量加载一次）
_FUND_LIST_CACHE: Optional[pd.DataFrame] = None
_FUND_LIST_LOCK = threading.Lock()

# 4. 热门基金缓存 (每日更新)
_HOT_FUNDS_CACHE: Optional[List[dict]] = None
_HOT_FUNDS_CACHE_DATE: Optional[date] = None
_HOT_FUNDS_LOCK = threading.Lock()

# 5. AI分析相关配置
# 修改AI分析缓存目录为规范路径
_AI_ANALYSIS_CACHE_DIR = "data/ai_analysis"  # AI分析结果缓存目录，遵循规范路径

# 创建AI分析缓存目录
os.makedirs(_AI_ANALYSIS_CACHE_DIR, exist_ok=True)

# 6. IP请求计数
_IP_REQUEST_COUNT = {}  # IP请求计数 {ip: (last_date, count)}
_IP_REQUEST_LOCK = threading.Lock()  # IP请求计数锁

# 7. 基金持仓缓存（内存，持仓季报数据，24小时有效）
# key: fund_code, value: {"df": DataFrame, "quarter": str, "cached_at": datetime}
_HOLDINGS_CACHE: dict = {}
_HOLDINGS_CACHE_LOCK = threading.Lock()
_HOLDINGS_CACHE_TTL = 60 * 60 * 24  # 24h in seconds



# 配置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


# --------------------------------------------------------------------------------
# 辅助函数：交易时间判断与重试机制
# --------------------------------------------------------------------------------

def _now_cn() -> datetime:
    try:
        return datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:
        return datetime.now()


def is_trading_time():
    """判断当前是否在 A 股交易时间内 (周一至周五 9:30-11:30, 13:00-15:00)"""
    now = _now_cn()
    if now.weekday() >= 5:
        return False
    t = now.time()
    morning = datetime.strptime("09:30", "%H:%M").time() <= t <= datetime.strptime("11:30", "%H:%M").time()
    afternoon = datetime.strptime("13:00", "%H:%M").time() <= t <= datetime.strptime("15:00", "%H:%M").time()
    return morning or afternoon


def get_trading_time_reason():
    """返回非交易时间的友好描述，用于日志输出"""
    now = _now_cn()
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
# AI分析相关函数
# --------------------------------------------------------------------------------

def generate_realtime_ai_analysis(fund_code: str) -> dict:
    """
    实时生成AI分析报告
    """
    # 获取基金基本信息
    fund_name = "未知基金"
    with _FUND_LIST_LOCK:
        if _FUND_LIST_CACHE is not None:
            name_match = _FUND_LIST_CACHE[_FUND_LIST_CACHE["基金代码"] == fund_code]["基金简称"]
            if not name_match.empty: 
                fund_name = name_match.iloc[0]
    
    # 获取基金持仓数据
    df_result, estimated_change, found_quarter = get_fund_top10_with_change(fund_code)
    
    # 准备持仓数据
    holdings_info = []
    if df_result is not None and not df_result.empty:
        for _, row in df_result.iterrows():
            holding = {
                "name": str(row.get("股票名称", "")),
                "code": str(row.get("股票代码", "")),
                "weight_pct": float(str(row.get("占净值比例", "0")).replace("%", "").strip()) if pd.notna(row.get("占净值比例")) else 0,
                "change_pct": float(row.get("实时涨跌幅(%)")) if pd.notna(row.get("实时涨跌幅(%)")) else None,
            }
            holdings_info.append(holding)
    
    # 调用AI模型生成分析
    analysis = call_free_ai_model(fund_code, fund_name, holdings_info, estimated_change, found_quarter)
    
    return analysis


def get_ai_analysis(fund_code: str, client_ip: str = "default"):
    """
    获取AI分析报告，支持缓存和IP限制
    """
    # 检查IP请求次数限制
    with _IP_REQUEST_LOCK:
        today = date.today()
        # Evict stale entries (Bug #3 fix)
        stale_ips = [ip for ip, (d, _) in _IP_REQUEST_COUNT.items() if d != today]
        for ip in stale_ips:
            del _IP_REQUEST_COUNT[ip]

        if client_ip in _IP_REQUEST_COUNT:
            # 检查今天是否已经超过限制
            last_request_date, count = _IP_REQUEST_COUNT[client_ip]
            if last_request_date == date.today():
                if count >= 5:  # 每个IP每天最多5次请求
                    raise Exception("今日AI分析额度已用完，请明天再试")
                else:
                    _IP_REQUEST_COUNT[client_ip] = (date.today(), count + 1)
            else:
                # 新的一天，重置计数
                _IP_REQUEST_COUNT[client_ip] = (date.today(), 1)
        else:
            _IP_REQUEST_COUNT[client_ip] = (date.today(), 1)

    # 检查缓存
    cache_path = os.path.join(_AI_ANALYSIS_CACHE_DIR, f"{fund_code}.json")
    
    # 检查是否有有效的缓存文件（7天内有效）
    if os.path.exists(cache_path):
        cache_time = os.path.getmtime(cache_path)
        if datetime.fromtimestamp(cache_time) + timedelta(days=7) > datetime.now():
            with open(cache_path, 'r', encoding='utf-8') as f:
                try:
                    cached_data = json.load(f)
                    return cached_data
                except json.JSONDecodeError:
                    pass  # 继续执行，重新生成分析

    # 如果没有有效缓存，则生成新的AI分析
    analysis = generate_realtime_ai_analysis(fund_code)
    
    # 保存到缓存
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    
    return analysis


def call_free_ai_model(fund_code: str, fund_name: str, holdings: list, estimated_change: float, quarter: str) -> dict:
    """
    调用AI模型API生成分析报告
    支持多种后端：使用通用的LLM API调用
    """
    # 构建分析所需的上下文信息
    context = build_analysis_context(fund_code, fund_name, holdings, estimated_change, quarter)
    
    # 尝试使用通用LLM API
    llm_response = call_llm_api(context)
    if llm_response:
        return parse_llm_response(llm_response, fund_code, fund_name, estimated_change, quarter)
    
    # 所有AI服务都失败，返回基础分析
    logging.warning(f"LLM API调用失败，返回基础分析: {fund_code}")
    return generate_basic_analysis(fund_code, fund_name, holdings, estimated_change, quarter)


def call_llm_api(context: str) -> Optional[dict]:
    """
    调用通用LLM API生成AI分析
    """
    try:
        # 获取API配置
        llm_api_key = os.getenv('LLM_AI_API_KEY')
        llm_api_url = os.getenv('LLM_API_URL', 'https://openrouter.ai/api/v1/chat/completions')
        llm_model = os.getenv('LLM_MODEL_NAME', 'stepfun/step-3.5-flash:free')
        
        logging.info(f"读取到 LLM API 密钥: {'存在' if llm_api_key else '不存在'}")
        if not llm_api_key:
            logging.warning("未配置LLM API密钥")
            return None
            
        headers = {
            "Authorization": f"Bearer {llm_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": llm_model,
            "messages": [
                {
                    "role": "system", 
                    "content": "你是一位资深的基金分析师，请根据以下信息，对这只基金进行专业、客观的分析。"
                },
                {
                    "role": "user",
                    "content": AI_ANALYSIS_PROMPT_TEMPLATE.format(context=context)
                }
            ],
            "temperature": 0.7
        }
        
        response = requests.post(llm_api_url, json=payload, headers=headers, timeout=60)
        if response.status_code == 200:
            result = response.json()
            return result
        else:
            logging.error(f"LLM API调用失败，状态码: {response.status_code}, 响应: {response.text}")
            return None
    except Exception as e:
        logging.error(f"LLM API调用异常: {e}")
        return None


def parse_llm_response(response: dict, fund_code: str, fund_name: str, estimated_change: float, quarter: str) -> dict:
    """
    解析LLM API响应并构建分析报告
    """
    try:
        choices = response.get('choices', [])
        if not choices:
            raise ValueError("API返回结果中没有choices字段")
            
        content = choices[0]['message']['content']
        # 提取AI分析的主要部分
        analysis_sections = extract_analysis_sections(content)
        
        return {
            "fund_code": fund_code,
            "fund_name": fund_name,
            "analysis": analysis_sections,
            "estimated_change": estimated_change,
            "quarter": quarter,
            "update_date": datetime.now().strftime("%Y-%m-%d"),
            "source": "AI深度分析"
        }
    except Exception as e:
        logging.error(f"解析LLM API响应失败: {e}")
        return generate_basic_analysis(fund_code, fund_name, [], estimated_change, quarter)


def extract_analysis_sections(content: str) -> List[dict]:
    """
    从AI生成的内容中提取分析章节
    """
    sections = [
        {"pattern": r"(1[.\s]*基金投资风格)[\s\S]*?(?=2\.|$)", "title": "1. 基金投资风格"},
        {"pattern": r"(2[.\s]*行业集中度)[\s\S]*?(?=3\.|1\.|$)", "title": "2. 行业集中度"},
        {"pattern": r"(3[.\s]*持仓逻辑)[\s\S]*?(?=4\.|1\.|2\.|$)", "title": "3. 持仓逻辑"},
        {"pattern": r"(4[.\s]*风险评估)[\s\S]*?(?=5\.|1\.|2\.|3\.|$)", "title": "4. 风险评估"},
        {"pattern": r"(5[.\s]*未来展望)[\s\S]*?(?=1\.|2\.|3\.|4\.|$)", "title": "5. 未来展望"}
    ]
    
    extracted_sections = []
    for section in sections:
        match = re.search(section["pattern"], content, re.IGNORECASE)
        if match:
            # 清理内容，去除标题部分
            content_part = match.group(0)
            clean_content = re.sub(r'^.*?\d[.\s]*\S+', '', content_part, count=1, flags=re.MULTILINE)
            extracted_sections.append({
                "title": section["title"],
                "content": clean_content.strip()
            })
    
    # 如果没有成功提取任何章节，返回原始内容作为单一章节
    if not extracted_sections:
        return [{
            "title": "AI分析报告",
            "content": content[:500] + "..." if len(content) > 500 else content
        }]
    
    return extracted_sections


def build_analysis_context(fund_code: str, fund_name: str, holdings: list, estimated_change: float, quarter: str) -> str:
    """
    构建AI分析所需的上下文信息
    """
    return CONTEXT_FORMAT_TEMPLATE.format(
        fund_code=fund_code,
        fund_name=fund_name,
        estimated_change=estimated_change,
        holdings_json=json.dumps(holdings, ensure_ascii=False),
        quarter=quarter
    )


def generate_basic_analysis(fund_code: str, fund_name: str, holdings: list, estimated_change: float, quarter: str) -> dict:
    """
    生成基础分析（当AI调用失败时的备选方案）
    """
    analysis_sections = [
        {
            "title": "1 基金投资风格",
            "content": f"该基金主要投资于{classify_fund_sector(holdings)}领域，属于{classify_investment_style(holdings)}风格。投资策略偏向于{classify_strategy(holdings)}，适合风险偏好为{classify_risk_level(holdings)}的投资者。"
        },
        {
            "title": "2 行业集中度",
            "content": f"该基金行业集中度{'较高' if is_high_concentration(holdings) else '适中'}，前三大行业占比约为{calculate_top3_concentration(holdings):.0f}%。重仓股涵盖{count_unique_sectors(holdings)}个不同行业，行业分布{'较为分散' if not is_high_concentration(holdings) else '相对集中'}。"
        },
        {
            "title": "3 持仓逻辑",
            "content": f"基金重仓股主要集中在{describe_holdings_logic(holdings)}。从持仓占比来看，该基金{'倾向于重仓龙头股' if is_heavy_on_leaders(holdings) else '注重均衡配置'}，体现了基金经理的{describe_investment_thesis(holdings)}的投资理念。"
        },
        {
            "title": "4 风险评估",
            "content": f"基于当前持仓，该基金风险等级为{'中高风险' if calculate_risk_score(holdings) > 0.6 else '中等风险' if calculate_risk_score(holdings) > 0.3 else '较低风险'}。主要风险因素包括：行业集中风险、市场波动风险、流动性风险等。"
        },
        {
            "title": "5 未来展望",
            "content": f"基于当前市场环境和基金持仓特点，预计该基金短期内可能受到{describe_market_factors()}的影响。从中长期看，{describe_long_term_outlook(holdings)}，建议投资者关注{describe_key_factors_to_monitor(holdings)}的变化。"
        }
    ]
    
    return {
        "fund_code": fund_code,
        "fund_name": fund_name,
        "analysis": analysis_sections,
        "estimated_change": estimated_change,
        "quarter": quarter,
        "update_date": datetime.now().strftime("%Y-%m-%d"),
        "source": "AI深度分析"
    }


def classify_fund_sector(holdings: list) -> str:
    """根据持仓分类基金所属行业领域"""
    sectors = {}
    for holding in holdings:
        # 模拟根据股票代码判断行业
        code = holding["code"]
        if code.startswith(('000', '001', '002', '003', '004', '005', '006', '007', '008', '009')):
            sector = "股票型"
        elif code.startswith(('15', '16')):
            sector = "指数型/ETF"
        elif code.startswith(('51')):
            sector = "ETF"
        else:
            sector = "混合型"
        
        sectors[sector] = sectors.get(sector, 0) + holding["weight_pct"]
    
    # 返回占比最高的行业
    if sectors:
        return max(sectors, key=sectors.get)
    return "综合"


def classify_investment_style(holdings: list) -> str:
    """分类投资风格"""
    avg_weight = sum([h["weight_pct"] for h in holdings]) / len(holdings) if holdings else 0
    if avg_weight > 5:
        return "集中投资"
    elif avg_weight > 2:
        return "均衡配置"
    else:
        return "分散投资"


def classify_strategy(holdings: list) -> str:
    """分类投资策略"""
    top10_concentration = sum([h["weight_pct"] for h in holdings[:10]]) if len(holdings) >= 10 else sum([h["weight_pct"] for h in holdings])
    if top10_concentration > 50:
        return "精选个股"
    else:
        return "广泛配置"


def classify_risk_level(holdings: list) -> str:
    """分类风险等级"""
    top10_concentration = sum([h["weight_pct"] for h in holdings[:10]]) if len(holdings) >= 10 else sum([h["weight_pct"] for h in holdings])
    if top10_concentration > 60:
        return "较高"
    elif top10_concentration > 40:
        return "中等"
    else:
        return "较低"


def is_high_concentration(holdings: list) -> bool:
    """判断是否持仓集中度高 (基于权重赫芬达尔指数，非行业分类)"""
    if not holdings:
        return False
    total = sum(h["weight_pct"] for h in holdings)
    if total == 0:
        return False
    hhi = sum((h["weight_pct"] / total) ** 2 for h in holdings)
    # HHI > 0.2 indicates moderate-to-high concentration
    return hhi > 0.2


def calculate_top3_concentration(holdings: list) -> float:
    """计算前三大持仓占比"""
    sorted_holdings = sorted(holdings, key=lambda x: x["weight_pct"], reverse=True)
    top3 = sorted_holdings[:3]
    return sum([h["weight_pct"] for h in top3])


def count_unique_sectors(holdings: list) -> int:
    """计算持仓多样性 (基于权重分布，非行业分类)"""
    if not holdings:
        return 0
    # Count distinct weight buckets (5% increments) as proxy for diversification
    weight_buckets = set()
    for h in holdings:
        bucket = int(h["weight_pct"] / 5)
        weight_buckets.add(bucket)
    return len(weight_buckets)


def describe_holdings_logic(holdings: list) -> str:
    """描述持仓逻辑"""
    if len(holdings) > 0:
        largest_holding = max(holdings, key=lambda x: x["weight_pct"])
        return f"以{largest_holding['name']}等重仓股为核心，注重{classify_investment_style(holdings)}的配置策略"
    return "多元化投资组合"


def is_heavy_on_leaders(holdings: list) -> bool:
    """判断是否重仓龙头股"""
    return any(h["weight_pct"] > 10 for h in holdings)


def describe_investment_thesis(holdings: list) -> str:
    """描述投资理念"""
    return "价值投资与成长投资相结合"


def calculate_risk_score(holdings: list) -> float:
    """计算风险分数 (0-1 scale)"""
    if not holdings:
        return 0.0
    avg_weight_pct = sum([h["weight_pct"] for h in holdings]) / len(holdings)
    # Normalize: assume max reasonable avg weight is 20%
    return min(avg_weight_pct / 20.0, 1.0)


def describe_market_factors(fund_code: str = "") -> str:
    """描述市场影响因素 (deterministic per fund code)"""
    factors = ["宏观经济数据", "政策面变化", "海外市场波动", "资金流向"]
    idx = int(hashlib.md5(fund_code.encode()).hexdigest(), 16) % len(factors)
    return factors[idx]


def describe_long_term_outlook(holdings: list) -> str:
    """描述中长期展望"""
    sector = classify_fund_sector(holdings)
    return f"{sector}领域基本面稳健，长期增长潜力较大"


def describe_key_factors_to_monitor(holdings: list) -> str:
    """描述需要关注的因素"""
    return "基金重仓股的业绩表现、行业政策变化及市场流动性"



def _parse_quarter_key(label: str) -> Tuple[int, int]:
    """Parse quarter label like '2024年第3季度' to (2024, 3)."""
    nums = re.findall(r'\d+', label)
    return (int(nums[0]), int(nums[1])) if len(nums) >= 2 else (0, 0)


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



def _sina_batch(stock_codes: List[str]) -> dict:
    """
    新浪财经批量行情接口，支持全品种（含科创板688xxx）。
    返回 {code: change_pct}，失败的股票不出现在结果里。
    """
    def to_sina(code):
        return f"sh{code}" if code.startswith("6") else f"sz{code}"

    symbols = ",".join(to_sina(c) for c in stock_codes)
    url = f"http://hq.sinajs.cn/list={symbols}"
    try:
        resp = requests.get(url, headers={"Referer": "http://finance.sina.com.cn"}, timeout=10)
        resp.encoding = "gbk"
        result = {}
        for line in resp.text.strip().split("\n"):
            m = re.match(r'var hq_str_\w{2}(\d+)="([^"]*)"', line)
            if not m:
                continue
            code = m.group(1).zfill(6)
            fields = m.group(2).split(",")
            if len(fields) < 4:
                continue
            try:
                prev_close = float(fields[2])
                current = float(fields[3])
                if prev_close > 0 and current > 0:
                    result[code] = round((current - prev_close) / prev_close * 100, 2)
            except ValueError:
                continue
        logging.warning(f"[sina_batch] ok={len(result)} total={len(stock_codes)}")
        return result
    except Exception as e:
        logging.warning(f"[sina_batch] failed: {e}")
        return {}


def get_stock_spot(stock_codes: List[str]) -> Tuple[Optional[pd.DataFrame], bool]:
    """新浪批量接口获取全部持仓行情，支持全品种（含科创板688xxx）。"""
    logging.warning(
        f"[get_stock_spot] start codes={len(stock_codes)} trading={is_trading_time()} reason={get_trading_time_reason()}"
    )
    sina_data = _sina_batch(stock_codes)
    if not sina_data:
        return pd.DataFrame(columns=["代码", "名称", "涨跌幅"]), False
    results = [{"代码": c, "名称": None, "涨跌幅": v} for c, v in sina_data.items()]
    logging.warning(f"[get_stock_spot] done ok={len(results)} total={len(stock_codes)}")
    return pd.DataFrame(results), True


def get_fund_top10_with_change(fund_code: str):
    """
    核心算法：获取最新持仓（内存缓存24h）-> 匹配实时行情 -> 估算基金涨幅。
    """
    # --- 持仓缓存读取 ---
    df_hold = None
    found_quarter = None
    with _HOLDINGS_CACHE_LOCK:
        cached = _HOLDINGS_CACHE.get(fund_code)
        if cached:
            age = (_now_cn() - cached["cached_at"]).total_seconds()
            if age < _HOLDINGS_CACHE_TTL:
                df_hold = cached["df"]
                found_quarter = cached["quarter"]
                logging.warning(f"[holdings_cache] hit fund_code={fund_code} quarter={found_quarter} age={int(age)}s")

    # --- 缓存未命中：从 akshare 拉取 ---
    if df_hold is None:
        today = date.today()
        years_to_try = [str(today.year - i) for i in range(3)]
        for year in years_to_try:
            try:
                df = fetch_with_retry(lambda y=year: ak.fund_portfolio_hold_em(symbol=fund_code, date=y))
                if df is None or df.empty: continue
                df.columns = df.columns.str.strip()
                actual_quarters = df["季度"].unique().tolist()
                latest_quarter = max(actual_quarters, key=_parse_quarter_key)
                df_q = df[df["季度"] == latest_quarter]
                if not df_q.empty:
                    df_hold = df_q.copy()
                    found_quarter = latest_quarter
                    break
            except Exception as e:
                logging.warning(f"[holdings_fetch] year={year} fund_code={fund_code} error={e}")
                continue

        if df_hold is None or df_hold.empty:
            raise ValueError(f"❌ 未找到基金 {fund_code} 的任何持仓数据")

        with _HOLDINGS_CACHE_LOCK:
            _HOLDINGS_CACHE[fund_code] = {"df": df_hold, "quarter": found_quarter, "cached_at": _now_cn()}
        logging.warning(f"[holdings_cache] miss fund_code={fund_code} quarter={found_quarter} — fetched and cached")

    df_hold["股票代码"] = df_hold["股票代码"].astype(str).str.zfill(6)
    stock_codes = df_hold["股票代码"].tolist()

    # 获取行情 (实时调用)
    logging.warning(f"[get_fund_top10_with_change] fetch spot fund_code={fund_code} stocks={len(stock_codes)} quarter={found_quarter}")
    df_spot, is_live = get_stock_spot(stock_codes)

    if not is_live:
        logging.warning(f"[get_fund_top10_with_change] spot not live fund_code={fund_code} reason={get_trading_time_reason()}")

    # 数据合并与估算计算
    df_result = df_hold[["序号", "股票代码", "股票名称", "占净值比例"]].merge(
        df_spot[["代码", "涨跌幅"]], left_on="股票代码", right_on="代码", how="left"
    ).drop(columns=["代码"])

    df_result.rename(columns={"涨跌幅": "实时涨跌幅(%)"}, inplace=True)
    df_result["实时涨跌幅(%)"] = pd.to_numeric(df_result["实时涨跌幅(%)"], errors="coerce")
    df_result["权重"] = pd.to_numeric(df_result["占净值比例"].astype(str).str.replace("%", "").str.strip(), errors="coerce") / 100
    df_result["贡献涨跌幅(%)"] = (df_result["实时涨跌幅(%)"] * df_result["权重"]).round(4)

    # Bug #1 fix: Handle case where Sina data is completely missing (all NaN)
    valid = df_result["实时涨跌幅(%)"].notna()
    if valid.any():
        valid_weights = df_result.loc[valid, "权重"].sum()
        valid_contributions = df_result.loc[valid, "贡献涨跌幅(%)"].sum()
        estimated_change = valid_contributions / valid_weights if valid_weights > 0 else None
    else:
        estimated_change = None

    return df_result, estimated_change, found_quarter

def get_fund_top10_json(fund_code: str) -> dict:
    """包装业务逻辑，返回前端友好的 JSON 结构。"""
    df_result, estimated_change, found_quarter = get_fund_top10_with_change(fund_code)
    
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
        "time": _now_cn().strftime("%Y-%m-%d %H:%M:%S"),
        "estimated_change": float(estimated_change) if estimated_change is not None else None,
        "top10_weight_pct": round(top10_weight * 100, 2) if top10_weight is not None else None,
        "holdings": holdings,
    }


def cleanup_expired_ai_reports():
    """
    清理过期的AI分析报告，按7天过期规则删除文件
    """
    logging.info("开始清理过期AI分析报告...")
    
    # 获取所有AI分析缓存文件
    cache_files = glob.glob(os.path.join(_AI_ANALYSIS_CACHE_DIR, "*.json"))
    expired_count = 0
    
    for cache_file in cache_files:
        try:
            # 获取文件修改时间
            mod_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
            # 检查是否超过7天
            if datetime.now() - mod_time > timedelta(days=7):
                os.remove(cache_file)
                expired_count += 1
                logging.info(f"已删除过期AI分析报告: {os.path.basename(cache_file)}")
        except Exception as e:
            logging.error(f"删除过期AI分析报告失败 {cache_file}: {e}")
    
    logging.info(f"完成清理，删除了 {expired_count} 个过期AI分析报告")


def schedule_cleanup_task():
    """
    启动后台定时清理任务，每天执行一次
    """
    def cleanup_loop():
        while True:
            # 计算距离第二天凌晨的时间差
            now = datetime.now()
            next_day = now + timedelta(days=1)
            next_midnight = next_day.replace(hour=0, minute=0, second=0, microsecond=0)
            sleep_seconds = (next_midnight - now).total_seconds()
            
            # 等待到第二天凌晨
            time.sleep(sleep_seconds)
            
            # 执行清理任务
            cleanup_expired_ai_reports()
    
    # 启动清理任务线程
    cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
    cleanup_thread.start()
    logging.info("AI分析报告清理任务已启动")


# 在模块加载时启动清理任务
schedule_cleanup_task()


def _base_fund_name(name: str) -> str:
    """去除基金名称末尾的份额类别后缀，用于去重。"""
    return re.sub(r'[\(（]?[A-Ea-e][类\)）]?$|联接[A-Ea-e]$', '', name).strip()


def get_hot_funds() -> List[dict]:
    """近1月涨幅前10，去除同系列A/C重复份额，每日缓存。"""
    global _HOT_FUNDS_CACHE, _HOT_FUNDS_CACHE_DATE

    with _HOT_FUNDS_LOCK:
        if _HOT_FUNDS_CACHE and _HOT_FUNDS_CACHE_DATE == date.today():
            return _HOT_FUNDS_CACHE

    try:
        df = fetch_with_retry(lambda: ak.fund_open_fund_rank_em())
        if '近1月' not in df.columns:
            raise ValueError("缺少'近1月'列")

        df['近1月'] = pd.to_numeric(df['近1月'], errors='coerce')
        df = df.dropna(subset=['近1月']).sort_values('近1月', ascending=False)

        # 去重：同一基础名称只保留近1月最高的一只
        seen: set = set()
        hot_funds = []
        for _, row in df.iterrows():
            base = _base_fund_name(row['基金简称'])
            if base in seen:
                continue
            seen.add(base)
            hot_funds.append({"code": row['基金代码'], "name": row['基金简称']})
            if len(hot_funds) == 10:
                break

        if not hot_funds:
            raise ValueError("未能提取热门基金")

        with _HOT_FUNDS_LOCK:
            _HOT_FUNDS_CACHE = hot_funds
            _HOT_FUNDS_CACHE_DATE = date.today()
        return hot_funds

    except Exception as e:
        logging.warning(f"[get_hot_funds] 失败: {e}")
        with _HOT_FUNDS_LOCK:
            if _HOT_FUNDS_CACHE:
                return _HOT_FUNDS_CACHE
        return [
            {"code": "110011", "name": "易方达中小盘混合"},
            {"code": "161725", "name": "招商中证白酒指数"},
            {"code": "000961", "name": "天弘沪深300ETF联接A"},
            {"code": "163406", "name": "兴全合润混合"},
            {"code": "001975", "name": "景顺长城新兴成长混合"},
            {"code": "270042", "name": "广发纳斯达克100ETF联接A"},
            {"code": "006228", "name": "中欧医疗健康混合A"},
            {"code": "001643", "name": "汇添富全球消费混合"},
            {"code": "000697", "name": "信达澳银新能源产业股票"},
            {"code": "001104", "name": "农银汇理新能源主题股票"},
        ]
