"""명령행 실행용 baseline 엔트리포인트.

실제 계산 로직은 주제별 baseline 모듈에 있고, 이 파일은 모든 레포에서 같은 명령어를 쓰기 위한 얇은 실행 래퍼다.
"""

from __future__ import annotations

# 레포별 계산 모듈의 main 함수를 가져와 `python -m src.run_baseline`에서 바로 호출한다.
from .technical_backtest_baseline import main


if __name__ == "__main__":
    # 모듈이 스크립트로 실행될 때만 baseline 계산을 수행한다.
    main()
