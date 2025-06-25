import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
import glob

class ClovaTextExtractor:
    """
    Clova Speech Recognition 결과에서 변경된 텍스트만 추출하는 클래스
    """
    
    def __init__(self, file_path: str):
        """
        초기화
        
        Args:
            file_path (str): Clova CSR 결과 JSON 파일 경로
        """
        self.file_path = file_path
        self.data = self._load_json()
    
    def _load_json(self) -> Dict[str, Any]:
        """JSON 파일을 로드합니다."""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {self.file_path}")
        except json.JSONDecodeError:
            raise ValueError(f"JSON 형식이 올바르지 않습니다: {self.file_path}")
    
    def get_edited_segments(self) -> List[Dict[str, Any]]:
        """
        편집된(변경된) 세그먼트만 반환합니다.
        
        Returns:
            List[Dict]: 편집된 세그먼트 리스트
        """
        edited_segments = []
        
        for segment in self.data.get('segments', []):
            # textEdited가 있고 원본 text와 다른 경우
            if 'textEdited' in segment and segment['textEdited'] != segment['text']:
                edited_segments.append(segment)
        
        return edited_segments
    
    def get_final_text_list(self) -> List[str]:
        """
        모든 세그먼트의 최종 텍스트를 반환합니다.
        수정된 기록이 있으면 수정된 텍스트를, 없으면 원본 텍스트를 반환합니다.
        
        Returns:
            List[str]: 최종 텍스트 리스트
        """
        final_texts = []
        
        for segment in self.data.get('segments', []):
            # textEdited가 있으면 수정된 텍스트 사용, 없으면 원본 텍스트 사용
            if 'textEdited' in segment and segment['textEdited'].strip():
                final_texts.append(segment['textEdited'])
            else:
                final_texts.append(segment['text'])
        
        return final_texts
    
    def get_edited_text_only(self) -> List[str]:
        """
        편집된 텍스트만 리스트로 반환합니다.
        
        Returns:
            List[str]: 편집된 텍스트 리스트
        """
        edited_segments = self.get_edited_segments()
        return [segment['textEdited'] for segment in edited_segments]
    
    def get_comparison_data(self) -> List[Dict[str, str]]:
        """
        원본 텍스트와 편집된 텍스트의 비교 데이터를 반환합니다.
        
        Returns:
            List[Dict]: 비교 데이터 (original, edited, speaker, timestamp 포함)
        """
        edited_segments = self.get_edited_segments()
        comparison_data = []
        
        for segment in edited_segments:
            comparison_data.append({
                'original': segment['text'],
                'edited': segment['textEdited'],
                'speaker': segment.get('speaker', {}).get('name', 'Unknown'),
                'start_time': self._ms_to_time(segment['start']),
                'end_time': self._ms_to_time(segment['end']),
                'updated_at': segment.get('updatedAt', 'N/A')
            })
        
        return comparison_data
    
    def _ms_to_time(self, ms: int) -> str:
        """밀리초를 시:분:초.밀리초 형태로 변환합니다."""
        seconds = ms // 1000
        milliseconds = ms % 1000
        minutes = seconds // 60
        seconds = seconds % 60
        hours = minutes // 60
        minutes = minutes % 60
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
    
    def save_final_text(self, output_dir: str, filename: str = None) -> str:
        """
        최종 텍스트(수정된 것 + 원본)를 파일로 저장합니다.
        
        Args:
            output_dir (str): 저장할 디렉토리 경로
            filename (str, optional): 저장할 파일명
            
        Returns:
            str: 저장된 파일 경로
        """
        if filename is None:
            base_name = os.path.splitext(os.path.basename(self.file_path))[0]
            filename = f"{base_name}_final_text.txt"
        
        output_path = os.path.join(output_dir, filename)
        final_texts = self.get_final_text_list()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, text in enumerate(final_texts, 1):
                f.write(f"{i}. {text}\n")
        
        return output_path
    
    def save_edited_text(self, output_dir: str, filename: str = None) -> str:
        """
        편집된 텍스트를 파일로 저장합니다.
        
        Args:
            output_dir (str): 저장할 디렉토리 경로
            filename (str, optional): 저장할 파일명
            
        Returns:
            str: 저장된 파일 경로
        """
        if filename is None:
            base_name = os.path.splitext(os.path.basename(self.file_path))[0]
            filename = f"{base_name}_edited_only.txt"
        
        output_path = os.path.join(output_dir, filename)
        edited_texts = self.get_edited_text_only()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, text in enumerate(edited_texts, 1):
                f.write(f"{i}. {text}\n")
        
        return output_path
    
    def save_comparison_report(self, output_dir: str, filename: str = None) -> str:
        """
        편집 전후 비교 보고서를 저장합니다.
        
        Args:
            output_dir (str): 저장할 디렉토리 경로
            filename (str, optional): 저장할 파일명
            
        Returns:
            str: 저장된 파일 경로
        """
        if filename is None:
            base_name = os.path.splitext(os.path.basename(self.file_path))[0]
            filename = f"{base_name}_comparison_report.txt"
        
        output_path = os.path.join(output_dir, filename)
        comparison_data = self.get_comparison_data()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=== Clova CSR 텍스트 편집 비교 보고서 ===\n\n")
            f.write(f"생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"총 편집된 세그먼트 수: {len(comparison_data)}\n\n")
            
            for i, data in enumerate(comparison_data, 1):
                f.write(f"[{i}] {data['start_time']} - {data['end_time']} ({data['speaker']})\n")
                f.write(f"원본: {data['original']}\n")
                f.write(f"수정: {data['edited']}\n")
                f.write(f"수정일시: {data['updated_at']}\n")
                f.write("-" * 50 + "\n\n")
        
        return output_path
    
    def print_summary(self):
        """편집 요약 정보를 출력합니다."""
        edited_segments = self.get_edited_segments()
        total_segments = len(self.data.get('segments', []))
        
        print(f"=== Clova CSR 텍스트 편집 요약 ===")
        print(f"파일: {os.path.basename(self.file_path)}")
        print(f"전체 세그먼트 수: {total_segments}")
        print(f"편집된 세그먼트 수: {len(edited_segments)}")
        if total_segments > 0:
            print(f"편집 비율: {len(edited_segments)/total_segments*100:.1f}%")
        
        # 화자별 편집 통계
        speaker_edits = {}
        for segment in edited_segments:
            speaker = segment.get('speaker', {}).get('name', 'Unknown')
            speaker_edits[speaker] = speaker_edits.get(speaker, 0) + 1
        
        if speaker_edits:
            print(f"\n화자별 편집 수:")
            for speaker, count in speaker_edits.items():
                print(f"  {speaker}: {count}개")


def process_folder(input_dir: str, output_dir: str):
    """
    폴더 내의 모든 JSON 파일을 처리합니다.
    
    Args:
        input_dir (str): 입력 폴더 경로
        output_dir (str): 출력 폴더 경로
    """
    # 출력 디렉토리가 없으면 생성
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # JSON 파일 찾기 (*.json과 *.txt 파일 모두 포함)
    json_files = []
    for ext in ['*.json', '*.txt']:
        json_files.extend(glob.glob(os.path.join(input_dir, ext)))
    
    if not json_files:
        print(f"입력 폴더에서 JSON/TXT 파일을 찾을 수 없습니다: {input_dir}")
        return
    
    print(f"처리할 파일 수: {len(json_files)}")
    print(f"입력 폴더: {input_dir}")
    print(f"출력 폴더: {output_dir}")
    print("=" * 50)
    
    processed_count = 0
    error_count = 0
    
    for file_path in json_files:
        try:
            print(f"\n처리 중: {os.path.basename(file_path)}")
            
            # ClovaTextExtractor 인스턴스 생성
            extractor = ClovaTextExtractor(file_path)
            
            # 요약 정보 출력
            extractor.print_summary()
            
            # 파일로 저장
            final_file = extractor.save_final_text(output_dir)
            edited_file = extractor.save_edited_text(output_dir)
            comparison_file = extractor.save_comparison_report(output_dir)
            
            print(f"저장 완료:")
            print(f"  - 최종 텍스트: {os.path.basename(final_file)}")
            print(f"  - 편집된 텍스트: {os.path.basename(edited_file)}")
            print(f"  - 비교 보고서: {os.path.basename(comparison_file)}")
            
            processed_count += 1
            
        except Exception as e:
            print(f"오류 발생 ({os.path.basename(file_path)}): {e}")
            error_count += 1
    
    print("\n" + "=" * 50)
    print(f"처리 완료 - 성공: {processed_count}개, 실패: {error_count}개")


def main():
    """메인 실행 함수"""
    import argparse
    
    # 명령행 인자 파싱
    parser = argparse.ArgumentParser(description='Clova CSR 텍스트 추출 도구')
    parser.add_argument('input_dir', nargs='?', help='입력 폴더 경로 (필수)')
    parser.add_argument('-o', '--output', help='출력 폴더 경로 (선택, 기본값: 입력폴더/output)')
    args = parser.parse_args()
    
    # 입력 폴더 결정
    if args.input_dir:
        input_dir = args.input_dir
    else:
        # 명령행 인자가 없으면 환경변수에서 가져오기
        input_dir = os.getenv('CLOVA_INPUT_DIR', './input')
    
    # 출력 폴더 결정
    if args.output:
        output_dir = args.output
    else:
        # 출력 폴더가 지정되지 않으면 입력 폴더 내의 output 폴더 사용
        output_dir = os.path.join(input_dir, 'output')
    
    # 상대 경로를 절대 경로로 변환
    input_dir = os.path.abspath(input_dir)
    output_dir = os.path.abspath(output_dir)
    
    print(f"입력 폴더: {input_dir}")
    print(f"출력 폴더: {output_dir}")
    
    # 입력 폴더 존재 확인
    if not os.path.exists(input_dir):
        print(f"입력 폴더가 존재하지 않습니다: {input_dir}")
        print("\n사용법:")
        print("  python script.py <입력폴더경로> [-o <출력폴더경로>]")
        print("\n예시:")
        print("  python script.py ./data")
        print("  python script.py /home/user/files -o ./results")
        print("  python script.py ../source --output /tmp/output")
        return
    
    try:
        # 폴더 내 모든 파일 처리
        process_folder(input_dir, output_dir)
        
    except Exception as e:
        print(f"오류 발생: {e}")


def show_usage():
    """사용법을 출력합니다."""
    print("=== Clova CSR 텍스트 추출 도구 사용법 ===")
    print("\n1. 기본 사용법:")
    print("   python script.py <입력폴더경로>")
    print("   예: python script.py ./data")
    print("   예: python script.py /home/user/clova_files")
    print("   예: python script.py ../source")
    print()
    print("2. 출력 폴더 지정:")
    print("   python script.py <입력폴더경로> -o <출력폴더경로>")
    print("   python script.py <입력폴더경로> --output <출력폴더경로>")
    print("   예: python script.py ./data -o ./results")
    print("   예: python script.py /home/user/files --output /tmp/output")
    print()
    print("3. 환경변수 사용 (인자 없이 실행):")
    print("   export CLOVA_INPUT_DIR='./input'")
    print("   python script.py")
    print()
    print("※ 출력 폴더를 지정하지 않으면 입력폴더/output에 저장됩니다.")
    print("=" * 50)


if __name__ == "__main__":
    import sys
    
    # 도움말 요청 시
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', 'help']:
        show_usage()
    else:
        main()