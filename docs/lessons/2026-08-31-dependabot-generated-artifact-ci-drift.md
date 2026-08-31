# Dependabot 변경과 generated artifact CI drift

## 배경

Dependabot PR #220은 `gradle/libs.versions.toml`의 Kotlin benchmark 버전을 갱신했고,
PR #221은 CI workflow의 `actions/setup-java` major version을 올렸다. 두 PR 모두 각
변경의 원본 파일만 수정한 채 병합되어 `develop`의 `Build BOM` 검증이 실패했다.

## 원인

- catalog 변경 뒤 `libs.versions.toml.sha256`, latest-stable inventory, audit를 함께
  재생성하지 않아 provenance chain이 이전 catalog를 가리켰다.
- workflow가 `actions/setup-java@v6.0.0`을 사용하지만 CI policy test는 여전히
  `actions/setup-java@v5`를 요구했다.
- aggregate `CI Status` 실패는 별도 결함이 아니라 위 `Build BOM` 실패의 결과였다.

## 결정

catalog source가 바뀌면 checksum과 inventory를 같은 변경에서 재생성하고 audit의
catalog/inventory 연결과 영향받은 current line을 함께 재기준화한다. historical audit의
전체 metadata refresh는 별도 report regeneration 범위이므로 이 복구에 섞지 않는다.
GitHub Action version을 올릴 때는 workflow와 policy test가 같은 major line을 검증하도록
함께 갱신한다. exact patch version 대신 major line을 검사해 Dependabot의 patch update를
허용한다.

## 검증

수정 전에는 checksum, inventory, `setup-java` policy test가 각각 실패했다. 수정 후 동일한
세 테스트가 통과했고, Python test는 `301`개를 실행해 `299`개가 통과했으며 Maven snapshot
조회 `403`에 따른 `2`개만 명시적으로 skip됐다. catalog audit는 authority `515`,
line `549`, current `449`, `adopt-latest` 후보 `0`을 유지했다. managed artifact `183`개
검증과 Gradle build도 통과했다.

## 재발 방지

Dependabot PR 검토 시 원본 파일뿐 아니라 저장소가 관리하는 generated provenance와
policy test의 연동 여부를 확인한다. historical audit를 갱신할 때는 record 전체 refresh가
별도 dependency adoption 범위를 흡수하지 않는지도 확인한다. 이 검증이 빠진 PR은 base
branch CI를 깨뜨리므로 후속 PR에 섞지 않고 prerequisite fix로 먼저 복구한다.
