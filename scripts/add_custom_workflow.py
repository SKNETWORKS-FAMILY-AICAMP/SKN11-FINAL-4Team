#!/usr/bin/env python3
"""
커스텀 워크플로우 등록 스크립트

사용법:
1. ComfyUI에서 워크플로우를 JSON으로 내보내기
2. 이 스크립트로 시스템에 등록

python scripts/add_custom_workflow.py --workflow-file my_workflow.json --name "내 커스텀 워크플로우"
"""

import json
import argparse
import sys
import os
from pathlib import Path

# 백엔드 경로 추가
sys.path.append(str(Path(__file__).parent.parent / "backend"))

from app.services.workflow_manager import get_workflow_manager, WorkflowTemplate

def load_workflow_json(file_path: str):
    """ComfyUI 워크플로우 JSON 파일 로드"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def analyze_workflow_nodes(workflow_json: dict):
    """워크플로우에서 사용자 입력이 가능한 노드들 분석"""
    input_parameters = {}
    
    for node_id, node_data in workflow_json.items():
        class_type = node_data.get("class_type", "")
        inputs = node_data.get("inputs", {})
        
        # 일반적인 사용자 입력 노드들 확인
        if class_type == "CLIPTextEncode":
            if "text" in inputs:
                param_name = "negative_prompt" if "negative" in node_data.get("_meta", {}).get("title", "").lower() else "prompt"
                input_parameters[param_name] = {
                    "node_id": node_id,
                    "input_name": "text",
                    "type": "string",
                    "description": f"텍스트 입력 ({param_name})"
                }
        
        elif class_type == "EmptyLatentImage":
            if "width" in inputs:
                input_parameters["width"] = {
                    "node_id": node_id,
                    "input_name": "width",
                    "type": "int",
                    "description": "이미지 너비"
                }
            if "height" in inputs:
                input_parameters["height"] = {
                    "node_id": node_id,
                    "input_name": "height", 
                    "type": "int",
                    "description": "이미지 높이"
                }
        
        elif class_type == "KSampler":
            for param in ["steps", "cfg", "seed"]:
                if param in inputs:
                    param_name = "cfg_scale" if param == "cfg" else param
                    input_parameters[param_name] = {
                        "node_id": node_id,
                        "input_name": param,
                        "type": "float" if param == "cfg" else "int",
                        "description": f"샘플링 {param_name}"
                    }
    
    return input_parameters

async def register_workflow(workflow_file: str, name: str, description: str = "", category: str = "txt2img"):
    """워크플로우를 시스템에 등록"""
    
    # 워크플로우 JSON 로드
    workflow_json = load_workflow_json(workflow_file)
    
    # 입력 파라미터 분석
    input_parameters = analyze_workflow_nodes(workflow_json)
    
    print(f"발견된 입력 파라미터: {list(input_parameters.keys())}")
    
    # 워크플로우 ID 생성
    import uuid
    workflow_id = f"custom_{uuid.uuid4().hex[:8]}"
    
    # 워크플로우 템플릿 생성
    workflow_template = WorkflowTemplate(
        id=workflow_id,
        name=name,
        description=description,
        category=category,
        workflow_json=workflow_json,
        input_parameters=input_parameters,
        created_by="user",
        tags=["커스텀", "사용자정의"],
        is_active=True
    )
    
    # 워크플로우 매니저를 통해 저장
    workflow_manager = get_workflow_manager()
    saved_id = await workflow_manager.save_workflow(workflow_template)
    
    print(f"✅ 워크플로우 등록 완료!")
    print(f"   ID: {saved_id}")
    print(f"   이름: {name}")
    print(f"   파일: {workflow_file}")
    print(f"   입력 파라미터: {len(input_parameters)}개")
    
    return saved_id

def main():
    parser = argparse.ArgumentParser(description="ComfyUI 커스텀 워크플로우 등록")
    parser.add_argument("--workflow-file", required=True, help="ComfyUI 워크플로우 JSON 파일 경로")
    parser.add_argument("--name", required=True, help="워크플로우 이름")
    parser.add_argument("--description", default="", help="워크플로우 설명")
    parser.add_argument("--category", default="txt2img", help="워크플로우 카테고리")
    parser.add_argument("--set-default", action="store_true", help="이 워크플로우를 기본값으로 설정")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.workflow_file):
        print(f"❌ 파일을 찾을 수 없습니다: {args.workflow_file}")
        return
    
    try:
        import asyncio
        workflow_id = asyncio.run(register_workflow(
            args.workflow_file,
            args.name,
            args.description,
            args.category
        ))
        
        if args.set_default:
            # 기본 워크플로우로 설정
            set_default_workflow(workflow_id)
            print(f"✅ '{args.name}'를 기본 워크플로우로 설정했습니다.")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

def set_default_workflow(workflow_id: str):
    """기본 워크플로우 설정"""
    config_file = Path(__file__).parent.parent / "backend" / "app" / "config" / "default_workflow.json"
    config_file.parent.mkdir(exist_ok=True)
    
    config = {
        "default_workflow_id": workflow_id,
        "updated_at": str(pd.Timestamp.now())
    }
    
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()