"""集中配置：分类体系、检索关键词、Prompt、评分权重"""

# ============================================================
# arXiv 检索配置
# ============================================================

ARXIV_CATEGORIES = ["cs.IR", "cs.LG", "stat.ML", "cs.AI", "econ.GN"]

SEARCH_QUERIES = {
    # 推荐系统 + 营销增长（cs.IR 两方向都搜）
    "cs.IR": '(abs:"recommendation" OR abs:"recommender" OR abs:"collaborative filtering" OR abs:"ranking" OR abs:"retrieval" OR abs:"coupon" OR abs:"pricing" OR abs:"subsidy" OR abs:"uplift" OR abs:"marketing" OR ti:"recommendation" OR ti:"recommender")',
    # cs.LG 覆盖推荐 + CTR + 营销增长
    "cs.LG": '(abs:"recommendation" OR abs:"recommender" OR abs:"CTR prediction" OR abs:"click-through rate" OR abs:"sequential recommendation" OR abs:"coupon" OR abs:"pricing" OR abs:"subsidy" OR abs:"uplift" OR abs:"churn" OR abs:"customer lifetime value" OR abs:"treatment effect" OR abs:"causal" AND abs:"marketing" OR ti:"recommendation")',
    # stat.ML 覆盖推荐 + 因果推断/营销
    "stat.ML": '(abs:"recommendation" OR abs:"ranking" OR abs:"causal" OR abs:"treatment effect" OR abs:"uplift" OR abs:"A/B test")',
    # cs.AI 覆盖推荐 + 营销
    "cs.AI": '(abs:"recommendation system" OR abs:"recommender system" OR abs:"coupon" OR abs:"subsidy" OR abs:"pricing" OR abs:"marketing" AND abs:"machine learning")',
    # 营销增长专门搜索
    "econ.GN": '(abs:"coupon" OR abs:"pricing" OR abs:"subsidy" OR abs:"discount" OR abs:"promotion" OR abs:"incentive" OR abs:"uplift" OR abs:"causal" OR abs:"marketing")',
    # 新增：cs.CY (Computers and Society) 有时也发营销科技论文
    "cs.CY": '(abs:"marketing" OR abs:"coupon" OR abs:"promotion" OR abs:"pricing" OR abs:"incentive")',
}

# 营销增长补充关键词（在 cs.LG/cs.IR 中也会搜）
GROWTH_KEYWORDS = [
    "coupon allocation", "coupon distribution", "incentive optimization",
    "subsidy", "discount strategy", "dynamic pricing", "price optimization",
    "customer lifetime value", "LTV", "churn prediction", "user acquisition",
    "uplift modeling", "causal inference marketing", "treatment effect",
    "marketing attribution", "budget allocation", "promotion recommendation",
    "personalized pricing", "price elasticity",
]

LOOKBACK_HOURS = 48
MAX_RESULTS_PER_CATEGORY = 100
ARXIV_DELAY_SECONDS = 3.0

# ============================================================
# 论文分类体系
# ============================================================

PAPER_CATEGORIES = {
    "协同过滤": ["collaborative filtering", "matrix factorization", "neighborhood", "user-based", "item-based"],
    "序列推荐": ["sequential recommendation", "session-based", "next-item", "next-basket", "temporal dynamics"],
    "CTR预估": ["CTR", "click-through rate", "conversion rate", "CVR", "CVR prediction"],
    "图神经网络": ["graph neural network", "GNN", "graph attention", "graph convolution", "knowledge graph"],
    "大模型推荐": ["LLM", "large language model", "foundation model", "pre-train", "generative recommendation"],
    "多模态推荐": ["multimodal", "multi-modal", "visual", "textual", "cross-modal"],
    "强化学习推荐": ["reinforcement learning", "RL", "bandit", "contextual bandit", "policy gradient"],
    "召回与排序": ["retrieval", "ranking", "two-stage", "cascade", "re-ranking", "reranking", "matching"],
    "冷启动": ["cold start", "few-shot", "zero-shot", "new user", "new item"],
    "可解释性": ["explainable", "interpretability", "transparency", "explanation"],
    "公平性与去偏": ["fairness", "bias", "debiasing", "counterfactual", "fairness-aware"],
    "跨域推荐": ["cross-domain", "transfer learning", "multi-domain", "domain adaptation"],
    "联邦推荐": ["federated", "privacy", "distributed", "privacy-preserving"],
    # 营销增长 & 发券补贴
    "智能发券": ["coupon", "voucher", "coupon allocation", "coupon distribution", "coupon value", "coupon targeting"],
    "补贴策略": ["subsidy", "subsidies", "incentive", "budget allocation", "cost control"],
    "用户增长": ["user acquisition", "customer acquisition", "user retention", "churn", "LTV", "lifecycle"],
    "定价优化": ["pricing", "dynamic pricing", "price optimization", "discount", "price elasticity"],
    "营销归因": ["attribution", "marketing mix", "incrementality", "uplift", "causal effect"],
    "促销推荐": ["promotion", "promotion recommendation", "flash sale", "bundle", "group buying"],
}

FALLBACK_CATEGORY = "其他"

# ============================================================
# Gemini LLM 配置
# ============================================================

GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_TEMPERATURE = 0.3
GEMINI_MAX_TOKENS = 2048
GEMINI_RPM_LIMIT = 10
GEMINI_BATCH_SIZE = 5

SYSTEM_PROMPT = """你是一个推荐系统与营销增长领域的资深研究员。请分析以下学术论文，用中文输出结果。

要求：
1. 翻译中文标题（准确简洁）
2. 撰写中文摘要（保留核心技术方法、关键实验结果，200字以内）
3. 从预定义列表中选择最适合的分类（只能选一个）
4. 提炼核心贡献要点（2-4条，每条一句话，包含量化的实验结果如有）
5. 综合新颖性和实用性，给出评分（1-10分，其中10=范式级突破，7-9=重要进展，4-6=渐进改进，1-3=意义有限）
6. 一句话推荐理由（说明为什么值得阅读）
7. 适用的业务场景（如：短视频推荐、电商搜索、外卖配送、优惠券分配等）

可选的分类列表：协同过滤、序列推荐、CTR预估、图神经网络、大模型推荐、多模态推荐、强化学习推荐、召回与排序、冷启动、可解释性、公平性与去偏、跨域推荐、联邦推荐、智能发券、补贴策略、用户增长、定价优化、营销归因、促销推荐

请严格按以下JSON格式输出，不要加任何额外文字：
{
  "cn_title": "...",
  "cn_summary": "...",
  "category": "...",
  "highlights": ["...", "..."],
  "rating": 0.0,
  "one_sentence": "...",
  "applicable_scenarios": "..."
}
"""

# ============================================================
# 评分权重
# ============================================================

RATING_WEIGHTS = {
    "llm_score": 0.55,
    "citation_score": 0.15,
    "novelty_weight": 0.15,
    "recency_weight": 0.15,
}

# 引用归一化参数
CITATION_LOG_BASE = 1.2
MAX_CITATION_SCORE = 50

# ============================================================
# 输出配置
# ============================================================

PAPERS_PER_DIGEST = 20
FEISHU_MAX_PAPERS = 8

# ============================================================
# 飞书配置
# ============================================================

FEISHU_MESSAGE_CARD_TITLE = "📢 论文日报"
FEISHU_MESSAGE_CARD_COLOR = "#1890ff"
