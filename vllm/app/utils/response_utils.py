def clean_response(response: str, influencer_name: str) -> str:
    """응답 후처리 (chat template 대응)"""
    # 기본 정리
    response = response.strip()
    
    # 특수 토큰 제거 (EXAONE 및 일반적인 토큰들)
    special_tokens = [
        "<|im_end|>", "<|endoftext|>", "[/INST]", "</s>", 
        "<|eot_id|>", "[|Human|]", "[|Assistant|]", "[|System|]",
        "<|end_of_text|>", "<eos>", "<pad>", "[PAD]", "[UNK]"
    ]
    
    for token in special_tokens:
        response = response.replace(token, "")
    
    # 인플루언서 이름 뒤의 콜론 제거 (여러 패턴 대응)
    patterns_to_remove = [
        f"{influencer_name}:",
        f"{influencer_name} :",
        f"**{influencer_name}:**",
        f"**{influencer_name}**:",
    ]
    
    for pattern in patterns_to_remove:
        if response.startswith(pattern):
            response = response[len(pattern):].strip()
            break
    
    # 마크다운 굵게 표시 제거
    response = response.replace("**", "")
    
    # 개행 정리 (연속된 개행을 하나로)
    import re
    response = re.sub(r'\n+', '\n', response)
    response = response.strip()
    
    # 너무 길면 자르기 (DM은 간결해야 함)
    if len(response) > 300:
        # 문장 단위로 자르기 시도
        sentences = response.split('. ')
        if len(sentences) > 1:
            truncated = ""
            for sentence in sentences:
                if len(truncated + sentence + ". ") <= 280:
                    truncated += sentence + ". "
                else:
                    break
            if truncated:
                response = truncated.strip()
            else:
                response = response[:280] + "..."
        else:
            response = response[:280] + "..."
    
    # 빈 응답인 경우 기본 응답 제공
    if not response.strip():
        response = f"안녕하세요! {influencer_name}입니다! 😊 메시지 감사해요!"
    
    return response
