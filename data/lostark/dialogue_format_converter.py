#!/usr/bin/env python3
"""
로스트아크 캐릭터 대사 파일 통일 변환기
다양한 형태의 텍스트 파일들을 aman_dialogue_array.json과 동일한 형태로 변환
"""

import json
import os
import re
import glob
from pathlib import Path
from typing import List, Dict, Any, Union
import argparse


class DialogueFormatConverter:
    """다양한 형태의 대사 파일을 통일된 JSON 배열 형태로 변환하는 클래스"""
    
    def __init__(self):
        self.supported_formats = {
            'clova_json': self._process_clova_json,
            'markdown_txt': self._process_markdown_txt,
            'simple_txt': self._process_simple_txt,
            'numbered_txt': self._process_numbered_txt,
            'json_array': self._process_json_array
        }
    
    def detect_format(self, file_path: str) -> str:
        """파일 형태를 자동으로 감지"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            # JSON 파일인지 확인
            if file_path.endswith('.json'):
                try:
                    data = json.loads(content)
                    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], str):
                        return 'json_array'
                    elif isinstance(data, dict) and 'segments' in data:
                        return 'clova_json'
                except:
                    pass
            
            # 텍스트 파일 형태 분석
            if file_path.endswith('.txt'):
                lines = content.split('\n')
                
                # 마크다운 형태 확인 (##, **, 등이 있는 경우)
                if any(line.strip().startswith('#') or '**' in line for line in lines[:10]):
                    return 'markdown_txt'
                
                # 숫자 리스트 형태 확인 (1., 2., 등이 있는 경우)
                numbered_pattern = re.compile(r'^\d+\.\s+')
                if sum(1 for line in lines[:10] if numbered_pattern.match(line.strip())) > 2:
                    return 'numbered_txt'
                
                return 'simple_txt'
            
            return 'unknown'
            
        except Exception as e:
            print(f"파일 형태 감지 실패 ({file_path}): {e}")
            return 'unknown'
    
    def _process_clova_json(self, file_path: str) -> List[str]:
        """Clova STT JSON 파일에서 대사 추출"""
        dialogues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if 'segments' in data:
                for segment in data['segments']:
                    # textEdited가 있으면 우선 사용, 없으면 text 사용
                    text = segment.get('textEdited', segment.get('text', '')).strip()
                    if text and text not in dialogues:
                        dialogues.append(text)
            
            # segments가 없으면 전체 text에서 추출 시도
            elif 'text' in data:
                text = data['text'].strip()
                if text:
                    # 문장 단위로 분할
                    sentences = re.split(r'[.!?]\s+', text)
                    for sentence in sentences:
                        sentence = sentence.strip()
                        if sentence and sentence not in dialogues:
                            dialogues.append(sentence)
            
        except Exception as e:
            print(f"Clova JSON 처리 실패 ({file_path}): {e}")
        
        return dialogues
    
    def _process_markdown_txt(self, file_path: str) -> List[str]:
        """마크다운 형태의 텍스트 파일에서 대사 추출"""
        dialogues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            
            for line in lines:
                line = line.strip()
                
                # 마크다운 문법 제거
                line = re.sub(r'^#+\s*', '', line)  # 헤더 제거
                line = re.sub(r'\*\*([^*]+)\*\*', r'\1', line)  # 볼드 제거
                line = re.sub(r'\*([^*]+)\*', r'\1', line)  # 이탤릭 제거
                
                # 대화 패턴 추출 (예: "아만": "대사내용")
                dialogue_pattern = r'["\"]([^"\"]+)["\"]'
                matches = re.findall(dialogue_pattern, line)
                
                for match in matches:
                    text = match.strip()
                    if text and len(text) > 2 and text not in dialogues:
                        dialogues.append(text)
                
                # 일반 텍스트에서도 의미있는 문장 추출
                if line and not line.startswith('#') and ':' not in line[:10] and len(line) > 5:
                    if line not in dialogues:
                        dialogues.append(line)
        
        except Exception as e:
            print(f"마크다운 텍스트 처리 실패 ({file_path}): {e}")
        
        return dialogues
    
    def _process_simple_txt(self, file_path: str) -> List[str]:
        """단순 텍스트 파일에서 대사 추출"""
        dialogues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 줄 단위로 분할
            lines = content.split('\n')
            
            for line in lines:
                line = line.strip()
                
                # 빈 줄이나 너무 짧은 줄 제외
                if not line or len(line) < 3:
                    continue
                
                # 특수 문자로 시작하는 메타데이터 제외
                if line.startswith(('#', '//', '<!--', '*', '-')):
                    continue
                
                if line not in dialogues:
                    dialogues.append(line)
        
        except Exception as e:
            print(f"단순 텍스트 처리 실패 ({file_path}): {e}")
        
        return dialogues
    
    def _process_numbered_txt(self, file_path: str) -> List[str]:
        """숫자 리스트 형태의 텍스트 파일에서 대사 추출"""
        dialogues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            
            for line in lines:
                line = line.strip()
                
                # 숫자와 점으로 시작하는 패턴 제거 (예: "1. ", "10. ")
                cleaned_line = re.sub(r'^\d+\.\s*', '', line)
                
                if cleaned_line and len(cleaned_line) > 2 and cleaned_line not in dialogues:
                    dialogues.append(cleaned_line)
        
        except Exception as e:
            print(f"숫자 리스트 텍스트 처리 실패 ({file_path}): {e}")
        
        return dialogues
    
    def _process_json_array(self, file_path: str) -> List[str]:
        """이미 JSON 배열 형태인 파일 처리"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                return [str(item).strip() for item in data if str(item).strip()]
            
        except Exception as e:
            print(f"JSON 배열 처리 실패 ({file_path}): {e}")
        
        return []
    
    def convert_file(self, input_path: str, output_path: str = None) -> bool:
        """단일 파일을 변환"""
        format_type = self.detect_format(input_path)
        
        if format_type == 'unknown':
            print(f"지원하지 않는 파일 형태: {input_path}")
            return False
        
        print(f"처리 중: {os.path.basename(input_path)} (형태: {format_type})")
        
        # 대사 추출
        dialogues = self.supported_formats[format_type](input_path)
        
        if not dialogues:
            print(f"대사를 찾을 수 없음: {input_path}")
            return False
        
        # 출력 파일 경로 결정
        if output_path is None:
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_dir = os.path.dirname(input_path)
            output_path = os.path.join(output_dir, f"{base_name}_converted.json")
        
        # JSON 배열로 저장
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(dialogues, f, ensure_ascii=False, indent=2)
            
            print(f"변환 완료: {output_path} ({len(dialogues)}개 대사)")
            return True
            
        except Exception as e:
            print(f"파일 저장 실패 ({output_path}): {e}")
            return False
    
    def convert_directory(self, input_dir: str, output_dir: str = None, pattern: str = "*"):
        """디렉토리 내 모든 파일 변환"""
        if output_dir is None:
            output_dir = os.path.join(input_dir, "converted")
        
        # 출력 디렉토리 생성
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 파일 찾기
        search_patterns = [
            os.path.join(input_dir, f"{pattern}.txt"),
            os.path.join(input_dir, f"{pattern}.json"),
            os.path.join(input_dir, "**", f"{pattern}.txt"),
            os.path.join(input_dir, "**", f"{pattern}.json")
        ]
        
        all_files = []
        for pattern_path in search_patterns:
            all_files.extend(glob.glob(pattern_path, recursive=True))
        
        # 중복 제거
        all_files = list(set(all_files))
        
        if not all_files:
            print(f"변환할 파일을 찾을 수 없습니다: {input_dir}")
            return
        
        print(f"총 {len(all_files)}개 파일을 변환합니다.")
        print(f"입력 디렉토리: {input_dir}")
        print(f"출력 디렉토리: {output_dir}")
        print("-" * 60)
        
        success_count = 0
        fail_count = 0
        
        for file_path in all_files:
            try:
                # 출력 파일명 생성
                rel_path = os.path.relpath(file_path, input_dir)
                base_name = os.path.splitext(rel_path)[0]
                output_file = os.path.join(output_dir, f"{base_name}_converted.json")
                
                # 출력 파일의 디렉토리 생성
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
                
                if self.convert_file(file_path, output_file):
                    success_count += 1
                else:
                    fail_count += 1
                    
            except Exception as e:
                print(f"파일 처리 중 오류 ({file_path}): {e}")
                fail_count += 1
        
        print("\n" + "=" * 60)
        print(f"변환 완료 - 성공: {success_count}개, 실패: {fail_count}개")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='로스트아크 캐릭터 대사 파일 통일 변환기')
    parser.add_argument('input', help='입력 파일 또는 디렉토리 경로')
    parser.add_argument('-o', '--output', help='출력 파일 또는 디렉토리 경로')
    parser.add_argument('-p', '--pattern', default='*', help='파일 검색 패턴 (디렉토리 모드에서만 사용)')
    parser.add_argument('--single', action='store_true', help='단일 파일 모드')
    
    args = parser.parse_args()
    
    converter = DialogueFormatConverter()
    
    if args.single or os.path.isfile(args.input):
        # 단일 파일 변환
        success = converter.convert_file(args.input, args.output)
        if not success:
            exit(1)
    else:
        # 디렉토리 변환
        converter.convert_directory(args.input, args.output, args.pattern)


def show_usage():
    """사용법 출력"""
    print("=== 로스트아크 캐릭터 대사 파일 통일 변환기 ===")
    print("\n지원하는 파일 형태:")
    print("  - Clova STT JSON (segments 포함)")
    print("  - 마크다운 텍스트 파일 (대화 형태)")
    print("  - 단순 텍스트 파일")
    print("  - 숫자 리스트 텍스트 파일")
    print("  - JSON 배열 파일")
    print("\n사용법:")
    print("1. 단일 파일 변환:")
    print("   python dialogue_format_converter.py <파일경로> [-o <출력파일>]")
    print()
    print("2. 디렉토리 일괄 변환:")
    print("   python dialogue_format_converter.py <디렉토리경로> [-o <출력디렉토리>] [-p <패턴>]")
    print()
    print("예시:")
    print("   python dialogue_format_converter.py ninav_dialogue.txt")
    print("   python dialogue_format_converter.py ./character_data -o ./converted")
    print("   python dialogue_format_converter.py ./lostark -p silian*")
    print()
    print("※ 모든 파일은 aman_dialogue_array.json과 동일한 JSON 배열 형태로 변환됩니다.")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) == 1:
        show_usage()
    elif len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', 'help']:
        show_usage()
    else:
        main()