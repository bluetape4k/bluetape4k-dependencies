# README 다이어그램 인포그래픽

## 배경

README 파일은 아키텍처, 클래스, 시퀀스, ERD 및 기타 다이어그램에 Mermaid 코드
블록을 사용했다. 워크스페이스 전체의 시각화 방향이 검토된 파스텔 인포그래픽 PNG로
변경되었으며, 재사용을 위해 SVG 소스 자산을 함께 보관한다.

## 결정

README의 Mermaid 블록을 생성된 PNG 이미지 링크로 교체하고, 일치하는 SVG 소스를
PNG 파일 옆에 저장한다. 다이어그램 텍스트는 영어만 사용하고, 큰 레이블에는
Architects Daughter를, 세부 텍스트에는 Comic Mono를 사용한다. 아키텍처, 클래스,
시퀀스, ERD 다이어그램에는 각각에 맞는 레이아웃을 적용한다.

## 결과

`bluetape4k.github.io/docs/readme-diagram-samples`의 공용 2026-05-19 스타일
가이드에 따라 README 다이어그램을 렌더링했다. 루트 README 자산은 저장소에 로컬
자산 배치 규칙이 있으면 해당 규칙을 따른다.

## 검증

저장소 간 변환 과정에서 rsvg-convert로 PNG/SVG 자산을 생성하고 README 링크를
확인했다.

## 향후 지침

README 다이어그램은 PNG를 삽입하고 편집용 SVG 소스를 함께 보관한다. 시각적 일관성이
중요한 경우 원시 Mermaid나 단순한 Mermaid 테마 색상 변경으로 되돌리지 않는다.
