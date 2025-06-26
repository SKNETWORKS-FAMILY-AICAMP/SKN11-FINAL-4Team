#!/usr/bin/env python3
"""
리그 오브 레전드 캐릭터 대사 추출기
텍스트 파일에서 대사만 추출하여 캐릭터별 JSON 리스트로 변환
"""

import json
import os
import re
from pathlib import Path
import argparse
import glob


class LOLDialogueExtractor:
    """LOL 캐릭터 대사를 추출하는 클래스"""
    
    def __init__(self):
        self.category_patterns = [
            r'^공격$',
            r'^이동$', 
            r'^선택$',
            r'^농담$',
            r'^도발$',
            r'^웃음$',
            r'^춤$',
            r'^죽음$',
            r'^부활$',
            r'^귀환$',
            r'^상점$',
            r'^스킬$',
            r'^궁극기$',
            r'^킬$',
            r'^어시스트$',
            r'^레벨업$',
            r'^승리$',
            r'^패배$',
            r'^특별한?\s*상호작용$',
            r'^특수\s*대사$',
            r'^.*스킨.*$',
            r'^.*상호작용.*$'
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
            if re.match(pattern, line, re.IGNORECASE):
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
        # 따옴표 제거 (앞뒤)
        dialogue = re.sub(r'^["\']|["\']$', '', dialogue)
        
        # 주석이나 설명 제거 (예: [2], (웃음), 등)
        dialogue = re.sub(r'\[[^\]]+\]', '', dialogue)
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
        if dialogue.strip() in ['...', '!', '?', '.', '-', '~', '헷!', '하!']:
            return False
        
        # 카테고리 헤더 제외
        if self.is_category_line(dialogue):
            return False
        
        # 순수 의성어나 의태어 제외
        meaningless_patterns = [
            r'^[ㅋㅎㅇㅏㅓㅗㅜㅡㅣ~!?.,\s]+$',  # ㅋㅋㅋ, 하하하 등
            r'^[듀빵야탕펑쾅후훼]+[!?~]*$',        # 의성어
            r'^[아어으음오우에이]+[!?~]*$'          # 감탄사
        ]
        
        for pattern in meaningless_patterns:
            if re.match(pattern, dialogue.strip()):
                return False
        
        return True
    
    def extract_character_name(self, filename: str) -> str:
        """
        파일명에서 캐릭터명 추출
        
        Args:
            filename (str): 파일명
        
        Returns:
            str: 캐릭터명
        """
        # 파일명 패턴: 캐릭터명_종류.txt
        base_name = os.path.splitext(filename)[0]
        
        # '_' 기준으로 분할하여 첫 번째 부분이 캐릭터명
        parts = base_name.split('_')
        if len(parts) > 0:
            return parts[0]
        
        return base_name
    
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
            
            print(f"  처리 중: {os.path.basename(file_path)}")
            
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
            
            print(f"    - 추출된 대사: {len(dialogues)}개")
            
        except Exception as e:
            print(f"    - 파일 읽기 실패: {e}")
        
        return dialogues
    
    def process_character_files(self, input_dir: str, output_dir: str = None):
        """
        캐릭터별로 모든 파일을 처리하여 통합된 대사 파일 생성
        
        Args:
            input_dir (str): 입력 디렉토리
            output_dir (str): 출력 디렉토리
        """
        if output_dir is None:
            output_dir = input_dir
        
        # 출력 디렉토리 생성
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 롤 데이터 폴더에서 파일 찾기
        data_dir = os.path.join(input_dir, "롤 데이터")
        if not os.path.exists(data_dir):
            print(f"롤 데이터 폴더를 찾을 수 없습니다: {data_dir}")
            return
        
        # 모든 텍스트 파일 찾기
        txt_files = glob.glob(os.path.join(data_dir, "*.txt"))
        
        if not txt_files:
            print(f"텍스트 파일을 찾을 수 없습니다: {data_dir}")
            return
        
        print(f"입력 디렉토리: {data_dir}")
        print(f"출력 디렉토리: {output_dir}")
        print(f"처리할 파일: {len(txt_files)}개")
        print("=" * 60)
        
        # 캐릭터별로 파일 그룹화
        character_files = {}
        for txt_file in txt_files:
            filename = os.path.basename(txt_file)
            character_name = self.extract_character_name(filename)
            
            if character_name not in character_files:
                character_files[character_name] = []
            character_files[character_name].append(txt_file)
        
        success_count = 0
        fail_count = 0
        
        # 캐릭터별로 처리
        for character_name, files in character_files.items():
            try:
                print(f"\n=== {character_name.upper()} 캐릭터 처리 ===")
                
                all_dialogues = []
                
                # 해당 캐릭터의 모든 파일에서 대사 추출
                for file_path in files:
                    dialogues = self.extract_dialogues_from_file(file_path)
                    all_dialogues.extend(dialogues)
                
                # 중복 제거
                unique_dialogues = []
                for dialogue in all_dialogues:
                    if dialogue not in unique_dialogues:
                        unique_dialogues.append(dialogue)
                
                print(f"  총 {len(unique_dialogues)}개의 고유한 대사 추출")
                
                # JSON 파일로 저장
                output_file = os.path.join(output_dir, f"{character_name}_dialogue_array.json")
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(unique_dialogues, f, ensure_ascii=False, indent=2)
                
                print(f"  저장 완료: {output_file}")
                
                # 미리보기
                print(f"\n📝 {character_name} 대사 미리보기 (처음 5개):")
                for i, dialogue in enumerate(unique_dialogues[:5], 1):
                    preview = dialogue[:60] + "..." if len(dialogue) > 60 else dialogue
                    print(f"    {i}. {preview}")
                
                success_count += 1
                
            except Exception as e:
                print(f"캐릭터 처리 중 오류 ({character_name}): {e}")
                fail_count += 1
        
        print("\n" + "=" * 60)
        print(f"처리 완료 - 성공: {success_count}개 캐릭터, 실패: {fail_count}개 캐릭터")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='리그 오브 레전드 캐릭터 대사 추출기')
    parser.add_argument('--input', '-i', default='.', help='입력 디렉토리 (기본값: 현재 디렉토리)')
    parser.add_argument('--output', '-o', help='출력 디렉토리 (기본값: 입력 디렉토리)')
    
    args = parser.parse_args()
    
    extractor = LOLDialogueExtractor()
    
    input_dir = os.path.abspath(args.input)
    output_dir = os.path.abspath(args.output) if args.output else input_dir
    
    extractor.process_character_files(input_dir, output_dir)


def show_usage():
    """사용법 출력"""
    print("=== 리그 오브 레전드 캐릭터 대사 추출기 ===")
    print("\n기능:")
    print("  - LOL 캐릭터 대사 텍스트 파일에서 순수 대사만 추출")
    print("  - 캐릭터별로 모든 파일을 통합하여 하나의 JSON 파일로 생성")
    print("  - 카테고리 헤더 제거 (공격, 이동, 선택 등)")
    print("  - 주석 및 설명 제거 ([숫자], (설명) 등)")
    print("  - 5글자 이하 및 의미없는 대사 제거")
    print("  - / 기호를 줄바꿈으로 처리하여 개별 대사로 분할")
    print("  - 중복 대사 제거")
    print("\n지원하는 캐릭터:")
    print("  - 바이 (바이_게임대사.txt, 바이_단편소설1.txt, 등)")
    print("  - 제이스 (제이스_게임대사.txt, 제이스_단편소설.txt)")
    print("  - 징크스 (징크스_게임대사.txt, 징크스_단편소설.txt)")
    print("  - 케이틀린 (케이틀린_게임대사.txt, 케이틀린_단편소설1.txt, 등)")
    print("\n사용법:")
    print("   python extract_lol_dialogues.py")
    print("   python extract_lol_dialogues.py -i ./lol -o ./output")
    print("\n결과:")
    print("   각 캐릭터별로 [캐릭터명]_dialogue_array.json 파일 생성")
    print("   예: 바이_dialogue_array.json, 징크스_dialogue_array.json")


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