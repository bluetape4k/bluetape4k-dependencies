# Kotlin 2.4.10과 Detekt preview/legacy 라인을 분리한다

## 배경

중앙 catalog의 Kotlin compiler/plugin을 `2.4.10`으로 올리고, 신규
`dev.detekt` plugin을 `2.0.0-alpha.6`으로 전환하는 Issue #189를 검증했다.

## 발견

- `dev.detekt` plugin과 `dev.detekt:detekt-rules-ktlint-wrapper`는 alpha.6 metadata를
  제공한다.
- `io.gitlab.arturbosch.detekt`와 `io.gitlab.arturbosch.detekt:detekt-formatting`은
  Maven Central에서 `1.23.8`이 최신 공개 호환 라인이다. 레거시 group에 alpha.6을
  기록하면 해석 불가능한 좌표가 된다.
- Kotlin 2.4.10은 최신 안정 감사에서 current지만 Detekt alpha.6은 preview-only라서
  stable delta ledger에 허위 검증 항목으로 넣을 수 없다.
- Leader의 전체 aggregate Detekt 실패는 후보 catalog와 무관하게 기준 catalog에서도
  발생하는 기존 `detektProductionSourceGuard` script receiver 오류였다. 모듈 task는
  후보 catalog에서 성공했다.

## 결정

중앙 source of truth에서는 신규 Detekt 좌표와 레거시 호환 좌표를 별도 유지한다.
`kotlin20=2.0.21`도 보존하여 legacy Detekt와 ABI/fixture 경계를 유지한다. Preview
라인의 채택 근거는 이 체크리스트와 canary/POM 결과에 기록하되, stable delta ledger에는
실제 resolved-graph 증거가 생길 때까지 추가하지 않는다.

## 재사용 규칙

다음 catalog train에서도 버전 숫자만 맞추지 말고 group/plugin 좌표의 공개 metadata를
먼저 확인한다. Preview plugin이 안정 버전 감사에 들어가지 않는 것은 실패가 아니라
명시적인 adoption 보류 상태이며, 레거시 consumer가 있는 경우 별도 canary를 실행한다.
