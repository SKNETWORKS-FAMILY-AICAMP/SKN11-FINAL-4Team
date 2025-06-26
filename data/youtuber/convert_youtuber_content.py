#!/usr/bin/env python3
"""
YouTube 크리에이터 데이터 변환기
ITSub_data.json과 JUYEON_data.json 파일의 content를 list 형태로 변환
"""

import json
import os
import re
from pathlib import Path
import argparse


class YoutuberContentConverter:
    """유튜버 데이터 파일의 content를 리스트로 변환하는 클래스"""
    
    def __init__(self):
        self.supported_files = ['ITSub_data.json', 'JUYEON_data.json']
    
    def extract_content_list(self, file_path: str) -> list:
        """
        JSON 파일에서 모든 content 값을 리스트로 추출
        
        Args:
            file_path (str): 입력 JSON 파일 경로
        
        Returns:
            list: 추출된 content 리스트
        """
        content_list = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            file_name = os.path.basename(file_path)
            print(f"\n처리 중: {file_name}")
            
            # 메타데이터 확인
            if 'metadata' in data:
                total_paragraphs = data['metadata'].get('total_paragraphs', 0)
                print(f"  - 총 단락 수: {total_paragraphs}")
            
            # files 섹션에서 content 추출
            if 'files' in data:
                for file_key, file_data in data['files'].items():
                    print(f"  - 파일: {file_key}")
                    
                    if 'paragraphs' in file_data:
                        paragraphs = file_data['paragraphs']
                        print(f"    단락 수: {len(paragraphs)}")
                        
                        for paragraph in paragraphs:
                            if 'content' in paragraph:
                                content = paragraph['content'].strip()
                                
                                # 의미있는 content만 추가
                                if self._is_valid_content(content):
                                    # 중복 제거
                                    if content not in content_list:
                                        content_list.append(content)
            
            print(f"  - 추출된 고유 content: {len(content_list)}개")
            
        except Exception as e:
            print(f"파일 처리 실패 ({file_path}): {e}")
        
        return content_list
    
    def _is_valid_content(self, content: str) -> bool:
        """
        content가 유효한지 판단
        
        Args:
            content (str): 검사할 content
        
        Returns:
            bool: 유효한 content인지 여부
        """
        # 빈 문자열이나 너무 짧은 경우 제외
        if not content or len(content.strip()) < 2:
            return False
        
        # URL만 있는 경우 제외
        if content.startswith('http') and len(content.split()) == 1:
            return False
        
        # 단순 숫자나 특수문자만 있는 경우 제외
        if content.isdigit() or content in ['?', '!', '.', ',', ':', ';']:
            return False
        
        # 의미없는 짧은 감탄사 제외
        meaningless_words = ['엥', '음', '어', '아', '으', '네', '예', '응']
        if content.strip() in meaningless_words:
            return False
        
        return True
    
    def clean_content_list(self, content_list: list) -> list:
        """
        content 리스트를 정제
        
        Args:
            content_list (list): 원본 content 리스트
        
        Returns:
            list: 정제된 content 리스트
        """
        cleaned_list = []
        
        for content in content_list:
            # 개행 문자를 공백으로 변경
            cleaned_content = re.sub(r'\n+', ' ', content)
            
            # 여러 공백을 하나로 정리
            cleaned_content = re.sub(r'\s+', ' ', cleaned_content)
            
            # 앞뒤 공백 제거
            cleaned_content = cleaned_content.strip()
            
            # 정제된 content가 유효하면 추가
            if self._is_valid_content(cleaned_content):
                cleaned_list.append(cleaned_content)
        
        return cleaned_list
    
    def convert_file(self, input_path: str, output_path: str = None) -> bool:
        """
        단일 파일을 변환
        
        Args:
            input_path (str): 입력 파일 경로
            output_path (str): 출력 파일 경로
        
        Returns:
            bool: 변환 성공 여부
        """
        # 출력 파일 경로 결정
        if output_path is None:
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_dir = os.path.dirname(input_path)
            output_path = os.path.join(output_dir, f"{base_name}_content_list.json")
        
        # content 추출
        content_list = self.extract_content_list(input_path)
        
        if not content_list:
            print(f"추출할 content가 없습니다: {input_path}")
            return False
        
        # content 정제
        cleaned_list = self.clean_content_list(content_list)
        
        # JSON 파일로 저장
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(cleaned_list, f, ensure_ascii=False, indent=2)
            
            print(f"변환 완료: {output_path}")
            print(f"  - 원본 content: {len(content_list)}개")
            print(f"  - 정제된 content: {len(cleaned_list)}개")
            
            # 미리보기
            print(f"\n📝 Content 미리보기 (처음 5개):")
            for i, content in enumerate(cleaned_list[:5], 1):
                preview = content[:80] + "..." if len(content) > 80 else content
                print(f"  {i}. {preview}")
            
            return True
            
        except Exception as e:
            print(f"파일 저장 실패 ({output_path}): {e}")
            return False
    
    def convert_all_files(self, input_dir: str, output_dir: str = None):
        """
        지원하는 모든 파일을 변환
        
        Args:
            input_dir (str): 입력 디렉토리
            output_dir (str): 출력 디렉토리
        """
        if output_dir is None:
            output_dir = input_dir
        
        # 출력 디렉토리 생성
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        print(f"입력 디렉토리: {input_dir}")
        print(f"출력 디렉토리: {output_dir}")
        print("=" * 60)
        
        success_count = 0
        fail_count = 0
        
        for file_name in self.supported_files:
            file_path = os.path.join(input_dir, file_name)
            
            if os.path.exists(file_path):
                # 출력 파일명 생성
                base_name = os.path.splitext(file_name)[0]
                output_file = os.path.join(output_dir, f"{base_name}_content_list.json")
                
                if self.convert_file(file_path, output_file):
                    success_count += 1
                else:
                    fail_count += 1
            else:
                print(f"파일을 찾을 수 없음: {file_path}")
                fail_count += 1
        
        print("\n" + "=" * 60)
        print(f"변환 완료 - 성공: {success_count}개, 실패: {fail_count}개")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='YouTube 크리에이터 데이터 변환기')
    parser.add_argument('--input', '-i', default='.', help='입력 디렉토리 (기본값: 현재 디렉토리)')
    parser.add_argument('--output', '-o', help='출력 디렉토리 (기본값: 입력 디렉토리)')
    parser.add_argument('--file', '-f', help='특정 파일만 변환')
    
    args = parser.parse_args()
    
    converter = YoutuberContentConverter()
    
    if args.file:
        # 특정 파일 변환
        input_path = os.path.abspath(args.file)
        output_path = None
        
        if args.output:
            output_dir = os.path.abspath(args.output)
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_path = os.path.join(output_dir, f"{base_name}_content_list.json")
        
        success = converter.convert_file(input_path, output_path)
        if not success:
            exit(1)
    else:
        # 모든 지원 파일 변환
        input_dir = os.path.abspath(args.input)
        output_dir = os.path.abspath(args.output) if args.output else input_dir
        
        converter.convert_all_files(input_dir, output_dir)


def show_usage():
    """사용법 출력"""
    print("=== YouTube 크리에이터 데이터 변환기 ===")
    print("\n지원하는 파일:")
    print("  - ITSub_data.json")
    print("  - JUYEON_data.json")
    print("\n기능:")
    print("  - JSON 파일의 paragraphs > content 값들을 리스트로 추출")
    print("  - 의미없는 content 필터링 및 정제")
    print("  - 중복 제거")
    print("\n사용법:")
    print("1. 모든 지원 파일 변환:")
    print("   python convert_youtuber_content.py")
    print("   python convert_youtuber_content.py -i ./youtuber -o ./output")
    print()
    print("2. 특정 파일 변환:")
    print("   python convert_youtuber_content.py -f ITSub_data.json")
    print("   python convert_youtuber_content.py -f JUYEON_data.json -o ./output")
    print()
    print("예시:")
    print("   python convert_youtuber_content.py")
    print("   python convert_youtuber_content.py --input /path/to/youtuber --output /path/to/output")


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