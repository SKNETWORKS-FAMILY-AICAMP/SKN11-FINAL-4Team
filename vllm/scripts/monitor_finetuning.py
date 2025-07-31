#!/usr/bin/env python3
"""
파인튜닝 프로세스 모니터링 스크립트
GPU 메모리 사용량, CPU 사용량, 프로세스 상태를 실시간으로 모니터링
"""

import os
import sys
import time
import psutil
import torch
import subprocess
from datetime import datetime

def get_gpu_memory_info():
    """GPU 메모리 정보 조회"""
    if not torch.cuda.is_available():
        return None
    
    info = []
    for i in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(i)
        allocated = torch.cuda.memory_allocated(i) / 1024**3
        reserved = torch.cuda.memory_reserved(i) / 1024**3
        total = props.total_memory / 1024**3
        
        info.append({
            'device': i,
            'name': props.name,
            'allocated': allocated,
            'reserved': reserved,
            'total': total,
            'free': total - allocated,
            'usage_percent': (allocated / total) * 100
        })
    
    return info

def get_process_info(process_name='python'):
    """특정 프로세스 정보 조회"""
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
        try:
            if process_name in proc.info['name']:
                cmdline = ' '.join(proc.cmdline())
                if 'fine_custom' in cmdline or 'finetuning' in cmdline:
                    processes.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cpu_percent': proc.cpu_percent(interval=0.1),
                        'memory_mb': proc.info['memory_info'].rss / 1024**2,
                        'cmdline': cmdline[:100] + '...' if len(cmdline) > 100 else cmdline
                    })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    return processes

def monitor_finetuning(interval=5):
    """파인튜닝 모니터링 메인 루프"""
    print("🔍 파인튜닝 모니터링 시작...")
    print(f"모니터링 간격: {interval}초")
    print("-" * 80)
    
    while True:
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n📊 [{timestamp}] 시스템 상태")
            
            # GPU 메모리 정보
            gpu_info = get_gpu_memory_info()
            if gpu_info:
                print("\n🖥️ GPU 메모리 상태:")
                for gpu in gpu_info:
                    print(f"  GPU {gpu['device']} ({gpu['name']}):")
                    print(f"    - 사용중: {gpu['allocated']:.2f}GB / {gpu['total']:.2f}GB ({gpu['usage_percent']:.1f}%)")
                    print(f"    - 여유: {gpu['free']:.2f}GB")
                    print(f"    - 예약됨: {gpu['reserved']:.2f}GB")
                    
                    # 메모리 부족 경고
                    if gpu['usage_percent'] > 90:
                        print(f"    ⚠️ 경고: GPU {gpu['device']} 메모리 사용률이 90% 이상입니다!")
                    elif gpu['usage_percent'] > 80:
                        print(f"    ⚠️ 주의: GPU {gpu['device']} 메모리 사용률이 80% 이상입니다.")
            
            # 프로세스 정보
            processes = get_process_info()
            if processes:
                print("\n🔄 파인튜닝 관련 프로세스:")
                for proc in processes:
                    print(f"  PID {proc['pid']}:")
                    print(f"    - CPU: {proc['cpu_percent']:.1f}%")
                    print(f"    - 메모리: {proc['memory_mb']:.0f}MB")
                    print(f"    - 명령: {proc['cmdline']}")
            else:
                print("\n❌ 실행 중인 파인튜닝 프로세스가 없습니다.")
            
            # 시스템 전체 정보
            print(f"\n💻 시스템 전체:")
            print(f"  - CPU 사용률: {psutil.cpu_percent(interval=1):.1f}%")
            print(f"  - 메모리 사용률: {psutil.virtual_memory().percent:.1f}%")
            
            print("-" * 80)
            
        except KeyboardInterrupt:
            print("\n\n🛑 모니터링 종료")
            break
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
        
        time.sleep(interval)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="파인튜닝 프로세스 모니터링")
    parser.add_argument('--interval', type=int, default=5, help='모니터링 간격 (초)')
    
    args = parser.parse_args()
    
    monitor_finetuning(interval=args.interval)