import openai
import os
import sys
import time
from pathlib import Path
import json
from datetime import datetime
from pydub import AudioSegment
import tempfile
import math

def get_audio_duration(audio_path):
    """오디오 파일의 길이를 구하는 함수"""
    try:
        audio = AudioSegment.from_file(audio_path)
        return len(audio) / 1000  # 초 단위
    except Exception as e:
        print(f"오디오 길이 확인 실패: {e}")
        return 0

def split_audio_file(audio_path, max_size_mb=23):
    """
    오디오 파일을 25MB 이하 청크로 분할
    
    Args:
        audio_path (str): 원본 오디오 파일 경로
        max_size_mb (int): 최대 파일 크기 (MB)
    
    Returns:
        list: 분할된 파일 경로들
    """
    
    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    
    # 파일이 충분히 작으면 분할하지 않음
    if file_size_mb <= max_size_mb:
        return [audio_path]
    
    print(f"파일 크기가 {file_size_mb:.1f}MB이므로 분할합니다...")
    
    # 오디오 로드
    audio = AudioSegment.from_file(audio_path)
    duration_ms = len(audio)
    duration_minutes = duration_ms / (1000 * 60)
    
    print(f"오디오 길이: {duration_minutes:.1f}분")
    
    # 청크 크기 계산 (10분 단위로 분할)
    chunk_duration_ms = 10 * 60 * 1000  # 10분
    overlap_ms = 2000  # 2초 겹침
    
    chunks = []
    temp_dir = tempfile.mkdtemp()
    
    start_ms = 0
    chunk_num = 0
    
    while start_ms < duration_ms:
        chunk_num += 1
        end_ms = min(start_ms + chunk_duration_ms, duration_ms)
        
        # 청크 추출
        chunk = audio[start_ms:end_ms]
        
        # 임시 파일로 저장
        chunk_path = os.path.join(temp_dir, f"chunk_{chunk_num:03d}.mp3")
        chunk.export(chunk_path, format="mp3", bitrate="128k")
        
        chunks.append(chunk_path)
        
        chunk_size = os.path.getsize(chunk_path) / (1024 * 1024)
        chunk_duration = len(chunk) / (1000 * 60)
        
        print(f"청크 {chunk_num}: {chunk_duration:.1f}분, {chunk_size:.1f}MB")
        
        # 다음 청크 시작점 (겹침 고려)
        start_ms = end_ms - overlap_ms
        
        if end_ms >= duration_ms:
            break
    
    print(f"총 {len(chunks)}개 청크로 분할 완료")
    return chunks

def transcribe_audio_with_api(audio_path, api_key, model="whisper-1", language=None, response_format="verbose_json", temperature=0):
    """
    OpenAI API를 사용해서 오디오 파일을 텍스트로 변환
    
    Args:
        audio_path (str): 오디오 파일 경로
        api_key (str): OpenAI API 키
        model (str): 사용할 모델
        language (str): 언어 코드
        response_format (str): 응답 형식
        temperature (float): 온도 설정
    
    Returns:
        dict: 변환 결과
    """
    
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {audio_path}")
    
    # 파일 크기 확인
    file_size = os.path.getsize(audio_path)
    file_size_mb = file_size / (1024 * 1024)
    
    if file_size > 25 * 1024 * 1024:
        raise ValueError(f"파일 크기가 25MB를 초과합니다: {file_size_mb:.2f}MB")
    
    # OpenAI 클라이언트 설정
    client = openai.OpenAI(api_key=api_key)
    
    print(f"처리 중: {os.path.basename(audio_path)} ({file_size_mb:.2f}MB)")
    
    start_time = time.time()
    
    try:
        with open(audio_path, "rb") as audio_file:
            # API 호출 매개변수 설정
            transcription_params = {
                "file": audio_file,
                "model": model,
                "response_format": response_format,
                "temperature": temperature
            }
            
            # 언어가 지정된 경우 추가
            if language:
                transcription_params["language"] = language
            
            # API 호출
            transcript = client.audio.transcriptions.create(**transcription_params)
            
        end_time = time.time()
        processing_time = end_time - start_time
        print(f"API 처리 완료: {processing_time:.2f}초")
        
        # 결과 정보 출력
        if response_format == "verbose_json":
            if hasattr(transcript, 'text'):
                text_length = len(transcript.text)
                segments_count = len(transcript.segments) if hasattr(transcript, 'segments') else 0
                print(f"텍스트 길이: {text_length}자, 세그먼트: {segments_count}개")
        
        return transcript
        
    except Exception as e:
        print(f"API 호출 실패: {str(e)}")
        raise

def transcribe_long_audio(audio_path, api_key, model="whisper-1", language=None, temperature=0):
    """
    긴 오디오 파일을 분할해서 전체 텍스트로 변환
    
    Args:
        audio_path (str): 오디오 파일 경로
        api_key (str): OpenAI API 키
        model (str): 모델명
        language (str): 언어 코드
        temperature (float): 온도
    
    Returns:
        dict: 전체 변환 결과
    """
    
    # 오디오 길이 확인
    duration = get_audio_duration(audio_path)
    print(f"전체 오디오 길이: {duration/60:.1f}분")
    
    # 예상 비용 계산
    estimated_cost = (duration / 60) * 0.006
    print(f"예상 비용: ${estimated_cost:.4f}")
    
    # 파일 분할
    chunk_paths = split_audio_file(audio_path)
    
    # 각 청크 처리
    all_segments = []
    full_text = ""
    total_duration = 0
    
    try:
        for i, chunk_path in enumerate(chunk_paths, 1):
            print(f"\n=== 청크 {i}/{len(chunk_paths)} 처리 중 ===")
            
            # 청크 처리
            result = transcribe_audio_with_api(
                chunk_path, 
                api_key, 
                model=model, 
                language=language, 
                response_format="verbose_json", 
                temperature=temperature
            )
            
            # 결과 처리
            if hasattr(result, 'text'):
                chunk_text = result.text.strip()
                full_text += chunk_text + " "
                
                # 세그먼트 정보 수집 (시간 오프셋 조정)
                if hasattr(result, 'segments'):
                    for segment in result.segments:
                        adjusted_segment = {
                            'start': segment.start + total_duration,
                            'end': segment.end + total_duration,
                            'text': segment.text
                        }
                        all_segments.append(adjusted_segment)
                
                # 청크 길이 누적
                chunk_duration = get_audio_duration(chunk_path)
                total_duration += chunk_duration
                
                print(f"청크 {i} 텍스트 길이: {len(chunk_text)}자")
            
    finally:
        # 임시 파일 정리
        for chunk_path in chunk_paths:
            if chunk_path != audio_path and os.path.exists(chunk_path):
                try:
                    os.remove(chunk_path)
                except:
                    pass
        
        # 임시 디렉토리 정리
        if len(chunk_paths) > 1:
            temp_dir = os.path.dirname(chunk_paths[0])
            try:
                os.rmdir(temp_dir)
            except:
                pass
    
    # 결과 반환
    result = {
        'text': full_text.strip(),
        'segments': all_segments,
        'language': language,
        'duration': total_duration
    }
    
    print(f"\n🎉 전체 처리 완료!")
    print(f"최종 텍스트 길이: {len(result['text'])}자")
    print(f"총 세그먼트: {len(all_segments)}개")
    print(f"총 처리 시간: {total_duration/60:.1f}분")
    
    return result

def save_transcript_result(result, output_path, include_timestamps=True):
    """변환 결과를 다양한 형식으로 저장"""
    
    # 텍스트 파일
    with open(f"{output_path}.txt", "w", encoding="utf-8") as f:
        f.write(result['text'])
    print(f"텍스트 저장: {output_path}.txt")
    
    # 타임스탬프 포함 텍스트
    if include_timestamps and 'segments' in result:
        with open(f"{output_path}_timestamps.txt", "w", encoding="utf-8") as f:
            for segment in result['segments']:
                start_time = f"{int(segment['start']//60):02d}:{int(segment['start']%60):02d}"
                f.write(f"[{start_time}] {segment['text'].strip()}\n")
        print(f"타임스탬프 저장: {output_path}_timestamps.txt")
    
    # JSON 파일
    with open(f"{output_path}.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"JSON 저장: {output_path}.json")

def get_api_key():
    """API 키 가져오기"""
    api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        api_key = input("OpenAI API 키를 입력하세요: ").strip()
        
        if not api_key:
            raise ValueError("API 키가 필요합니다.")
    
    return api_key

def main():
    """메인 함수"""
    
    if len(sys.argv) < 2:
        print("=== OpenAI Whisper API STT 변환기 (긴 음성 지원) ===")
        print("\n사용법:")
        print("   python whisper_long_stt.py <오디오_파일> [언어]")
        print("\n예시:")
        print("   python whisper_long_stt.py audio.mp3")
        print("   python whisper_long_stt.py audio.mp3 ko")
        print("\n언어 코드: ko(한국어), en(영어), ja(일본어), zh(중국어) 등")
        print("\n환경변수 설정:")
        print("   export OPENAI_API_KEY=your_api_key_here")
        print("\n특징:")
        print("   - 긴 음성 파일 자동 분할 처리")
        print("   - 타임스탬프 포함 결과")
        print("   - 전체 음성 완전 변환")
        return
    
    try:
        # API 키 가져오기
        api_key = get_api_key()
        
        audio_file = sys.argv[1]
        language = sys.argv[2] if len(sys.argv) > 2 else None
        
        # 음성 인식 실행
        result = transcribe_long_audio(
            audio_file, 
            api_key,
            language=language
        )
        
        # 출력 파일 이름 생성
        output_name = os.path.splitext(audio_file)[0]
        
        # 결과 저장
        save_transcript_result(result, output_name, include_timestamps=True)
        
        # 결과 미리보기
        print(f"\n📝 변환 결과 미리보기:")
        preview = result['text'][:300] + "..." if len(result['text']) > 300 else result['text']
        print(f"{preview}")
        
    except Exception as e:
        print(f"오류 발생: {str(e)}")

if __name__ == "__main__":
    main()