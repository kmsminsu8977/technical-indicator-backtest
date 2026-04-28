# Technical Indicator Backtest

기술적 지표 백테스트 프로젝트의 기본 연구 구조와 재현 가능한 baseline 산출물을 담은 저장소입니다.

**핵심 연구 질문**

> 이동평균 교차 신호는 거래비용을 고려해도 단순 보유보다 나은 경로를 만드는가?

## 저장소 구조

```text
technical-indicator-backtest/
├── src/                         # baseline 계산 로직과 실행 엔트리포인트
├── data/sample/                 # 합성 샘플 입력 데이터
├── docs/                        # 방법론과 해석 기준
├── notebooks/                   # 실행 흐름을 보여주는 최소 노트북
├── outputs/tables/              # 재현 가능한 결과 CSV
├── presentation/                # 발표/보고서 초안
└── references/                  # 재작성 개념 노트와 참고문헌 메모
```

## 빠른 시작

```bash
python -m src.run_baseline
```

실행 결과는 `outputs/tables/baseline_results.csv`에 저장됩니다.

## 구현 범위

- 단기 이동평균이 장기 이동평균을 넘으면 long, 아니면 cash로 둔다.
- 신호는 다음 기간 수익률에 적용하고 포지션 변경 비용을 차감한다.
- 가격 경로는 이동평균 신호 계산 흐름을 설명하는 합성 데이터다.

## 주요 파일

- `src/technical_backtest_baseline.py`: 단기/장기 이동평균 신호를 재현 가능한 백테스트 테이블로 변환한다.
- `data/sample/price_series.csv`: baseline 실행용 합성 입력값
- `docs/methodology.md`: 계산 절차, 입력/출력 정의, 해석상 주의점
- `outputs/tables/baseline_results.csv`: 현재 baseline 산출물

## 다음 확장 방향

- 실제 공개 데이터 또는 별도 수집 데이터 연결
- notebook 기반 탐색 분석 추가
- 차트와 표를 포함한 최종 보고서 작성
- 모델 검증, 민감도 분석, 비용/리스크 가정 보강
