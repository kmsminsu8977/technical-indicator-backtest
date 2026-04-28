# SOURCE.md

## 문서 목적

이 문서는 `technical-indicator-backtest` 컨텐츠를 만들 때 참고해야 할 로컬 source inventory입니다. 새 코드, 데이터 예시, 문서, 산출물을 만들 때는 이 파일과 `AGENTS.md`를 먼저 확인합니다.

## 프로젝트 식별

- 프로젝트명: 기술적 지표 백테스트 (Technical Indicator Backtest)
- 연구 카테고리: Market Signals & Event Analytics
- 핵심 질문: 이동평균 교차 신호는 거래비용을 고려해도 단순 보유보다 나은 경로를 만드는가?

## KAIST-DFMBA 참고 경로

아래 경로는 컨텐츠를 설계할 때 확인할 로컬 참고 위치입니다. 세부 구현은 이 저장소의 목적에 맞게 별도 구조로 정리합니다.

- KAIST-DFMBA/Quant-and-Factor-Investment-Strategies/
- KAIST-DFMBA/Financial-Data-Analysis/
- KAIST-DFMBA/Digital-Finance-Programming/

## 참고 초점

- 가격 시계열에서 신호를 생성하는 방식
- 신호 사용 가능 시점과 수익률 적용 시점 분리
- 거래비용 차감 누적성과 계산

## 현재 저장소 표준 구조

- `README.md`: 프로젝트 개요, 실행 방법, 주요 산출물 요약
- `AGENTS.md`: 작업 기준과 품질 기준
- `SOURCE.md`: 참고 경로와 컨텐츠 재구성 기준
- `docs/`: 방법론, 가정, 검증 기준
- `data/raw/`: 원천 데이터 위치와 수집 메모
- `data/processed/`: 정제 데이터 위치와 처리 메모
- `data/sample/`: 실행 가능한 작은 샘플 입력
- `notebooks/`: 탐색 분석과 설명용 노트북
- `src/`: 재사용 가능한 계산 로직
- `outputs/tables/`: 재현 가능한 결과 테이블
- `outputs/charts/`: 결과 차트
- `outputs/images/`: 보고서용 이미지
- `presentation/`: 발표/보고서 초안
- `references/`: 참고 문헌, 개념 노트, 링크 메모
- `archive/`: 오래된 실험 또는 보류 파일

## 컨텐츠 작성 순서

1. `SOURCE.md`에서 참고 경로와 참고 초점을 확인한다.
2. `AGENTS.md`에서 저장소 작업 기준과 금지 사항을 확인한다.
3. `data/sample/`에 작은 입력 예시를 먼저 둔다.
4. `src/`에서 반복 가능한 계산 로직을 만든다.
5. `outputs/tables/` 또는 `outputs/charts/`에 실행 결과를 남긴다.
6. `docs/methodology.md`와 `README.md`에 입력, 방법, 결과, 한계를 연결한다.

## 현재 baseline 산출물

- 실행 명령: `python -m src.run_baseline` 또는 레포별 README의 실행 명령
- 입력 데이터: `data/sample/`
- 결과 테이블: `outputs/tables/`
- 방법론 문서: `docs/methodology.md`

## 재구성 기준

- 참고 경로의 흐름은 연구 설계와 설명 순서를 잡는 데 사용한다.
- 프로젝트별 예제 값, 변수명, 설명, 코드 구조는 현재 저장소의 연구 질문에 맞게 작성한다.
- 코드와 문서는 나중에 실제 데이터로 교체할 수 있도록 입력, 계산, 출력 단계를 분리한다.
