import yt_dlp
import os
import sys
from pathlib import Path

def download_youtube_audio(url, output_path="downloads"):
    """
    YouTube 영상을 MP3 형식으로 다운로드하는 함수
    
    Args:
        url (str): YouTube 영상 URL
        output_path (str): 다운로드할 폴더 경로
    
    Returns:
        bool: 다운로드 성공 여부
    """
    
    # 다운로드 옵션 설정
    ydl_opts = {
        'format': 'bestaudio/best',  # 최고 품질의 오디오
        'outtmpl': f'{output_path}/%(title)s.%(ext)s',  # 파일명 형식
        'noplaylist': True,  # 플레이리스트가 아닌 단일 영상만 다운로드
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',  # 320kbps 품질
        }],
        'postprocessor_args': [
            '-ar', '44100',  # 샘플링 레이트
        ],
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # 영상 정보 가져오기
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Unknown')
            duration = info.get('duration', 0)
            
            # 시간 포맷팅
            minutes = duration // 60
            seconds = duration % 60
            duration_str = f"{minutes:02d}:{seconds:02d}"
            
            print(f"다운로드 시작: {title} ({duration_str})")
            
            # 오디오 다운로드
            ydl.download([url])
            print(f"다운로드 완료: {title}")
            return True
            
    except Exception as e:
        print(f"다운로드 실패 - {url}: {str(e)}")
        return False

def download_from_txt_file(txt_file_path, output_path="downloads", quality="320"):
    """
    텍스트 파일에서 YouTube URL을 읽어와서 순차적으로 MP3로 다운로드하는 함수
    
    Args:
        txt_file_path (str): YouTube URL이 저장된 텍스트 파일 경로
        output_path (str): 다운로드할 폴더 경로
        quality (str): MP3 품질 (128, 192, 256, 320)
    """
    
    # 출력 폴더가 없으면 생성
    Path(output_path).mkdir(parents=True, exist_ok=True)
    
    try:
        # 텍스트 파일 읽기
        with open(txt_file_path, 'r', encoding='utf-8') as file:
            urls = file.readlines()
        
        # URL 정리 (공백, 개행문자 제거)
        urls = [url.strip() for url in urls if url.strip()]
        
        if not urls:
            print("텍스트 파일에 URL이 없습니다.")
            return
        
        print(f"총 {len(urls)}개의 음원을 MP3로 다운로드합니다.")
        print(f"품질: {quality}kbps")
        print(f"저장 폴더: {os.path.abspath(output_path)}")
        print("-" * 50)
        
        success_count = 0
        fail_count = 0
        
        # 다운로드 옵션 설정 (품질 적용)
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'{output_path}/%(title)s.%(ext)s',
            'noplaylist': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': quality,
            }],
            'postprocessor_args': [
                '-ar', '44100',
            ],
        }
        
        # 각 URL에 대해 다운로드 시도
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}] 처리 중...")
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # 영상 정보 가져오기
                    info = ydl.extract_info(url, download=False)
                    title = info.get('title', 'Unknown')
                    duration = info.get('duration', 0)
                    
                    # 시간 포맷팅
                    minutes = duration // 60
                    seconds = duration % 60
                    duration_str = f"{minutes:02d}:{seconds:02d}"
                    
                    print(f"다운로드 시작: {title} ({duration_str})")
                    
                    # 오디오 다운로드
                    ydl.download([url])
                    print(f"다운로드 완료: {title}")
                    success_count += 1
                    
            except Exception as e:
                print(f"다운로드 실패 - {url}: {str(e)}")
                fail_count += 1
        
        # 결과 출력
        print("\n" + "=" * 50)
        print(f"MP3 다운로드 완료!")
        print(f"성공: {success_count}개")
        print(f"실패: {fail_count}개")
        
    except FileNotFoundError:
        print(f"파일을 찾을 수 없습니다: {txt_file_path}")
    except Exception as e:
        print(f"오류 발생: {str(e)}")

def download_single_audio(url, output_path="downloads", quality="320"):
    """
    단일 YouTube URL을 MP3로 다운로드하는 함수
    
    Args:
        url (str): YouTube 영상 URL
        output_path (str): 다운로드할 폴더 경로
        quality (str): MP3 품질
    """
    
    # 출력 폴더가 없으면 생성
    Path(output_path).mkdir(parents=True, exist_ok=True)
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{output_path}/%(title)s.%(ext)s',
        'noplaylist': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': quality,
        }],
        'postprocessor_args': [
            '-ar', '44100',
        ],
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"MP3 다운로드 중... ({quality}kbps)")
            ydl.download([url])
            print("다운로드 완료!")
            return True
    except Exception as e:
        print(f"다운로드 실패: {str(e)}")
        return False

def main():
    """메인 함수"""
    
    # 사용법 안내
    if len(sys.argv) < 2:
        print("=== YouTube MP3 다운로더 ===")
        print("\n사용법:")
        print("1. 텍스트 파일에서 여러 URL 다운로드:")
        print("   python youtube_mp3_downloader.py <txt_파일_경로> [출력_폴더] [품질]")
        print("\n2. 단일 URL 다운로드:")
        print("   python youtube_mp3_downloader.py --single <YouTube_URL> [출력_폴더] [품질]")
        print("\n예시:")
        print("   python youtube_mp3_downloader.py urls.txt")
        print("   python youtube_mp3_downloader.py urls.txt my_music 192")
        print("   python youtube_mp3_downloader.py --single https://www.youtube.com/watch?v=example")
        print("\n품질 옵션: 128, 192, 256, 320 (기본값: 320kbps)")
        print("\n※ FFmpeg가 설치되어 있어야 합니다.")
        return
    
    # 단일 URL 다운로드
    if sys.argv[1] == "--single":
        if len(sys.argv) < 3:
            print("URL을 입력해주세요.")
            return
            
        url = sys.argv[2]
        output_folder = sys.argv[3] if len(sys.argv) > 3 else "downloads"
        quality = sys.argv[4] if len(sys.argv) > 4 else "320"
        
        download_single_audio(url, output_folder, quality)
        
    # 텍스트 파일에서 다운로드
    else:
        txt_file = sys.argv[1]
        output_folder = sys.argv[2] if len(sys.argv) > 2 else "downloads"
        quality = sys.argv[3] if len(sys.argv) > 3 else "320"
        
        # 품질 검증
        if quality not in ['128', '192', '256', '320']:
            print("지원되는 품질: 128, 192, 256, 320")
            quality = "320"
            print(f"기본값 {quality}kbps로 설정됩니다.")
        
        download_from_txt_file(txt_file, output_folder, quality)

if __name__ == "__main__":
    main()