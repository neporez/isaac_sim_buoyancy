"""
Buoyancy Simulation v2 - Point Cloud Based
복잡한 메시에서도 정확한 부력 계산

사용법:
1. Isaac Sim Script Editor에서 이 스크립트 실행
2. UI에서 물체 경로 입력 (하위에 Collider + Mass 필요)
3. Add Buoyancy 클릭
4. Play 버튼으로 시뮬레이션 시작 (자동으로 포인트 초기화)

구조:
/World/Ship (RigidBodyAPI + ForceAPI)
    /Hull (CollisionAPI + MassAPI)
    /Engine (CollisionAPI + MassAPI)
    /Deck (CollisionAPI + MassAPI)
"""
import sys
SCRIPTS_PATH = "/home/rain/isaac_sim_test/Scripts2"
if SCRIPTS_PATH not in sys.path:
    sys.path.insert(0, SCRIPTS_PATH)

from buoyancy_manager import BuoyancyManager

# 매니저 생성
manager = BuoyancyManager()
