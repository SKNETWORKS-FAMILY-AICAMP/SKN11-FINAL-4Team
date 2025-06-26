#!/usr/bin/env python3
"""
오버워치 캐릭터 대사 추출기
텍스트 파일에서 대사만 추출하여 리스트 형태로 변환
"""

import json
import os
import re
from pathlib import Path
import argparse
import glob


class OverwatchDialogueExtractor:
    """오버워치 캐릭터 대사를 추출하는 클래스"""
    
    def __init__(self):
        self.category_patterns = [
            r'^영웅 선택$',
            r'^영웅 변경$', 
            r'^게임 준비$',
            r'^게임 시작$',
            r'^이동$',
            r'^공격$',
            r'^궁극기$',
            r'^사망$',
            r'^부활$',
            r'^승리$',
            r'^패배$',
            r'^기타$'
        ]
    
    def is_category_line(self, line: str) -> bool:
        """
        해당 줄이 카테고리 헤더인지 확인
        
        Args:
            line (str): 검사할 줄
        
        Returns:
            bool: 카테고리 헤더인지 여부
        """
        line = line.strip()
        for pattern in self.category_patterns:
            if re.match(pattern, line):
                return True
        return False
    
    def clean_dialogue(self, dialogue: str) -> str:
        """
        대사를 정제
        
        Args:
            dialogue (str): 원본 대사
        
        Returns:
            str: 정제된 대사
        """
        # 스킨 정보 제거 (예: <산타요정 스킨>, <T. 레이서·마하 T 스킨>)
        dialogue = re.sub(r'<[^>]+>\s*', '', dialogue)
        
        # 괄호 안의 부가 설명 제거 (예: (웃음), (기타 연주 흉내))
        dialogue = re.sub(r'\([^)]+\)', '', dialogue)
        
        # / 를 줄바꿈으로 처리
        dialogue = dialogue.replace('/', '\n')
        
        # 여러 공백을 하나로 정리
        dialogue = re.sub(r'\s+', ' ', dialogue)
        
        # 앞뒤 공백 제거
        dialogue = dialogue.strip()
        
        return dialogue
    
    def is_valid_dialogue(self, dialogue: str) -> bool:
        """
        유효한 대사인지 확인
        
        Args:
            dialogue (str): 검사할 대사
        
        Returns:
            bool: 유효한 대사인지 여부
        """
        # 빈 문자열이나 5글자 이하 제외
        if not dialogue or len(dialogue.strip()) <= 5:
            return False
        
        # 특수문자만 있는 경우 제외
        if dialogue.strip() in ['...', '!', '?', '.', '-']:
            return False
        
        # 카테고리 헤더 제외
        if self.is_category_line(dialogue):
            return False
        
        return True
    
    def extract_dialogues_from_file(self, file_path: str) -> list:
        """
        텍스트 파일에서 대사 추출
        
        Args:
            file_path (str): 텍스트 파일 경로
        
        Returns:
            list: 추출된 대사 리스트
        """
        dialogues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            print(f"처리 중: {os.path.basename(file_path)}")
            print(f"  - 총 줄 수: {len(lines)}")
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                
                # 빈 줄 건너뛰기
                if not line:
                    continue
                
                # 카테고리 헤더 건너뛰기
                if self.is_category_line(line):
                    continue
                
                # 대사 정제
                cleaned_dialogue = self.clean_dialogue(line)
                
                # / 로 나뉜 대사들을 개별 처리
                if '\n' in cleaned_dialogue:
                    # 줄바꿈으로 분할된 여러 대사 처리
                    split_dialogues = cleaned_dialogue.split('\n')
                    for split_dialogue in split_dialogues:
                        split_dialogue = split_dialogue.strip()
                        if self.is_valid_dialogue(split_dialogue):
                            if split_dialogue not in dialogues:
                                dialogues.append(split_dialogue)
                else:
                    # 단일 대사 처리
                    if self.is_valid_dialogue(cleaned_dialogue):
                        if cleaned_dialogue not in dialogues:
                            dialogues.append(cleaned_dialogue)
            
            print(f"  - 추출된 대사: {len(dialogues)}개")
            
        except Exception as e:
            print(f"파일 읽기 실패 ({file_path}): {e}")
        
        return dialogues
    
    def extract_character_dialogues(self, file_path: str, output_path: str = None) -> bool:
        """
        캐릭터 대사 파일을 처리하여 JSON으로 저장
        
        Args:
            file_path (str): 입력 파일 경로
            output_path (str): 출력 파일 경로
        
        Returns:
            bool: 처리 성공 여부
        """
        # 출력 파일 경로 결정
        if output_path is None:
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            output_dir = os.path.dirname(file_path)
            output_path = os.path.join(output_dir, f"{base_name}_dialogue_array.json")
        
        # 대사 추출
        dialogues = self.extract_dialogues_from_file(file_path)
        
        if not dialogues:
            print(f"추출할 대사가 없습니다: {file_path}")
            return False
        
        # JSON 파일로 저장
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(dialogues, f, ensure_ascii=False, indent=2)
            
            print(f"저장 완료: {output_path}")
            
            # 결과 미리보기
            character_name = os.path.splitext(os.path.basename(file_path))[0].upper()
            print(f"\n📝 {character_name} 대사 미리보기 (처음 5개):")
            for i, dialogue in enumerate(dialogues[:5], 1):
                preview = dialogue[:60] + "..." if len(dialogue) > 60 else dialogue
                print(f"  {i}. {preview}")
            
            return True
            
        except Exception as e:
            print(f"파일 저장 실패 ({output_path}): {e}")
            return False
    
    def process_all_characters(self, input_dir: str, output_dir: str = None):
        """
        디렉토리 내 모든 캐릭터 파일 처리
        
        Args:
            input_dir (str): 입력 디렉토리
            output_dir (str): 출력 디렉토리
        """
        if output_dir is None:
            output_dir = input_dir
        
        # 출력 디렉토리 생성
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 텍스트 파일 찾기
        txt_files = glob.glob(os.path.join(input_dir, "*.txt"))
        
        if not txt_files:
            print(f"텍스트 파일을 찾을 수 없습니다: {input_dir}")
            return
        
        print(f"입력 디렉토리: {input_dir}")
        print(f"출력 디렉토리: {output_dir}")
        print(f"처리할 파일: {len(txt_files)}개")
        print("=" * 60)
        
        success_count = 0
        fail_count = 0
        
        for txt_file in txt_files:
            try:
                # 출력 파일명 생성
                base_name = os.path.splitext(os.path.basename(txt_file))[0]
                output_file = os.path.join(output_dir, f"{base_name}_dialogue_array.json")
                
                if self.extract_character_dialogues(txt_file, output_file):
                    success_count += 1
                else:
                    fail_count += 1
                
                print()  # 빈 줄로 구분
                    
            except Exception as e:
                print(f"파일 처리 중 오류 ({txt_file}): {e}")
                fail_count += 1
        
        print("=" * 60)
        print(f"처리 완료 - 성공: {success_count}개, 실패: {fail_count}개")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='오버워치 캐릭터 대사 추출기')
    parser.add_argument('--input', '-i', default='.', help='입력 디렉토리 또는 파일')
    parser.add_argument('--output', '-o', help='출력 디렉토리 또는 파일')
    parser.add_argument('--character', '-c', help='특정 캐릭터 파일만 처리')
    
    args = parser.parse_args()
    
    extractor = OverwatchDialogueExtractor()
    
    if args.character:
        # 특정 캐릭터 파일 처리
        input_path = os.path.abspath(args.character)
        output_path = None
        
        if args.output:
            if os.path.isdir(args.output):
                base_name = os.path.splitext(os.path.basename(input_path))[0]
                output_path = os.path.join(args.output, f"{base_name}_dialogue_array.json")
            else:
                output_path = os.path.abspath(args.output)
        
        success = extractor.extract_character_dialogues(input_path, output_path)
        if not success:
            exit(1)
    
    elif os.path.isfile(args.input):
        # 단일 파일 처리
        input_path = os.path.abspath(args.input)
        output_path = None
        
        if args.output:
            output_path = os.path.abspath(args.output)
        
        success = extractor.extract_character_dialogues(input_path, output_path)
        if not success:
            exit(1)
    
    else:
        # 디렉토리 내 모든 파일 처리
        input_dir = os.path.abspath(args.input)
        output_dir = os.path.abspath(args.output) if args.output else input_dir
        
        extractor.process_all_characters(input_dir, output_dir)


def show_usage():
    """사용법 출력"""
    print("=== 오버워치 캐릭터 대사 추출기 ===")
    print("\n기능:")
    print("  - 오버워치 캐릭터 대사 텍스트 파일에서 순수 대사만 추출")
    print("  - 카테고리 헤더 제거 (영웅 선택, 게임 준비 등)")
    print("  - 스킨 정보 및 부가 설명 제거")
    print("  - 중복 대사 제거")
    print("  - JSON 배열 형태로 저장")
    print("\n사용법:")
    print("1. 디렉토리 내 모든 파일 처리:")
    print("   python extract_overwatch_dialogues.py")
    print("   python extract_overwatch_dialogues.py -i ./overwatch -o ./output")
    print()
    print("2. 특정 파일 처리:")
    print("   python extract_overwatch_dialogues.py -c tracer.txt")
    print("   python extract_overwatch_dialogues.py -i junkrat.txt -o junkrat_dialogues.json")
    print()
    print("예시:")
    print("   python extract_overwatch_dialogues.py")
    print("   python extract_overwatch_dialogues.py --input /path/to/overwatch")
    print("   python extract_overwatch_dialogues.py --character tracer.txt --output ./output")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) == 1:
        show_usage()
        print("\n기본 실행 중...")
        main()
    elif len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', 'help']:
        show_usage()
    else:
        main()