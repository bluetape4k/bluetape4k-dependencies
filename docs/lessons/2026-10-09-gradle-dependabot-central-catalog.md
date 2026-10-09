# Gradle Dependabot과 중앙 catalog 소유권

## 배경

`bluetape4k-exposed` 이슈 #885는 같은 `develop` SHA에서 dependency submission이 성공한 직후 Dependabot 보안 업데이트가 `dependency_not_found`로 실패한 사례다. 실패한 updater payload에는 9개 좌표가 있었다. 제출 SBOM에는 여러 좌표의 오래된 plugin classpath 버전과 중앙 catalog에서 관리하는 패치 버전이 함께 보였지만, LZ4는 아직 1.11.2였다. LZ4 catalog alias를 직접 쓰는 저장소는 6곳이며, 현재 열린 중앙 catalog 소비자 변경 9곳은 모두 같은 불변 catalog SHA를 참조해야 한다.

## 원인

Exposed `settings.gradle.kts`는 중앙 catalog를 SHA로 고정해 `raw.githubusercontent.com`에서 가져온 뒤, 저장소에 체크인되지 않는 `.gradle/bluetape4k-dependencies/.../libs.versions.toml`에서 `bt4k` version catalog를 읽는다. 같은 SHA의 dependency submission은 1,283개 좌표가 든 SBOM을 업로드했고, 뒤이은 Dependabot updater는 별도 의존성 기준 데이터에서 9개 좌표를 찾지 못했다. 두 run 사이의 시간 차이는 22초였지만, 로그에는 manifest parsing에서 실패한 것으로 나타나므로 단순 제출 지연으로 결론내리지 않는다. GitHub 문서는 Gradle security update가 수동 제출 graph에 의존하며, Dependabot version update가 PR을 만들려면 부모 의존성이 manifest에 직접 선언되어야 한다고 설명한다. 또한 지원되는 Gradle 입력은 체크인된 build 파일, 표준 `gradle/libs.versions.toml`, lockfile 등이다. 이 저장소가 런타임에 내려받아 `.gradle` 아래서 불러오는 외부 catalog는 updater가 직접 편집할 수 있는 manifest가 아니므로, 업로드 graph와 편집 가능한 선언의 불일치가 `Job dependencies not found in the dependency snapshot` 오류를 일으킨 것으로 판단한다. 이 설명은 동일 SHA의 성공·실패 run, 제출 SBOM과 GitHub Gradle 지원 계약을 결합한 원인 분석이다. 실패 payload의 좌표는 `at.yawk.lz4:lz4-java`, `com.fasterxml.jackson.core:jackson-core`, `com.fasterxml.jackson.core:jackson-databind`, `org.bouncycastle:bcprov-jdk18on`, `org.freemarker:freemarker`, `org.jsoup:jsoup`, `org.mariadb.jdbc:mariadb-java-client`, `tools.jackson.core:jackson-core`, `tools.jackson.core:jackson-databind`였다.

Dependabot 경고를 제출 SBOM과 중앙 catalog에 대조했다. catalog가 직접 관리하는 좌표는 이미 패치 버전 이상인 경우가 많았지만, SBOM에는 Dokka, Flyway, Exposed 및 기타 Gradle plugin classpath가 불러온 취약한 구버전도 별도로 남아 있었다. `at.yawk.lz4:lz4-java` catalog alias만 1.11.2로 패치 기준보다 낮아 1.12.0으로 올렸다. checksum, inventory, audit, delta를 함께 갱신했다. catalog alias 갱신만으로 plugin classpath의 모든 전이 버전이 바뀐다고 가정하지 않는다.

## 결정

공유 라이브러리 버전은 중앙 저장소에서 먼저 수정하고 각 소비 저장소는 정확한 catalog SHA를 참조한다. 중앙 소유로 분류한 좌표는 기존 ignore generator로 leaf 저장소 설정에 반영한다. GitHub 문서상 `ignore`는 일반 버전 업데이트와 보안 업데이트 모두를 제외하므로, 이 정책은 central team이 해당 좌표의 alert를 추적하고 catalog 또는 상위 plugin을 갱신한다는 운영 책임을 함께 둔다. 외부 catalog가 plugin classpath 전이를 직접 제어하지 않는 경우에는 해당 제한을 별도 기록하고 무시 상태를 해소된 alert로 취급하지 않는다.

Exposed에는 Gradle entry를 추가해 제출된 그래프를 유지하고, `open-pull-requests-limit: 0`으로 일반 Gradle 버전 업데이트 PR을 끈다. 이 한도는 보안 업데이트 PR 한도가 아니므로 보안 업데이트 경로를 막는 근거로 사용하지 않는다. `target-branch`는 지정하지 않아 보안 업데이트 동작이 바뀌지 않게 한다. GitHub Actions entry는 그대로 유지한다.

## 결과

중앙 catalog 후보는 LZ4를 1.12.0으로 고정했다. LZ4를 직접 사용하는 Exposed, Projects, Experimental, Graph, JaVers, Leader 6곳과 현재 열린 catalog 소비자 변경 9곳의 범위를 구분해 기록했다. 중앙 ignore generator는 중앙 소유 목록을 생성하고 Exposed 설정 후보는 Gradle 및 GitHub Actions 항목을 보존한다. 이는 해당 패키지의 보안 alert가 사라졌다는 뜻이 아니므로, 중앙 catalog와 plugin graph를 계속 확인한다.

## 검증

- Dependency submission run `37914457800`과 Dependabot Updates run `37914573273`은 모두 `a12896750f3130841ac4cf142fc63e438228312d` SHA를 사용했다. 첫 run은 manifest `settings.gradle.kts`의 1,283개 resolved 좌표를 제출했고 성공했지만, 22초 뒤 시작한 security updater는 같은 SHA에서 실패했다.
- 실패한 보안 job의 updater payload에는 서로 다른 9개 좌표가 있었고 `ignore-conditions`는 비어 있었다. 제출 SBOM에는 구버전과 패치 버전이 함께 있었으며, 여러 구버전은 Gradle plugin classpath에서 유입됐다. 로그는 9개 모두 `Job dependencies not found in the dependency snapshot`으로 보고했다. 새 Gradle ignore 설정이 해당 updater 실행을 통과시키는지, 보안 alert가 계속 남는지는 원격 통합 후 별도로 확인해야 한다.
- ignore generator 테스트는 변경 전 RED 두 건을 확인한 뒤 변경 후 13/13 통과했다. 관련 중앙 Python 테스트 67개, catalog audit/checksum check, 중앙 Gradle build도 통과했다. 이 evidence는 현재 로컬 중앙 후보에 대한 것이며 아직 GitHub 원격에서 실행하지 않았다.
- 공식 Maven Central metadata에서 1.12.0을 확인했고 SHA-256은 `3c49b392085b9101077f67020a871cab5a90994ea9c49013012497fe9d80fbe2`였다.
- Exposed 설정은 YAML로 읽었으며 Gradle PR 한도 `0`, `target-branch` 미지정, GitHub Actions 항목 보존을 확인했다.
- LZ4 `dependencyInsight`는 `1.12.0`을 선택했고, `CompressedBlobColumnTypeTest`는 H2/PostgreSQL/MySQL에서 6/6 통과했다. `:bluetape4k-exposed-core:test`는 287개 통과, 13개 대기, UUID v7 millisecond timestamp 동등성 1건 실패였다. 이 테스트를 분리 재실행하자 세 DB에서 3/3 통과했지만 전체 suite를 깨끗한 상태로 다시 통과시킨 것은 아니다. 이 타이밍성 실패는 LZ4 변경 범위와 분리해 기록한다.
- 중앙 PR #258의 CI run `37935913572`는 두 검증을 실패했다. `Verify catalog scripts`는 검증 대기 ledger cutoff가 `2026-10-07`이라고 고정한 테스트 때문에 실패했다. 실제 ledger와 audit evidence는 `2026-10-09`였고, 현재 pending delta에는 `at-yawk-lz4`만 있으므로 테스트의 날짜와 예상 키 집합을 갱신했다.
- 같은 CI run의 publication POM 검증은 2026-09-08/09에 고정된 publisher commit들을 사용해 실패했다. Projects의 오래된 commit `d6e4a8be...`로 생성한 82개 POM에서 256개의 중복 dependency-management 항목을 재현했고, `idgenerators` POM에서 CI와 같은 `reactor-bom`, `kotlin-stdlib`, `kotlin-reflect` 중복을 확인했다. 검증을 약화하지 않고 `config/catalog-publisher-repository-refs.json`을 현재 소비자 후보의 정확한 SHA로 갱신했다.
- 수정 후 영향 범위 Python 테스트 35개와 latest-stable audit/checksum 검사가 통과했다. Python 3.13 전체 suite는 477개 중 475개가 통과했고 2개 workspace 통합 테스트는 실패했다. 실패는 이 개발 workspace에 존재하는 sibling checkout들을 직접 읽는 검사에서 나왔다. `test_real_workspace_has_approved_hard_coded_candidate_baseline`은 9 대신 16개를 보고했고, `test_real_workspace_has_no_downstream_explicit_external_authority`는 Graph checkout의 명시 authority 2건을 보고했다. 이 검사는 테스트 코드 변경과 무관한 현재 로컬 checkout 상태에 의존하므로 전체 suite는 완전 통과로 기록하지 않는다. 기본 Python 3.9에서는 `tomllib`가 없어 해당 전체 실행을 검증 근거로 쓰지 않았다.
- 최신 소비자 후보 SHA를 고정한 map `a16d6692435d6733c5f9b431dc748199f1e00991de1bc32f0152e41254c12ff5`로 publisher 검증을 재실행했다. 9개 저장소, POM 192개, 의존성 50,518개, Maven effective model 192개가 검사됐고 `failures=0`이었다.
- 검증 시점에 GitHub PR #258은 기존 head `ef161acbdbad93376ce01846c646cf1d15e8d7c9`에서 계속 열려 있었으므로, 위 결과는 수정된 로컬 후보의 검증이다. 새 head를 push하고 hosted CI를 다시 실행하기 전까지 원격 CI 통과나 #885 완료를 주장하지 않는다. consumer dependency submission, Dependabot 재실행 및 남은 보안 alert 조회도 중앙 catalog 변경이 병합된 뒤 확인해야 한다.

## 재발 방지

Dependabot 문제를 조사할 때 dependency submission과 updater run의 상태를 따로 확인한다. 실패 좌표를 라이브 Dependabot alert와 중앙 catalog에 대조하고, 중앙 버전을 먼저 수정한다. 소비자 `settings.gradle.kts`와 CI pin을 바꿀 때는 central `snapshot-catalog-ref-overrides`와 계약 테스트도 같은 exact SHA로 갱신하고, 중앙 원격에서 해당 SHA를 fetch할 수 있는지 확인한다. 그 뒤 실제 Dependabot 실행 결과와 보안 경고를 다시 조회한다. 검증 인벤토리의 기존 저장소 소유 metadata가 누락되면 임의로 issue/review를 만들어 채우지 말고 해당 catalog promotion 경로를 보류한다.

## 출처

- [GitHub Gradle 지원](https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories#gradle)
- [Dependabot ignore 동작](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/manage-your-dependency-security/controlling-dependencies-updated)
- [Dependency submission API](https://docs.github.com/en/rest/dependency-graph/dependency-submission)
- [Security updates 설정](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configure-security-updates)
- [open-pull-requests-limit](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference#open-pull-requests-limit)
- [LZ4 Maven Central metadata](https://repo.maven.apache.org/maven2/at/yawk/lz4/lz4-java/maven-metadata.xml)
