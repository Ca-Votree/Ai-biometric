#!/usr/bin/env python3
"""
GPU Checker for AI Biometrics
Kiểm tra GPU, CUDA, và các thư viện ML cần thiết
"""

import os
import sys

def check_gpu_status():
    """Comprehensive GPU check"""
    
    print("\n" + "="*70)
    print("   🚀 AI BIOMETRICS - GPU STATUS CHECK")
    print("="*70)
    
    success_count = 0
    total_count = 0
    
    # 1. ONNXRuntime
    print("\n[1] 🔧 ONNXRuntime (Dùng cho YOLO và InsightFace/ArcFace)")
    total_count += 1
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        
        print(f"  ✅ ONNXRuntime phiên bản: {ort.__version__}")
        print(f"  📊 Providers khả dụng: {', '.join(providers)}")
        
        if 'CUDAExecutionProvider' in providers:
            print(f"  ✅ CUDA Provider: YES")
            success_count += 1
        else:
            print(f"  ⚠️  CUDA Provider: NO (sẽ dùng CPU)")
            
    except ImportError as e:
        print(f"  ❌ ONNXRuntime chưa cài đặt: {e}")
    
    # 3. Ultralytics YOLO
    print("\n[3] 🔧 Ultralytics YOLO")
    total_count += 1
    try:
        from ultralytics import YOLO
        print(f"  ✅ Ultralytics cài đặt thành công")
        success_count += 1
    except ImportError as e:
        print(f"  ❌ Ultralytics chưa cài đặt: {e}")
    
    # 4. FAISS (Vector Search)
    print("\n[4] 🔧 FAISS (Vector Search - GPU Optimized)")
    total_count += 1
    try:
        import faiss
        gpu_available = faiss.get_num_gpus() > 0
        
        if gpu_available:
            print(f"  ✅ FAISS GPU build: YES ({faiss.get_num_gpus()} device(s))")
            success_count += 1
        else:
            print(f"  ⚠️  FAISS GPU build: NO (running CPU version)")
            
    except ImportError as e:
        print(f"  ❌ FAISS chưa cài đặt: {e}")
    
    # 5. InsightFace
    print("\n[5] 🔧 InsightFace")
    total_count += 1
    try:
        import insightface
        print(f"  ✅ InsightFace cài đặt thành công")
        success_count += 1
    except ImportError as e:
        print(f"  ❌ InsightFace chưa cài đặt: {e}")
    
    # 6. Application Config
    print("\n[6] ⚙️  Application Configuration")
    total_count += 1
    try:
        from app.config import settings
        
        print(f"  ✅ Cấu hình tải thành công")
        print(f"     - USE_GPU: {settings.USE_GPU}")
        print(f"     - GPU_DEVICE: {settings.GPU_DEVICE}")
        print(f"     - MAX_FACES_PER_FRAME: {settings.MAX_FACES_PER_FRAME}")
        print(f"     - FACE_DETECTION_THRESHOLD: {settings.FACE_DETECTION_THRESHOLD}")
        print(f"     - FACE_RECOGNITION_THRESHOLD: {settings.FACE_RECOGNITION_THRESHOLD}")
        success_count += 1
    except Exception as e:
        print(f"  ❌ Lỗi tải cấu hình: {e}")
    
    # Summary
    print("\n" + "="*70)
    print(f"📊 SUMMARY: {success_count}/{total_count} checks passed")
    
    if success_count == total_count:
        print("✅ Tất cả kiểm tra PASSED - Sẵn sàng chạy GPU!")
    elif success_count >= total_count - 1:
        print("⚠️  Hầu hết kiểm tra PASSED - Có thể chạy nhưng hiệu năng può bị ảnh hưởng")
    else:
        print("❌ Có lỗi - Vui lòng cài đặt các dependencies còn thiếu")
    
    print("="*70 + "\n")
    
    return success_count == total_count

if __name__ == "__main__":
    success = check_gpu_status()
    sys.exit(0 if success else 1)
