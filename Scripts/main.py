"""
Buoyancy Simulation - Main Entry Point

사용법:
1. Omniverse Isaac Sim의 Script Editor에서 이 파일을 실행
2. 'Create Platform' 버튼 클릭
3. 'Add Buoyancy' 버튼 클릭 (density: 50 kg/m³)
4. Timeline에서 PLAY 버튼 클릭
5. 파라미터 조정으로 실험
"""

import sys
SCRIPTS_PATH = "/home/rain/isaac_sim_test/Scripts"  # 실제 Scripts 폴더 경로
if SCRIPTS_PATH not in sys.path:
    sys.path.insert(0, SCRIPTS_PATH)

from buoyancy_manager import BuoyancyManager

# 기존 인스턴스 정리
if 'buoyancy_mgr' in globals():
    try:
        buoyancy_mgr.sub.unsubscribe()
    except:
        pass

# 새 인스턴스 생성
print("="*60)
print("Physics-Based Buoyancy Manager with Water Tank")
print("="*60)
print("Steps:")
print("  1. Click 'Create Platform'")
print("  2. Click 'Add Buoyancy' (default 50 kg/m³)")
print("  3. Click 'Enable Debug Output'")
print("  4. Press PLAY")
print("  5. Adjust parameters:")
print("     - Amplitude: Wave height")
print("     - Speed: Wave movement speed")
print("     - Tank Size: 10-50m")
print("     - Resolution: Mesh quality (10-50)")
print("="*60)

buoyancy_mgr = BuoyancyManager()

print("\n✓ System ready")
print("✓ Water tank created (Blue)")
print("✓ Transparent water material applied")
print("✓ Sun lighting enabled")
print("\nTo stop: buoyancy_mgr.sub.unsubscribe()")