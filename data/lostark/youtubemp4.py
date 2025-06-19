import yt_dlp
import os
import sys
from pathlib import Path

def download_youtube_video(url, output_path="downloads"):
    """
    YouTube 영상을 MP4 형식으로 다운로드하는 함수
    
    Args:
        url (str): YouTube 영상 URL
        output_path (str): 다운로드할 폴더 경로
    
    Returns:
        bool: 다운로드 성공 여부
    """
    
    # 다운로드 옵션 설정
    ydl_opts = {
        'format': 'best[ext=mp4]/mp4/best',  # MP4 형식 우선, 없으면 최고 화질
        'outtmpl': f'{output_path}/%(title)s.%(ext)s',  # 파일명 형식
        'noplaylist': True,  # 플레이리스트가 아닌 단일 영상만 다운로드
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # 영상 정보 가져오기
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Unknown')
            print(f"다운로드 시작: {title}")
            
            # 영상 다운로드
            ydl.download([url])
            print(f"다운로드 완료: {title}")
            return True
            
    except Exception as e:
        print(f"다운로드 실패 - {url}: {str(e)}")
        return False

def download_from_txt_file(txt_file_path, output_path="downloads"):
    """
    텍스트 파일에서 YouTube URL을 읽어와서 순차적으로 다운로드하는 함수
    
    Args:
        txt_file_path (str): YouTube URL이 저장된 텍스트 파일 경로
        output_path (str): 다운로드할 폴더 경로
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
        
        print(f"총 {len(urls)}개의 영상을 다운로드합니다.")
        print(f"저장 폴더: {os.path.abspath(output_path)}")
        print("-" * 50)
        
        success_count = 0
        fail_count = 0
        
        # 각 URL에 대해 다운로드 시도
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}] 처리 중...")
            
            if download_youtube_video(url, output_path):
                success_count += 1
            else:
                fail_count += 1
        
        # 결과 출력
        print("\n" + "=" * 50)
        print(f"다운로드 완료!")
        print(f"성공: {success_count}개")
        print(f"실패: {fail_count}개")
        
    except FileNotFoundError:
        print(f"파일을 찾을 수 없습니다: {txt_file_path}")
    except Exception as e:
        print(f"오류 발생: {str(e)}")

def main():
    """메인 함수"""
    
    # 사용법 안내
    if len(sys.argv) < 2:
        print("사용법:")
        print("python youtube_downloader.py <txt_파일_경로> [출력_폴더]")
        print("\n예시:")
        print("python youtube_downloader.py urls.txt")
        print("python youtube_downloader.py urls.txt my_videos")
        return
    
    txt_file = sys.argv[1]
    output_folder = sys.argv[2] if len(sys.argv) > 2 else "downloads"
    
    # 다운로드 실행
    download_from_txt_file(txt_file, output_folder)

if __name__ == "__main__":
    main()