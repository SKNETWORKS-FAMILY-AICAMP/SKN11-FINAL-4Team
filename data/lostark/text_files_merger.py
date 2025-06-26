import os
import re
import json

def merge_silian_texts(folder_path, output_file):
    """
    실리안 텍스트 파일들을 하나로 합쳐서 리스트 형태로 저장하는 함수
    
    Args:
        folder_path (str): 텍스트 파일들이 있는 폴더 경로
        output_file (str): 저장할 파일 경로 (예: "merged_silian_texts.txt")
    """
    
    all_texts = []
    
    # 폴더 내의 모든 txt 파일 찾기
    txt_files = [f for f in os.listdir(folder_path) if f.endswith('.txt')]
    txt_files.sort()  # 파일명 순으로 정렬
    
    print(f"찾은 파일들: {txt_files}")
    
    for filename in txt_files:
        file_path = os.path.join(folder_path, filename)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read().strip()
                
                # 파일 내용을 줄 단위로 분리
                lines = content.split('\n')
                
                for line in lines:
                    line = line.strip()
                    if line:  # 빈 줄 제외
                        # 앞의 숫자와 점 제거 (예: "1. ", "10. " 등)
                        cleaned_line = re.sub(r'^\d+\.\s*', '', line)
                        
                        if cleaned_line:  # 정리 후에도 내용이 있는 경우만 추가
                            all_texts.append(cleaned_line)
                            
        except Exception as e:
            print(f"파일 '{filename}' 읽기 오류: {e}")
    
    # 결과를 텍스트 파일로 저장
    output_path = os.path.join(folder_path, output_file)
    
    with open(output_path, 'w', encoding='utf-8') as output:
        # 각 텍스트를 리스트 형태로 저장
        for i, text in enumerate(all_texts, 1):
            output.write(f"{i}. {text}\n")
    
    # JSON 형태로도 저장 (선택사항)
    json_output = output_file.replace('.txt', '.json')
    json_path = os.path.join(folder_path, json_output)
    
    with open(json_path, 'w', encoding='utf-8') as json_file:
        json.dump(all_texts, json_file, ensure_ascii=False, indent=2)
    
    print(f"총 {len(all_texts)}개의 텍스트가 합쳐졌습니다.")
    print(f"결과 파일: {output_path}")
    print(f"JSON 파일: {json_path}")
    
    return all_texts

# 사용 예시
if __name__ == "__main__":
    # 폴더 경로 설정
    folder_path = "/Users/link/Documents/SKN/FINAL-project/silian_text_extract"
    
    # 합친 텍스트를 저장할 파일명
    output_filename = "merged_silian_texts.txt"
    
    # 함수 실행
    merged_texts = merge_silian_texts(folder_path, output_filename)
    
    # 처음 5개 텍스트 미리보기
    print("\n처음 5개 텍스트 미리보기:")
    for i, text in enumerate(merged_texts[:5], 1):
        print(f"{i}. {text}")