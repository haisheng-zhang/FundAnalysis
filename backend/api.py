"""
FastAPI 后端：提供基金估算 API，供前端调用。
- 行情用应用内内存缓存，后台线程每 10 秒用 akshare 刷新，不落库。
- 运行: uvicorn api:app --reload
"""
import os
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from fund_estimation import (
    get_fund_top10_json, 
    search_funds, 
    get_hot_funds,
    get_ai_analysis,
    refresh_fund_list_cache
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("  🚀 后端服务启动中...")
    refresh_fund_list_cache() # 启动时加载基金列表用于搜索
    yield
    print("  👋 后端服务已关闭")


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
def api_fund(request: Request, fund_code: str):
    """根据基金代码返回十大重仓 + 估算涨幅。"""
    client_ip = request.client.host if request.client else "unknown"
    logging.warning(f"[api_fund] start fund_code={fund_code} ip={client_ip}")

    if not fund_code.isdigit() or len(fund_code) > 6:
        raise HTTPException(status_code=400, detail="基金代码应为数字，最多6位")

    try:
        result = get_fund_top10_json(fund_code.strip())
        logging.warning(
            f"[api_fund] done fund_code={fund_code} ip={client_ip} estimated_change={result.get('estimated_change')} holdings={len(result.get('holdings', []))}"
        )
        return result
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


@app.get("/api/hot-funds")
def api_hot_funds():
    """获取热门基金列表（过去一个月涨幅前10，已去除同系列重复份额）"""
    return get_hot_funds()


@app.get("/api/ai-analysis/{fund_code}")
def api_ai_analysis(request: Request, fund_code: str):
    """获取基金的 AI 分析报告，带IP限制"""
    # 获取客户端IP
    client_ip = request.client.host
    logging.info(f"[api_ai_analysis] incoming request fund_code={fund_code}, ip={client_ip}")
    
    # 基金代码校验（只接受最多6位数字的基金代码）
    if not fund_code.isdigit() or len(fund_code) > 6:
        raise HTTPException(status_code=404, detail="基金代码无效或不存在")
    
    try:
        return get_ai_analysis(fund_code, client_ip)
    except Exception as e:
        if "今日AI分析额度已用完" in str(e):
            raise HTTPException(status_code=429, detail=str(e))
        else:
            # 即使AI分析失败，也返回基础分析而不是抛出错误
            from fund_estimation import generate_realtime_ai_analysis
            try:
                return generate_realtime_ai_analysis(fund_code)
            except Exception as inner_e:
                raise HTTPException(status_code=500, detail=f"AI分析生成失败: {inner_e}")
