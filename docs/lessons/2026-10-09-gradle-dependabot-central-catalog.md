# Gradle Dependabot과 중앙 catalog 소유권

## 배경

`bluetape4k-exposed` 이슈 #885는 Dependabot dependency submission이 성공한 같은 `develop` SHA에서도 보안 업데이트가 `dependency_not_found`로 실패한 사례다. Exposed는 버전을 `bluetape4k-dependencies` catalog에서 가져오며, 같은 catalog를 직접 쓰는 6개 소비 저장소의 LZ4 좌표도 함께 확인해야 했다.

## 원인

Exposed `settings.gradle.kts`는 중앙 catalog를 SHA로 고정해 `raw.githubusercontent.com`에서 내려받고, 체크인되지 않는 `.gradle/bluetape4k-dependencies/.../libs.versions.toml` 파일을 `bt4k` version catalog로 불러온다. Gradle이 이 설정을 실행하는 dependency submission은 성공했지만, 같은 SHA의 Dependabot security job에는 9개 alert 좌표가 전달됐고 `ignore-conditions`는 비어 있었다. updater는 `Job dependencies not found in the dependency snapshot` 오류로 종료했다. 이 증거는 실행된 Gradle graph와 updater가 편집 대상으로 인식하는 manifest가 맞물리지 않는다는 점을 보여준다. 중앙 catalog 의존성을 Dependabot이 직접 고치게 하는 대신, leaf 설정에서 중앙 소유 좌표를 제외하고 catalog 변경 뒤 소비자의 SHA를 갱신하는 것이 이 경계에 맞는 대응이다. 새 ignore 설정이 실제 security job을 통과시키는지는 원격 통합 후 live run으로 확인해야 한다.

Dependabot 경고의 중앙 catalog 대조 결과, jsoup, Jackson 2/3, FreeMarker, Bouncy Castle, MariaDB Connector는 이미 고정 catalog에서 패치 버전 이상이었다. `at.yawk.lz4:lz4-java`만 1.11.2로 패치 기준보다 낮았다. 중앙 catalog를 Maven Central의 당시 최신 안정 버전 1.12.0으로 올리고 checksum, inventory, audit, delta를 재생성했다.

## 결정

공유 라이브러리 버전은 중앙 저장소에서 먼저 수정하고 각 소비 저장소는 정확한 catalog SHA를 참조한다. 중앙에서 소유하는 좌표는 기존 ignore generator를 통해 leaf 저장소 Dependabot 설정에 반영하되, 업데이트 담당자가 중앙 버전을 먼저 고칠 수 있도록 한다. GitHub 문서상 `ignore` 규칙은 일반 버전 업데이트와 보안 업데이트 모두에 적용되므로, 중앙 보안 수정과 다운스트림 동기화를 분리해서 검증한다.

Exposed에는 Gradle entry를 추가해 제출된 그래프를 유지하고, `open-pull-requests-limit: 0`으로 일반 Gradle 버전 업데이트 PR을 끈다. 이 한도는 보안 업데이트 PR 한도가 아니므로 보안 업데이트 경로를 막는 근거로 사용하지 않는다. `target-branch`는 지정하지 않아 보안 업데이트 동작이 바뀌지 않게 한다. GitHub Actions entry는 그대로 유지한다.

## 결과

중앙 catalog 후보는 LZ4를 1.12.0으로 고정했고, 직접 사용하는 Exposed, Projects, Experimental, Graph, JaVers, Leader를 영향 범위로 기록했다. 중앙 ignore generator는 실패 로그에서 확인한 LZ4, jsoup, MariaDB 좌표를 중앙 소유 목록에 포함한다. Exposed 설정 후보는 Gradle과 GitHub Actions 업데이트 항목을 함께 보존한다.

## 검증

- Dependency submission run `37914457800`과 Dependabot Updates run `37914573273`은 모두 `a12896750f3130841ac4cf142fc63e438228312d` SHA를 사용했다. 제출은 성공했지만, 바로 뒤의 security job은 실패했다.
- 실패한 보안 job의 updater payload에는 서로 다른 9개 좌표가 있었고 `ignore-conditions`는 비어 있었다. 로그는 9개 모두 `Job dependencies not found in the dependency snapshot`으로 보고했다. 새 Gradle ignore 설정이 이 payload를 바꾸는지, 그리고 보안 업데이트 실행이 오류 없이 끝나는지는 아직 live로 검증하지 않았다.
- ignore generator 테스트는 변경 전 RED 두 건을 확인한 뒤 변경 후 13/13 통과했다. 관련 중앙 Python 테스트 67개, catalog audit/checksum check, 중앙 Gradle build도 통과했다.
- 공식 Maven Central metadata에서 1.12.0을 확인했고 SHA-256은 `3c49b392085b9101077f67020a871cab5a90994ea9c49013012497fe9d80fbe2`였다.
- Exposed 설정은 YAML로 읽었으며 Gradle PR 한도 `0`, `target-branch` 미지정, GitHub Actions 항목 보존을 확인했다.
- LZ4 `dependencyInsight`는 `1.12.0`을 선택했고, `CompressedBlobColumnTypeTest`는 H2/PostgreSQL/MySQL에서 6/6 통과했다. `:bluetape4k-exposed-core:test`는 287개 통과, 13개 대기, UUID v7 millisecond timestamp 동등성 1건 실패였다. 이 테스트를 분리 재실행하자 세 DB에서 3/3 통과했지만 전체 suite를 깨끗한 상태로 다시 통과시킨 것은 아니다. 이 타이밍성 실패는 LZ4 변경 범위와 분리해 기록한다.
- 중앙 후보의 9개 publisher POM 검증과 6개 소비 저장소의 정확한 중앙 SHA 해석은 아직 끝나지 않았다. 중앙 후보가 원격 통합된 뒤 새 Dependabot 실행과 경고 재조회가 필요하다. 따라서 이 기록은 #885 완료를 주장하지 않는다.

## 재발 방지

Dependabot 문제를 조사할 때 dependency submission과 updater run의 상태를 따로 확인한다. 실패 좌표를 라이브 Dependabot alert와 중앙 catalog에 대조하고, 중앙 버전을 먼저 수정한다. 다음으로 정확한 catalog SHA를 소비자에게 동기화하고, 실제 Dependabot 실행 결과와 보안 경고를 다시 조회한다. 검증 인벤토리의 기존 저장소 소유 metadata가 누락되면 임의로 issue/review를 만들어 채우지 말고 해당 catalog promotion 경로를 보류한다.

## 출처

- [GitHub Gradle 지원](https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories#gradle)
- [Dependabot ignore 동작](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/manage-your-dependency-security/controlling-dependencies-updated)
- [Security updates 설정](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configure-security-updates)
- [open-pull-requests-limit](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference#open-pull-requests-limit)
- [LZ4 Maven Central metadata](https://repo.maven.apache.org/maven2/at/yawk/lz4/lz4-java/maven-metadata.xml)
