def clean_response(response: str, influencer_name: str) -> str:
    """응답 후처리"""
    # 기본 정리
    response = response.strip()
    
    # 특수 토큰 제거
    special_tokens = [
        "<|im_end|>", "<|endoftext|>", "[/INST]", "</s>", 
        "<|eot_id|>", "[|Human|]", "[|Assistant|]", "[|System|]"
    ]
    
    for token in special_tokens:
        response = response.replace(token, "")
    
    # 인플루언서 이름 뒤의 콜론 제거
    if response.startswith(f"{influencer_name}:"):
        response = response[len(f"{influencer_name}:"):].strip()
    
    # 너무 길면 자르기
    if len(response) > 300:
        response = response[:300] + "..."
    
    # 빈 응답인 경우 기본 응답 제공
    if not response.strip():
        response = f"안녕하세요! {influencer_name}입니다! 😊 메시지 감사해요!"
    
    return response
