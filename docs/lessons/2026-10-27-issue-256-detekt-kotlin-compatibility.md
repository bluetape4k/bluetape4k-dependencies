# Detekt alpha.6과 Kotlin 2.4.x의 compiler 경계

## 배경

Issue [#256](https://github.com/bluetape4k/bluetape4k-dependencies/issues/256)은
중앙 catalog의 Kotlin `2.4.x` train과 `dev.detekt` `2.0.0-alpha.6`을 함께
적용할 때 Detekt configuration classpath가 다른 Kotlin compiler 버전을
사용하는 문제를 추적한다. 현재 중앙 catalog의 제품 Kotlin은 `2.4.21`이고,
기존 Leader canary는 Kotlin `2.4.20`에서 같은 `detekt-dev` 버전을 사용했다.

## 결정 또는 발견

- Detekt `2.0.0-alpha.6` 릴리스는 Kotlin `2.4.10`으로 빌드됐다고
  명시한다. [alpha.6 릴리스 노트](https://github.com/detekt/detekt/releases/tag/v2.0.0-alpha.6)와
  [호환성 표](https://detekt.dev/docs/introduction/compatibility/)를 기준 정보로
  사용한다.
- alpha.6의 Gradle plugin source는
  [`getSupportedKotlinVersion()`](https://github.com/detekt/detekt/blob/v2.0.0-alpha.6/detekt-gradle-plugin/src/main/kotlin/dev/detekt/gradle/plugin/DetektPlugin.kt#L194-L195)를
  제공한다. Spring dependency-management와 함께 사용할 때의 configuration
  override 패턴은 [Detekt 호환성 이슈 #6198](https://github.com/detekt/detekt/issues/6198)을
  근거로 삼는다.
- 제품 compile classpath를 Kotlin `2.4.10`으로 되돌리면 안정 버전과 보안
  업데이트를 취소하므로 중앙 Kotlin line을 낮추지 않는다.
- Detekt plugin이 제공하는
  `dev.detekt.gradle.plugin.getSupportedKotlinVersion()`으로 `detekt`
  configuration만 plugin 지원 compiler에 맞춘다. 제품 소스와 일반 Kotlin
  dependency에는 중앙 Kotlin line을 유지한다.
- 중앙 catalog에는 이 경계를 주석으로 명시하고 checksum sidecar를 갱신한다.
  `detekt-dev` 버전 자체를 임의로 올리거나 compatibility line을 복제하지
  않는다.

## Consumer inventory와 실제 canary

문자열 guard만으로는 소비자 build에서 resolver가 제거된 상태를 감지할 수
없으므로 `config/detekt-kotlin-compatibility-consumers.json`에 consumer를
`active`와 `root_only`로 나눠 기록한다. 다음 명령은 inventory의 Gradle
source를 읽고, active consumer의 `detekt` configuration dependency report와
root-only consumer의 `detekt NO-SOURCE` task를 실제로 실행한다.

```bash
python3 scripts/verify-detekt-kotlin-compatibility.py \
  --workspace /path/to/bluetape4k \
  --catalog /path/to/bluetape4k-dependencies/gradle/libs.versions.toml \
  --run-gradle --json
```

현재 checkout에서는 `consumer_count=13`, `failed_repositories=[]`로
끝났다. 중앙 catalog를 주입한 AWS, Text, Leader, Projects, Exposed, Graph,
Javers의 7개 probe가 모두 `dev.detekt:detekt-cli:2.0.0-alpha.6`와
`org.jetbrains.kotlin:kotlin-compiler:2.4.10`을 해석했다. Workshop, Clinic,
Exposed Workshop의 local-catalog probe도 같은 compiler line을 확인했다.
Image, Experimental, Exposed R2DBC Workshop의 3개 root-only probe는 모두
`Task :detekt NO-SOURCE`와 `BUILD SUCCESSFUL`을 반환했다.

검증기는 dependency report에 요청 좌표가 포함됐는지만 검사하지 않는다.
Gradle이 출력하는 `requested -> selected` 형식과 `{strictly ...} -> ...`
형식의 오른쪽 선택 버전을 읽어 예상 compiler와 일치하는지 확인한다. 예를
들어 `kotlin-compiler:2.4.10 -> 2.4.21`은 실패하며, 선택 결과가 실제로
`2.4.10`인 경우에만 통과한다. 이 충돌 회귀 테스트는
`tests/test_detekt_kotlin_compatibility.py`에 보존한다.

AWS 전체 `./gradlew detekt`는 compatibility resolution과 별개로 기존
`bluetape4k-aws-ktor`의 Detekt 28개 분석 이슈 때문에 실패했다. 따라서 이
canary는 source findings의 통과를 주장하지 않고, `detekt` configuration의
compiler resolution을 검증하는 dependency report를 증거로 사용한다.

## 소비자 범위 점검

2026-10-27 기준으로 `dev.detekt`를 실제 subproject에 적용하는 AWS, Text,
Leader, Projects, Exposed, Graph, Javers, `clinic-appointment`,
`exposed-workshop`은 모두 `getSupportedKotlinVersion()` resolver를 갖는다.
`bluetape4k-workshop`도 root resolver를 갖는다.

`bluetape4k-image`, `bluetape4k-experimental`, `exposed-r2dbc-workshop`은
root에만 Detekt plugin을 선언하고 현재 `./gradlew detekt`가 `NO-SOURCE`로
끝난다. 이 세 consumer는 아직 source analysis를 실행하지 않으므로 resolver
적용 여부를 완료로 판정하지 않는다. 향후 subproject에 Detekt를 적용하거나
source set을 추가할 때는 같은 configuration resolver를 먼저 추가하고,
개별 저장소의 변경과 canary를 이 이슈의 후속 증거로 등록해야 한다.

## 결과

`gradle/libs.versions.toml`은 Detekt plugin의 compiler 경계와 consumer 적용
규칙을 설명한다. `gradle/libs.versions.toml.sha256`은 새 catalog 바이트를
가리키도록 다시 계산했다. 이미 병합된 AWS #664, Text #345, Leader #965와
기존 Projects/Exposed/Graph/Javers consumer override가 이 규칙을 적용한다.

## 재현 가능한 검증

- 변경 전 호환성 계약 guard는 `getSupportedKotlinVersion()` 선언이 없어 RED가
  됐다. 다음 명령으로 같은 guard를 재현할 수 있다.

  ```bash
  python3 - <<'PY'
  from pathlib import Path

  catalog = Path("gradle/libs.versions.toml").read_text(encoding="utf-8")
  assert 'detekt-dev = "2.0.0-alpha.6"' in catalog
  assert "getSupportedKotlinVersion()" in catalog
  print("PASS: central Detekt/Kotlin compatibility contract")
  PY
  ```

- 변경 후 guard, catalog checksum, central sync, publication POM, Gradle build를
  순서대로 재실행했다. guard와 checksum은 통과했고, `sync-shared-versions`만
  기존 Projects 중복 7건으로 실패했다.
- consumer inventory 정적 guard와 13개 실제 canary를 추가로 실행했다. 이
  결과는 catalog/comment 문자열이 아니라 consumer Gradle resolution과
  root-only 경계를 직접 확인한다.
- Leader의 full Nightly backend matrix와 새 원격 immutable catalog ref는
  중앙 commit이 원격에 게시된 뒤 별도 canary에서 확인해야 한다. 현재 일일
  Nightly의 skipped backend jobs를 완료 증거로 사용하지 않는다.

## 향후 지침

Detekt 또는 Kotlin compiler를 올릴 때 먼저 공식 호환성 표와 plugin의 지원
resolver를 확인한다. 제품 Kotlin 버전과 Detekt configuration Kotlin 버전을
하나의 중앙 version ref로 강제하지 말고, consumer build에서 `detekt`
configuration에만 지원 버전을 적용한다. 새 catalog ref를 downstream에 고정할
때는 exact commit, sidecar checksum, consumer canary, full Nightly matrix를
각각 다시 읽고 검증한다. 위의 세 root-only consumer가 source analysis를
시작하는 변경을 받을 때까지 Issue #256은 완료 상태로 닫지 않는다.
