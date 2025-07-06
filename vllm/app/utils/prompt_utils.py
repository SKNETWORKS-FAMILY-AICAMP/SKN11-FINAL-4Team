def create_chat_prompt(user_message: str, system_message: str, influencer_name: str) -> str:
    """채팅 프롬프트 생성 (EXAONE 스타일)"""
    # EXAONE 모델에 최적화된 프롬프트 템플릿
    prompt = f"""[|System|] {system_message}

[|Human|] {user_message}

[|Assistant|] {influencer_name}: """
    
    return prompt
