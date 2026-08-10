# 이슈 #182 라이브러리 빌드 표준 wave

## 결정

`bluetape4k-projects#1326`에서 먼저 검증한 Kotlin 2.4.10, Kotlin language/API 2.4,
JDK 25, Gradle 9.7.0 기준을 나머지 `bluetape4k-*` 라이브러리 저장소에 같은
계약으로 전파한다. Detekt는 제거하지 않고 저장소별 현재 정적 분석 계약과
호환되는 경로를 유지한다.

이번 wave의 라이브러리 범위는 다음과 같다.

- `bluetape4k-aws`
- `bluetape4k-experimental`
- `bluetape4k-exposed`
- `bluetape4k-graph`
- `bluetape4k-image`
- `bluetape4k-javers`
- `bluetape4k-leader`
- `bluetape4k-text`

`bluetape4k-projects`는 PR #1326이 이미 병합되어 기준 구현으로 사용한다.

## 예제 저장소 연기

다음 저장소는 이 wave에서 변경하지 않는다.

- `bluetape4k-workshop`
- `exposed-workshop`
- `exposed-r2dbc-workshop`
- `clinic-appointment`
- `timefold-workshop`

이 저장소들은 `bluetape4k-dependencies`의 다음 배포인 `1.5.0` 시점에 각 저장소의
소유자가 별도 변경한다. 따라서 이번 issue의 구현·검증·PR 범위에 포함하지 않으며,
예제 저장소의 현재 Kotlin/JDK/Gradle 설정을 이 wave의 성공 조건으로 사용하지 않는다.

## 기준 구현에서 보존할 계약

- root compiler 설정은 Kotlin language/API 2.4와 JDK 25 toolchain/target을 명시한다.
- Java compile release와 Kotlin JVM target은 25로 정렬하고, `.java-version`과 CI
  setup도 JDK 25를 사용한다.
- Gradle wrapper와 SHA-256 sidecar는 9.7.0으로 정렬한다.
- CodeQL 및 dependency-submission workflow는 JDK 25 실행 계약을 따르며,
  catalog pin 단계가 더 이상 Kotlin 2.4.0을 2.3.21로 치환하지 않도록 갱신한다.
- Java 21 compatibility island 또는 provider/runtime 선택처럼 저장소별 실행 제약은
  전체 toolchain 전환으로 삭제하지 않고 dependency closure와 테스트로 보존한다.

## 검증 경계

각 라이브러리 저장소의 build, 정적 분석, workflow 설정, publication POM을 저장소별
PR에서 확인한다. 예제 저장소는 `1.5.0` 배포 wave에서 별도 검증한다.
