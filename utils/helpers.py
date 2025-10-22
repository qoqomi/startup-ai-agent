def extract_industry(query: str) -> str:
    """쿼리에서 산업 추출"""
    if "핀테크" in query.lower() or "금융" in query.lower():
        return "핀테크"
    if "헬스케어" in query.lower() or "의료" in query.lower():
        return "헬스케어"
    if "AI" in query or "인공지능" in query:
        return "AI"
    return "스타트업"

def extract_company_name(text: str) -> str:
    """텍스트에서 기업명 추출"""
    return text.split()[0] if text else ""
