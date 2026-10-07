# 중앙 BOM import는 개수와 catalog 버전까지 검증한다

## 배경

`verify-publication-poms.py`는 versioned imported BOM의 존재를 Maven dependency
management 예비 검사로 사용한다. 기존 검사는 요구된 Jackson BOM coordinate가
있기만 하면 통과했으므로, 기대 버전 `2.22.3`에 오래된 중복 버전 `2.22.2`가
함께 있는 central BOM도 오류 없이 통과했다.

## 결정

중앙 catalog가 관리하는 필수 BOM coordinate마다 generated central BOM에 import가
정확히 하나 있어야 하며, 그 버전은 catalog의 `version.ref` 값과 일치해야 한다.
이 구조 검사는 Maven effective-model 검증을 대체하지 않는다. 두 검사를 함께
실행해 중복·오래된 import와 실제 Maven 관리 범위 누락을 모두 찾는다.

## 결과와 재발 방지

`jackson2-bom` 및 `jackson3-bom` alias에서 module과 version을 읽고, 생성된
`bluetape4k-dependencies` POM의 import 개수와 catalog 버전을 비교한다. 회귀
테스트는 누락, 오래된 버전, 기대 버전과 stale 중복의 공존, 올바른 단일 import를
각각 검증한다. 새 BOM을 추가할 때는 alias, published platform import, exact
cardinality/version 검사를 같은 변경에 추가한다.

수정 전 RED 관찰은 올바른 Jackson 2 버전과 stale 중복 버전이 함께 있을 때
감사 결과가 `errors=0`이었다. 수정 후 targeted Python suite 54개가 통과했다.
생성한 central POM 1개에는 dependency 88개가 있었고 구조 감사 오류 0건 및
Maven effective model 성공을 확인했다. 전체 9 publisher 검증은 현재 exact
candidate map을 새로 만든 뒤 별도 gate에서 수행한다.

관련 구현과 회귀 테스트는 `scripts/verify-publication-poms.py`,
`tests/test_verify_publication_poms.py`, `tests/test_ci_catalog_governance.py`에
있다. 일반적인 Maven POM 생성/effective-model 기준은
`docs/lessons/2026-07-17-cross-repo-publication-pom-gate.md`를 따른다.
