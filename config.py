import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# 설정
CHROMA_DB_PATH = "./data/chroma_db"
CACHE_PATH = "./data/cache"
OUTPUT_PATH = "./outputs/reports"

# 평가 가중치
SCORECARD_WEIGHTS = {
    "경영진": 0.30,
    "시장": 0.25,
    "제품": 0.15,
    "경쟁": 0.10,
    "판매": 0.10,
    "투자": 0.05,
    "기타": 0.05,
}

# 검색 설정
MAX_SEARCH_RESULTS = 10
RERANK_TOP_K = 5
