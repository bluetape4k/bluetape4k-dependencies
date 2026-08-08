# README 다이어그램 이미지 검증

## 배경

의존성 BOM README 다이어그램을 원래 Mermaid 기록에서 공용 파스텔 인포그래픽
PNG/SVG 스타일로 다시 생성했다.

## 결정

README 삽입에는 PNG를 사용하고 재사용을 위해 SVG를 옆에 보관한다. 다이어그램
텍스트는 영어만 유지하며, 의존성 그래프가 필요한 공간을 사용할 수 있도록 캔버스
크기를 고정하지 않는다.

## 결과

- 렌더링된 아티팩트 2개
- PNG 파일 1개
- SVG 소스 파일 1개
- 누락된 README 이미지 링크 없음
- README 파일에 로컬 SVG 이미지를 삽입한 사례 없음
- 남아 있는 Mermaid 코드 블록 없음

## 검증

- `node /Users/debop/work/bluetape4k/.omx/scripts/refine-readme-diagrams.mjs .`
- README 이미지 링크 및 Mermaid 잔여물 검사
- PNG/SVG 형태 검사
- 시각 이미지 검토
- `git diff --check`

## 향후 지침

밀도가 높은 의존성 다이어그램에서는 균일한 그리드나 저장소 전체의 고정 이미지
크기를 강제하기보다 읽기 쉬운 레이블과 올바른 화살표 기하를 우선한다.
