"""
AI提示词配置文件
此文件包含用于AI分析的提示词模板，可以随时修改以调整AI输出格式和内容
"""

# 基础AI分析提示词模板
AI_ANALYSIS_PROMPT_TEMPLATE = """请基于以下基金信息生成一份专业的AI分析报告：

{context}

请按照以下结构输出分析报告：
1. 基金投资风格
2. 行业集中度  
3. 持仓逻辑
4. 风险评估
5. 未来展望

每个部分提供详细分析，语言专业但易于理解。"""


# 上下文信息格式化模板
CONTEXT_FORMAT_TEMPLATE = """
基金代码: {fund_code}
基金名称: {fund_name}
预估涨幅: {estimated_change}%
持仓数据: {holdings_json}
报告季度: {quarter}
"""