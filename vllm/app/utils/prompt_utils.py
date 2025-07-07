def create_chat_prompt(user_message: str, system_message: str, influencer_name: str) -> str:
    """채팅 프롬프트 생성 (토크나이저 chat template 필수 사용)"""
    from app.core import tokenizer
    
    # 토크나이저가 초기화되지 않은 경우 에러
    if not tokenizer:
        raise RuntimeError("토크나이저가 초기화되지 않았습니다. 서버를 다시 시작해주세요.")
    
    # chat template이 없는 경우 에러  
    if not hasattr(tokenizer, 'apply_chat_template') or tokenizer.chat_template is None:
        raise RuntimeError("토크나이저에 chat template이 없습니다. EXAONE 모델을 사용해주세요.")
    
    try:
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
        
        # 토크나이저의 chat template 사용
        prompt = tokenizer.apply_chat_template(
            messages, 
            tokenize=False, 
            add_generation_prompt=True
        )
        
        return prompt
        
    except Exception as e:
        # chat template 적용 실패 시 에러 발생
        raise RuntimeError(f"Chat template 적용 실패: {e}")
