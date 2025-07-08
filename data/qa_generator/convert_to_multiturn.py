import json
import csv
from pathlib import Path
from collections import defaultdict

def csv_to_multiturn_format(csv_file_path, output_file_path):
    """CSV 파일에서 멀티턴 대화 형태로 변환"""
    with open(csv_file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        data = list(reader)
    
    # 대화ID별로 그룹화하고 A, B 발화자만 추출
    conversations = defaultdict(list)
    current_conversation = None
    
    for item in data:
        speaker = item.get('발화자')
        utterance = item.get('발화', '').strip()
        conv_id = item.get('﻿대화ID', '').strip() or item.get('대화ID', '').strip()
        
        if speaker in ['A', 'B'] and utterance:
            # 새로운 대화가 시작되면 대화ID 업데이트
            if conv_id:
                current_conversation = conv_id
            
            # 현재 대화 ID가 있는 경우 해당 대화에 추가
            if current_conversation:
                conversations[current_conversation].append({
                    'speaker': speaker,
                    'utterance': utterance,
                    'utterance_num': int(item.get('발화 번호', 0))
                })
    
    # 멀티턴 대화 데이터셋 생성
    multiturn_dataset = []
    
    for conv_id, messages in conversations.items():
        if len(messages) < 2:  # 최소 2개 메시지가 있어야 대화
            continue
        
        # 발화 번호로 정렬
        messages.sort(key=lambda x: x['utterance_num'])
        
        # 누적 컨텍스트 형태로 변환
        conversation_history = []
        
        for i in range(len(messages) - 1):
            current_msg = messages[i]
            next_msg = messages[i + 1]
            
            # 역할 일관성을 위해 A를 user, B를 assistant로 고정
            if current_msg['speaker'] == 'A':
                user_msg = current_msg['utterance']
                assistant_msg = next_msg['utterance'] if next_msg['speaker'] == 'B' else None
            else:
                user_msg = next_msg['utterance'] if next_msg['speaker'] == 'A' else None
                assistant_msg = current_msg['utterance']
            
            if user_msg and assistant_msg:
                # 현재까지의 대화 이력을 포함한 턴 생성
                turn_data = {
                    "conversation_id": conv_id,
                    "turn": i + 1,
                    "conversation_history": conversation_history.copy(),
                    "user": user_msg,
                    "assistant": assistant_msg
                }
                
                multiturn_dataset.append(turn_data)
                
                # 대화 이력에 현재 턴 추가
                conversation_history.append({
                    "user": user_msg,
                    "assistant": assistant_msg
                })
    
    # 결과 저장
    with open(output_file_path, 'w', encoding='utf-8') as f:
        json.dump(multiturn_dataset, f, ensure_ascii=False, indent=2)
    
    print(f"멀티턴 변환 완료: {len(multiturn_dataset)}개 턴 -> {output_file_path}")
    return len(multiturn_dataset)

def csv_to_conversation_sessions(csv_file_path, output_file_path):
    """CSV 파일에서 전체 대화 세션 형태로 변환"""
    with open(csv_file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        data = list(reader)
    
    # 대화ID별로 그룹화
    conversations = defaultdict(list)
    current_conversation = None
    
    for item in data:
        speaker = item.get('발화자')
        utterance = item.get('발화', '').strip()
        conv_id = item.get('﻿대화ID', '').strip() or item.get('대화ID', '').strip()
        
        if speaker in ['A', 'B'] and utterance:
            if conv_id:
                current_conversation = conv_id
            
            if current_conversation:
                conversations[current_conversation].append({
                    'speaker': speaker,
                    'utterance': utterance,
                    'utterance_num': int(item.get('발화 번호', 0))
                })
    
    # 전체 대화 세션 형태로 변환
    conversation_sessions = []
    
    for conv_id, messages in conversations.items():
        if len(messages) < 2:
            continue
        
        # 발화 번호로 정렬
        messages.sort(key=lambda x: x['utterance_num'])
        
        # messages 배열 생성 (A를 user, B를 assistant로)
        session_messages = []
        for msg in messages:
            role = "user" if msg['speaker'] == 'A' else "assistant"
            session_messages.append({
                "role": role,
                "content": msg['utterance']
            })
        
        conversation_session = {
            "conversation_id": conv_id,
            "messages": session_messages
        }
        
        conversation_sessions.append(conversation_session)
    
    # 결과 저장
    with open(output_file_path, 'w', encoding='utf-8') as f:
        json.dump(conversation_sessions, f, ensure_ascii=False, indent=2)
    
    print(f"대화 세션 변환 완료: {len(conversation_sessions)}개 세션 -> {output_file_path}")
    return len(conversation_sessions)

def process_all_csv_files():
    """모든 CSV 파일을 멀티턴 형태로 변환"""
    base_dir = Path("sns_data")
    
    for folder in ["학습 데이터", "검증 데이터"]:
        folder_path = base_dir / folder
        
        # 두 가지 형태로 출력
        multiturn_output_folder = base_dir / f"{folder}_multiturn_context"
        session_output_folder = base_dir / f"{folder}_conversation_sessions"
        
        multiturn_output_folder.mkdir(exist_ok=True)
        session_output_folder.mkdir(exist_ok=True)
        
        total_turns = 0
        total_sessions = 0
        
        for csv_file in folder_path.glob("*.csv"):
            # 누적 컨텍스트 형태
            multiturn_output = multiturn_output_folder / f"{csv_file.stem}_multiturn.json"
            turns = csv_to_multiturn_format(csv_file, multiturn_output)
            total_turns += turns
            
            # 대화 세션 형태
            session_output = session_output_folder / f"{csv_file.stem}_sessions.json"
            sessions = csv_to_conversation_sessions(csv_file, session_output)
            total_sessions += sessions
        
        print(f"\n{folder} 요약:")
        print(f"- 누적 컨텍스트: {total_turns}개 턴")
        print(f"- 대화 세션: {total_sessions}개 세션")

if __name__ == "__main__":
    process_all_csv_files()
    print("\n모든 CSV 파일이 멀티턴 형태로 변환되었습니다!")