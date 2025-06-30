#!/usr/bin/env python3
"""
Clova STT JSON 결과에서 대사만 추출하여 리스트로 변환하는 스크립트
니나브와 실리안의 Clova JSON 파일에서 정제된 대사만 추출
"""

import json
import os
from pathlib import Path
import argparse


def extract_dialogues_from_clova_json(file_path: str) -> list:
    """
    Clova STT JSON 파일에서 대사만 추출
    
    Args:
        file_path (str): Clova JSON 파일 경로
    
    Returns:
        list: 추출된 대사 리스트
    """
    dialogues = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"처리 중: {os.path.basename(file_path)}")
        
        # segments에서 대사 추출
        if 'segments' in data:
            for segment in data['segments']:
                # textEdited가 있으면 우선 사용 (사용자가 수정한 텍스트)
                if 'textEdited' in segment and segment['textEdited'].strip():
                    text = segment['textEdited'].strip()
                # textEdited가 없으면 원본 text 사용
                elif 'text' in segment and segment['text'].strip():
                    text = segment['text'].strip()
                else:
                    continue
                
                # 중복 제거 및 의미있는 대사만 추가
                if text and len(text) > 1 and text not in dialogues:
                    # 숫자만 있는 경우나 의미없는 짧은 텍스트 제외
                    if not text.isdigit() and not text in ['아', '어', '음', '으', '네', '예']:
                        dialogues.append(text)
            
            print(f"  - 총 {len(data['segments'])}개 세그먼트에서 {len(dialogues)}개 대사 추출")
        
        # segments가 없으면 전체 text에서 추출 시도
        elif 'text' in data:
            full_text = data['text'].strip()
            if full_text:
                # 문장 부호로 분할하여 개별 대사로 만들기
                import re
                sentences = re.split(r'[.!?]\s+', full_text)
                for sentence in sentences:
                    sentence = sentence.strip()
                    if sentence and len(sentence) > 2 and sentence not in dialogues:
                        dialogues.append(sentence)
                
                print(f"  - 전체 텍스트에서 {len(dialogues)}개 대사 추출")
        
        else:
            print(f"  - 경고: segments와 text 모두 없음")
        
    except Exception as e:
        print(f"오류 발생 ({file_path}): {e}")
    
    return dialogues


def process_character_files(character_name: str, input_dir: str, output_dir: str = None):
    """
    특정 캐릭터의 모든 Clova JSON 파일을 처리
    
    Args:
        character_name (str): 캐릭터 이름 (ninav, silian)
        input_dir (str): 입력 디렉토리
        output_dir (str): 출력 디렉토리
    """
    if output_dir is None:
        output_dir = input_dir
    
    # 캐릭터별 폴더 찾기
    character_folder = None
    for folder_name in os.listdir(input_dir):
        if character_name.lower() in folder_name.lower() and 'character_text' in folder_name:
            character_folder = os.path.join(input_dir, folder_name)
            break
    
    if not character_folder or not os.path.exists(character_folder):
        print(f"{character_name} 캐릭터 폴더를 찾을 수 없습니다.")
        return
    
    print(f"\n=== {character_name.upper()} 캐릭터 대사 추출 ===")
    print(f"입력 폴더: {character_folder}")
    
    # JSON 파일 찾기
    json_files = []
    for file_name in os.listdir(character_folder):
        if file_name.endswith('.txt') and 'dialogue' in file_name:
            # .txt 파일이지만 실제로는 JSON 형태인 파일들
            file_path = os.path.join(character_folder, file_name)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content.startswith('{') and '"segments"' in content:
                        json_files.append(file_path)
            except:
                continue
    
    if not json_files:
        print(f"  - Clova JSON 파일을 찾을 수 없습니다.")
        return
    
    # 모든 대사를 하나의 리스트로 수집
    all_dialogues = []
    
    for json_file in json_files:
        dialogues = extract_dialogues_from_clova_json(json_file)
        all_dialogues.extend(dialogues)
    
    # 중복 제거
    unique_dialogues = []
    for dialogue in all_dialogues:
        if dialogue not in unique_dialogues:
            unique_dialogues.append(dialogue)
    
    print(f"  - 총 {len(unique_dialogues)}개의 고유한 대사 추출 완료")
    
    # 출력 파일 저장
    output_file = os.path.join(output_dir, f"{character_name}_dialogue_array.json")
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(unique_dialogues, f, ensure_ascii=False, indent=2)
        
        print(f"  - 저장 완료: {output_file}")
        
        # 결과 미리보기
        print(f"\n📝 {character_name} 대사 미리보기 (처음 5개):")
        for i, dialogue in enumerate(unique_dialogues[:5], 1):
            preview = dialogue[:50] + "..." if len(dialogue) > 50 else dialogue
            print(f"  {i}. {preview}")
        
        return unique_dialogues
        
    except Exception as e:
        print(f"파일 저장 실패 ({output_file}): {e}")
        return None


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='Clova STT JSON에서 대사 추출')
    parser.add_argument('--character', choices=['ninav', 'silian', 'all'], 
                       default='all', help='처리할 캐릭터 선택')
    parser.add_argument('--input', default='.', help='입력 디렉토리')
    parser.add_argument('--output', help='출력 디렉토리 (기본값: 입력 디렉토리)')
    
    args = parser.parse_args()
    
    input_dir = os.path.abspath(args.input)
    output_dir = os.path.abspath(args.output) if args.output else input_dir
    
    print(f"입력 디렉토리: {input_dir}")
    print(f"출력 디렉토리: {output_dir}")
    
    # 출력 디렉토리 생성
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    success_count = 0
    
    if args.character in ['ninav', 'all']:
        result = process_character_files('ninav', input_dir, output_dir)
        if result:
            success_count += 1
    
    if args.character in ['silian', 'all']:
        result = process_character_files('silian', input_dir, output_dir)
        if result:
            success_count += 1
    
    print(f"\n🎉 처리 완료: {success_count}개 캐릭터")


if __name__ == "__main__":
    main()