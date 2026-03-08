"""
FastAPI 后端：提供基金估算 API，供前端调用。
- 行情用应用内内存缓存，后台线程每 10 秒用 akshare 刷新，不落库。
- 运行: uvicorn api:app --reload
"""
import os
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from fund_estimation import (
    get_fund_top10_json, 
    start_spot_refresh_background, 
    search_funds, 
    get_market_sentiment
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_spot_refresh_background()
    yield


app = FastAPI(
    title="基金涨幅估算",
    description="根据十大重仓股实时涨跌幅估算基金当日涨幅",
    lifespan=lifespan,
)

# 允许前端跨域（GitHub Pages 或任意域名调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/fund/{fund_code}")
def api_fund(fund_code: str):
    """根据基金代码返回十大重仓 + 估算涨幅（行情来自内存缓存，由后台每 10 秒刷新）。"""
    if not fund_code.isdigit() or len(fund_code) > 6:
        raise HTTPException(status_code=400, detail="基金代码应为数字，最多6位")
    try:
        return get_fund_top10_json(fund_code.strip())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器错误: {e}")


@app.get("/api/search")
def api_search(q: str):
    """根据关键词搜索基金代码或名称"""
    if len(q) < 2:
        return []
    return search_funds(q)


@app.get("/api/sentiment")
def api_sentiment():
    """获取全市场行情情绪统计"""
    return get_market_sentiment()


@app.get("/api/hot-funds")
def api_hot_funds():
    """ TODO: 热门基金应该以如下逻辑做：过去1个月涨幅最高的三只基金"""
    """获取热门基金列表（静态数据，无数据库）"""
    return [
        {"code": "020465", "name": "招商中证半导体产业ETF联接C"},
        {"code": "001508", "name": "富国中证红利指数增强A"},
        {"code": "161725", "name": "招商白酒"},
        {"code": "005827", "name": "易方达蓝筹精选混合"}
    ]


@app.get("/api/ai-analysis/{fund_code}")
def api_ai_analysis(fund_code: str):
    """获取预生成的 AI 分析报告内容"""
    file_path = os.path.join(os.path.dirname(__file__), "data", "ai_analysis", f"{fund_code}.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="该基金暂无 AI 深度分析报告")
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取分析报告失败: {e}")
