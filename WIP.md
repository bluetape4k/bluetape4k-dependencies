# WIP - bluetape4k-dependencies

기준일: 2026-11-25 (KST)
범위: Dependencies `2.2.0-SNAPSHOT` catalog를 같은 immutable ref로 다시 검증·게시하고, 중앙 BOM은 하위 BOM 뒤에 공개한다.

## 2026-11-25 PR #291 병합 및 snapshot 게시 확인

- PR #291은 head `f4a5b58dccb5e6c62f1261179cb12519549a719d`에서 2026-11-24
  13:34:49 UTC에 merge commit `78a2f525c1d12c576f80f2c8f84dbb2fbb942ede`로
  병합됐다. 해당 head의 CI run `45401341780`은 10개 check 모두 성공했다.
- merge commit에서 후속 CI run `45404899275`와 성공한 develop Nightly에 의해
  자동 시작된 Publish Snapshot run `45407764459`가 모두 성공했다. Publish Snapshot은
  같은 merge commit을 게시했다.
- Sonatype Central Portal snapshot 저장소에서 중앙 Dependencies BOM과 8개 하위
  BOM의 snapshot metadata, metadata가 지정한 timestamped POM 및 Gradle `.module`을
  다시 조회해 모두 HTTP 200을 확인했다. 중앙 metadata의 `lastUpdated`는
  `20261124135253`, timestamped POM은
  `2.2.0-20261124.135253-1`이다. 이 artifact들은 POM packaging BOM이므로 JAR을
  요구하지 않는다.
- PR #291의 review submission, inline review comment, issue comment는 각각 0건이다.
  단독 개발자 lane의 인간 리뷰 subgate는 사용자의 지시에 따라
  `N/A (single-developer lane)`으로 기록한다.
- 보정 후보의 `verify_development(..., require_artifacts=True)`와 9개 consumer policy를
  임시 workspace에서 실행해 통과했다. 이 workspace는 공식 `origin/develop`의
  Timefold catalog를 사용했고, 모든 현재 snapshot artifact를 다시 검사했다.
- 실제 로컬 workspace에서 CLI를 실행했을 때 유일한 오류는 Timefold 작업 checkout이
  `fix/nightly-test-dependency-cache` 브랜치의 `2.1.0-SNAPSHOT`을 사용한 점이다.
  해당 checkout의 `origin/develop` catalog는 공식 소비자 버전 `2.1.0`이다. 사용자
  브랜치와 파일은 수정하지 않았다.
- 전체 publication-POM/Maven effective-model gate는 canonical Dependencies checkout의
  기존 사용자 문서 변경 때문에 `publisher repository is dirty: bluetape4k-dependencies`
  로 중단됐다. 이 변경을 보존한다. `sync-shared-versions.py --check`는 Projects의
  7개 `library-coordinate-duplicate` 항목을 보고했으며 이번 PR 1은 version
  catalog를 수정하지 않는다.
- 남은 항목: PR 1 exact-head CI와 전체 publication-POM/Maven effective-model gate.
  snapshot read-back과 임시 workspace 검증은 이 gate들을 대신하지 않는다.

## 2026-11-24 공통 catalog ref 보정 및 snapshot 재게시

안정 기준은 Dependencies/Projects/Exposed `2.1.0`, AWS/Graph/Image/JaVers/Leader/Text
`1.1.0`이다. 내부 게시 저장소의 개발선은 Projects/Exposed `2.2.0-SNAPSHOT`, 나머지
하위 BOM `1.2.0-SNAPSHOT`, 중앙 Dependencies `2.2.0-SNAPSHOT`으로 정렬한다.
공통 catalog는 서명된 tag `catalog/2026-11-24-01`과 commit
`c44ec6c47aa3a8dc3e862dbd7d041eb9d78355f3`으로 고정한다. source의
`snapshotVersion=`은 비워 두고 snapshot workflow가 suffix를 주입한다.

- Workshop/example/application 소비자: 공식 `bluetape4k-dependencies:2.1.0`과
  안정 catalog ref `1669b069690864be8a19a67598e9ac9db807f9f5`를 유지한다.
- 9개 내부 소비자 PR의 Settings/CI ref는 모두 `c44ec6c…`을 사용한다. 마지막 live
  확인에서 Projects #1918은 31/31, AWS #689 20/20, Experimental #110 6/6,
  Exposed #953 42/43, Graph #669 21/21, Image #715 33/34, JaVers #406 17/17,
  Leader #1026 46/46, Text #355 13/13 checks가 성공했다. Exposed와 Image의
  각 1개 `SKIPPED`는 조건부 검사다. 9개 PR 모두 OPEN/CLEAN이고 review submission은
  0건이다. 각 PR은 병합 직전에 정확한 head, CI, review/thread를 다시 읽는다.
- 게시 순서: Projects → Exposed → AWS/Graph/Image/JaVers/Leader/Text를 의존 관계에
  따라 차례로 병합하고 Full Nightly를 실행한다. 성공한 Nightly가 Publish Snapshot을
  자동 실행한다. 8개 하위 BOM의 metadata/POM/GMM과 게시 파일을 확인한 뒤 중앙
  Dependencies snapshot을 마지막에 게시하고 전체 POM 및 하위 저장소 smoke를
  다시 검증한다. Publish Snapshot은 수동 dispatch하지 않는다.
- 2026-11-23에 공개된 child snapshot은 `catalog/2026-11-22-01` 기준이다. 새 공통
  ref의 배포 증거로 재사용하지 않고 새 merge SHA에서 다시 게시한다. 마지막
  read-back에서 8개 child metadata/POM/GMM은 HTTP 200, Dependencies metadata는
  HTTP 404였다.

### Dependencies #291 후보 보정

기존 #291 후보의 `consumer-policy.snapshot-catalog-ref`가 구 catalog SHA
`7a5995f…`를 가리키는 불일치를 발견했다. manifest와 regression test를 새 공통
ref `c44ec6c…`로 맞췄고, README의 중앙 BOM 예시도 게시되지 않은 정식 `2.2.0`에서
`2.2.0-SNAPSHOT`으로 정렬했다. Maven Central에서 Dependencies `2.1.0` POM은
HTTP 200, `2.2.0` POM은 HTTP 404다. 기존 PR #291 head `0d38163`의 10개 check는
PASS했지만 이 수정 전 결과다. 새 exact-head CI와 모든 게시 저장소의 POM 및
effective model 검증이 필요하다.

인라인 코드 리뷰는 검토 범위의 두 P1을 수정하고 P0–P3 미해결 항목이 없음을 확인했다.
독립 아키텍처 검토 attestation은 없다. native architect 재시도는 설치된
`codex-code-mode-host` 경로 부재로 파일을 열기 전에 실패했고, Claude Code는 조직의
subscription 정책으로 실행이 차단됐다. Codex 0.172.0 검토 프로세스는 exact diff를
읽었지만 verdict를 반환하지 않아 중단했다. 사용자는 단독 개발자 lane에서 독립 리뷰를
생략하라고 명시했으므로, 인간 리뷰 subgate와 독립 아키텍처 리뷰는 `N/A`로 처리한다.
기존 인라인 source review는 독립 attestation으로 표시하지 않는다. PR merge 전에는
소비자 저장소 snapshot 재게시, 최신 exact-head CI, POM gate, live review/thread와
mergeability를 확인한다.

Receipt helper를 다룰 때 `--expected-head`에는 Git SHA가 아닌 직전
`mutation-check`의 receipt checksum을 넣고, owner handle은 state root의
`handles/` 바로 아래에서 사용한다. lane/topology 입력 JSON을 helper에 넘기기 전에
검증하고, 30초 startup ACK deadline을 지킨다. 잘못된 입력으로 거부된 명령은
receipt를 바꾸지 않았으며, 미실행 리뷰 예약은 만료 근거를 남겨 취소했다.

## 2026-09-07 예제 저장소 2.1.0-SNAPSHOT 개발선 전환

사용자 결정에 따라 `bluetape4k-workshop`, `clinic-appointment`,
`exposed-r2dbc-workshop`, `exposed-workshop`, `timefold-workshop`을 모두
`bluetape4k-dependencies:2.1.0-SNAPSHOT` 소비자로 분류한다. 기존 2026-09-04
안정 소비자 정책은 이 결정을 기준으로 대체한다.

중앙 verifier는 5개 저장소를 `development-snapshot-repositories`에서 검사하며,
`official-release-repositories`는 빈 목록을 허용한다. 또한 live
`bluetape4k-graph/develop`가 사용하는 catalog ref
`55b5269bddd2bd041d5f282abcd0238dc242c171`을 명시적 override로 고정한다.

2026-09-08 PR #247 CI에서는 signing 고정 커밋의 checkout을 개발선 검사에도
사용해 Graph ref가 불일치했다. signing manifest와 exact repository map은
유지하고, 개발선 검증은 별도 `$RUNNER_TEMP/development-workspace`에서
Publish Snapshot과 같은 후보/develop 선택 정책으로 수행한다. 회귀 테스트는
후보 선택, 404 대체, 403 중단과 signing checkout 보존을 검증한다.

## 2026-09-04 workshop 안정 소비자 정책 정렬

`bluetape4k-workshop`, `exposed-r2dbc-workshop`, `exposed-workshop`,
`clinic-appointment`, `timefold-workshop`은 모두 정식 공개된
`bluetape4k-dependencies:2.0.0` 안정 BOM을 사용한다. 중앙
`config/post-publish-next-development-line.json`에서도 이 5개 저장소를
`official-release-repositories`로 분류하고, `development-snapshot-repositories`는
비워 둔다. `2.1.0-SNAPSHOT`은 내부 라이브러리 저장소의 다음 개발선에만
사용한다.

이번 정렬은 PR #241의 hosted CI가 `bluetape4k-workshop/develop`의 안정
`2.0.0` 소비를 발견한 결과를 반영한다. `exposed-r2dbc-workshop`과
`exposed-workshop`도 동일한 안정 기준으로 재검증한 뒤 중앙 정책과 함께
전환한다.

## 2026-09-04 외부 catalog 최신 안정판 정렬

Maven Central의 authoritative metadata를 2026-09-04T04:40:29Z에 다시
조회해 515개 authority line(이 중 510개 metadata verified)을 감사했다. 그
결과 126개 외부 version key를 최신 안정판이면서 현재 호환선에 맞는 값으로
승격했다. 주요 변경에는 Spring Boot 4.1.1, Jackson 2.22.2/3.2.2,
Exposed 1.5.0, AWS SDK Java 2.54.12, AWS SDK for Kotlin 1.8.46,
Fory 1.7.1, MongoDB driver 5.11.0, gRPC 1.84.0, Micrometer 1.17.1,
Vert.x 4.5.33/5.1.7이 포함된다.

내부 `bluetape4k-*` BOM의 `2.1.0-SNAPSHOT`/`1.1.0-SNAPSHOT` 개발선은
변경하지 않았다. Kotlin 2.4.10, Netty 4.1.136.Final, Kafka 4.2.1 및
Timefold Solver 2.4.0은 각각 승인된 compatibility line, audit selector
제약, 또는 별도 migration 검증이 필요하므로 이번 train에서 보류했다.
Lettuce 7.7.0.RELEASE도 `bluetape4k-leader`의 coroutine `psetex`/`setnx`
호출이 제거되어 compile 오류가 발생하므로 7.6.0.RELEASE를 유지했다.
Avro 1.12.2는 `ClassSecurityValidator`의 stricter trust 정책과 ByteBuffer
serializer 실패 의미 변경으로 `bluetape4k-avro:test` 221개 중 134개가
실패했고, 기준 Avro 1.12.1에서는 동일 테스트가 모두 통과했다. 따라서
adapter migration 전까지 1.12.1을 compatibility hold로 유지한다.
Maven Central에 2.0.62 POM이 없는 `managed-fastjson2-extension-spring6`은
before graph를 재현할 수 없어 별도 alias 제거/migration train으로 보류했다.
`config/latest-stable-version-deltas.json`은 126개 delta와 152개 spec/304개
observation의 resolved graph 증적을 기록한다. 9개 publisher의 POM 188개와
Maven model 188개를 모두 검증했고, 9개 repository `assemble`도 성공했다.
Docker와 central manual checkout을 고정한 뒤 원격 exact HEAD
`0be7daa7a6d98937126486ff4b84a76e416696d6`의 후보 `bluetape4k-projects` 전체
build를 실행했다. `:bluetape4k-lettuce:multiKeyLeasePerformanceTest`의
normalized p95 비율 assertion이 한 번 실패(`13.390084 > 3.6915`)해 전체
build가 중단됐고, 같은 성능 테스트를 후보 catalog에서 3회 재실행한 결과
2회 통과·1회 실패했다. 기준 catalog도 3회 중 2회 통과했으며 나머지 1회는
성능 assertion이 아닌 `:bluetape4k-junit5:compileKotlin`/
`:bluetape4k-core:compileKotlin` 환경 실패였다. 따라서 catalog 버전 회귀가
아닌 성능/환경 flake로 분류하고 Projects [#1630](https://github.com/bluetape4k/bluetape4k-projects/issues/1630)으로 등록했다. 이전 head의
Keycloak readiness 기록은 receipt의 `historical-projects-full-build`에 보존했다.

Graph 전체 build의 AGE PostgreSQL 초기화 EOF는 1회 발생했지만 동일 테스트
3회 재실행은 모두 통과했다. Exposed는 4,934개 실행·230개 skip 뒤 PostgreSQL
test worker가 JDBC handshake에서 9분 정지하고 SIGTERM되어 환경 blocker로
남았다. 이 증거 때문에 9개 downstream full-build 상태는 `PENDING`으로
유지한다. catalog/BOM publication, PR, merge를 포함하지 않는다.

코드 수준에서 확인한 신규 이슈는 Text [#322](https://github.com/bluetape4k/bluetape4k-text/issues/322)의
`containsMatch` 공백 경계 누락과 Graph [#614](https://github.com/bluetape4k/bluetape4k-graph/issues/614)의
GraphML property 타입 손실이다. AWS `outputStreamPartSizeBytes` 후보는 기존
열린 [#615](https://github.com/bluetape4k/bluetape4k-aws/issues/615)와 중복되어
새 이슈를 만들지 않았다.

## 2026-09-02 2.1.0 minor 개발선 전환

`2.0.0` 정식 배포와 8개 내부 BOM의 stable 승격을 완료했다. 다음 개발선은
Projects와 Exposed 및 Dependencies를 `2.1.0`, AWS/Graph/Image/Javers/Leader/Text를
`1.1.0`으로 올린다. source의 `snapshotVersion=`은 비워 두고 snapshot
workflow가 `-SNAPSHOT` suffix를 주입하는 기존 계약을 유지한다.

모든 내부 라이브러리 SNAPSHOT 공개를 검증한 뒤 중앙 BOM을
`2.1.0-SNAPSHOT`으로 발행한다. downstream consumer는 개발선 catalog를 확정한
commit `850959d0ea5f76ac7e2c442400f47653d5f95eed` 하나를 공유한다.

## 2026-09-02 Batch 2 stable 승격

마지막 배포 묶음인 AWS/Javers/Leader `1.0.0`의 signed annotated tag,
exact tag commit의 release workflow, GitHub Release와 Maven Central BOM
공개를 다시 확인했다. release workflow 기준선은 AWS `33602516061`,
Javers `33602516342`, Leader `33604184809`이다.

central catalog의 남은 3개 `SNAPSHOT` BOM ref를 stable로 승격하고,
`stable-catalog-repositories`를 8개 publishable repository 전체로
완성한다. 이 변경은 dependencies 2.0.0 publication 직전의 최종 internal BOM
집합이며, downstream 저장소의 source ref를 다시 바꾸는 작업은 포함하지 않는다.

internal BOM ref 변경은 latest-stable inventory의 authority record를 바꾸지
않고 catalog/input checksum만 바꾼다. 따라서 기존 metadata-verified 510건의
audit record를 유지한 채 새 inventory checksum에 재바인딩한다. 오늘 시점의
외부 dependency 151건을 새로 채택하는 별도 upgrade train은 이 release
경계에 섞지 않는다.

## 2026-09-02 Batch 1 stable 승격

첫 배포 묶음인 Exposed 2.0.0, Image 1.0.0, Text 1.0.0을 모두 공개한 뒤
central catalog에서 한 번만 stable로 승격한다. Exposed release commit
`d632a0bc0662ae616b786f552150a7fabd1cee3e`의 Full Nightly
`33591311604`는 51/51 성공했고 Publish Release `33593217541`도 성공했다.
Maven Central에서 Exposed publication 45개의 POM/module 90개와 batch/core
migration schema resource 각 9개를 확인했다.

Image release commit `b38d4891b66dff8bc63db0018b5e41810d1da9bc`와 Text release
commit `59256aea7011d3f9073d74470459a13363150153`도 exact-head Nightly,
release workflow, GitHub Release, Maven Central 공개를 확인했다. Image 1.0.0의
정식 publication인 `bluetape4k-images-captcha`를 generator와 catalog alias에
복구했다. 이 Batch 1 merge commit은 AWS/Javers/Leader 1.0.0 release가 사용할
하나의 immutable catalog ref가 된다.

## 2026-09-02 Graph 1.0.0 stable 승격

`bluetape4k-graph:1.0.0`의 signed annotated tag가 release commit
`a405300799b36d4d6edb7267ad07ff34d4ad3afe`를 가리키고, exact-head Full
Nightly run `33551524797`과 Publish Release run `33552374208`이 성공했다.
Maven Central에서 publication 16개의 POM, 15개의 JAR·sources·javadoc 및
서명 122개와 metadata 16개를 HTTP 200으로 확인하고 central catalog의
`bluetape4k-graph-bom`을 stable `1.0.0`으로 승격한다.

`config/post-publish-next-development-line.json`의
`stable-catalog-repositories`에도 `bluetape4k-graph`를 기록한다. 이 승격
commit은 다음 downstream release wave의 immutable catalog ref가 되며, Graph
release source와 tag는 변경하지 않는다.

## 2026-09-02 Projects 2.0.0 stable 승격

`bluetape4k-projects:2.0.0`의 signed tag가 release commit
`8165a8989e0075e7c17c489bf3000bf41fef8232`을 가리키고, exact-head Full
Nightly run `33522892818`의 47/47 job과 publication run `33537327623`이
성공했다. Maven Central에서 `bluetape4k-bom`, Gradle module metadata,
`bluetape4k-core`, `bluetape4k-coroutines` 2.0.0을 HTTP 200으로 확인하고
central catalog의 `bluetape4k-bom`을 stable `2.0.0`으로 승격한다.
`config/post-publish-next-development-line.json`의
`stable-catalog-repositories`에도 `bluetape4k-projects`를 기록해 공개 완료된
repository만 stable ref를 허용하고 나머지 7개는 계속 SNAPSHOT으로 검증한다.

이 승격 commit은 첫 downstream release wave의 immutable catalog ref가 된다.
나머지 internal BOM은 각 저장소의 정식 공개 전까지 현재 SNAPSHOT line을
유지한다. `bluetape4k-dependencies:2.0.0` publication은 모든 internal BOM의
stable 승격과 최종 downstream handoff가 끝날 때까지 dispatch하지 않는다.

## 2026-08-12 게시 후속 보강

안정 게시 후 다음 개발선이 `baseVersion` 변경만으로 끝나지 않도록 중앙
catalog의 8개 내부 BOM ref를 각 `baseVersion + -SNAPSHOT`으로 정렬하고,
`config/post-publish-next-development-line.json` 및
`scripts/verify-post-publish-next-development-line.py`로 fail-closed 검증을
추가했다. 소스의 `snapshotVersion=`은 계속 비워 두며 snapshot workflow가
`-PsnapshotVersion=-SNAPSHOT`을 runtime에 주입한다.

기준선 점검에서 발견한 이미 커밋된 `bluetape4k-graph-io-micrometer` 모듈의
생성 catalog 누락도 같은 격리 작업트리에서 복구했다. 생성기 검증 결과는
`aliases=169`, `sub-boms=8`이다.

snapshot publication 검증은 preflight와 post-publication metadata 확인을
분리했다. 첫 snapshot이 아직 없을 때도 publication을 시작할 수 있고, publish
직후에만 `--require-artifacts`를 요구한다. stable `main` CI는 개발선 검증을
건너뛰고 release workflow의 stable boundary guard를 사용한다.

publish 소비자 경계는 두 종류로 분리했다. 내부 라이브러리 9개만 immutable
snapshot catalog commit `45235aa22184b6a2280f530fb90c82a94e31c59d`을
사용한다. `bluetape4k-workshop`, `clinic-appointment`,
`exposed-r2dbc-workshop`, `exposed-workshop`, `timefold-workshop`은 각 로컬
version catalog에서 공식 배포 BOM `1.4.0`을 유지한다. JDK 25 전환은 이
dependency 정책과 독립적이며 예제 BOM을 snapshot으로 바꾸지 않는다.

이번 일회성 JDK 25 전환을 위해 `exposed-r2dbc-workshop`,
`exposed-workshop`, `timefold-workshop`의 JDK25 worktree workflow를 25로
정렬하고, `bluetape4k-workshop`에는 별도 `chore/jdk25-workflows`
worktree를 만들었다. 원격 반영과 PR/merge는 별도 전달 gate다.

현재 snapshot catalog content는 격리된 `chore/publish-next-line-jdk25`의
`45235aa22184b6a2280f530fb90c82a94e31c59d`에 있다. 내부 라이브러리 9개의
격리 branch는 이 SHA를 사용하도록 준비했고, 예제 5개는 공식 BOM `1.4.0`을
유지한다. 새 immutable catalog ref 공개와 push/PR/merge/publication은 별도
전달 gate다. `.java-version` 21 -> 25 변경은 모든 1차 repository root의 다른
검증이 끝난 뒤 마지막 mutation으로 수행했고, 각 JDK25 격리 branch에도 로컬
커밋했다.

## 현재 상태

`bluetape4k-dependencies:1.4.0` 안정 배포 train은 완료됐다. 선행 라이브러리
8개, 최종 catalog `catalog/2026-08-06-03`, dependencies BOM, GitHub Release,
Maven Central metadata와 Central-only consumer를 모두 검증했다. issue #168과
#171 및 milestone `1.4.0`도 최종 증거와 함께 닫았다.

현재 `baseVersion`은 `2.1.0`이고 `snapshotVersion`은 비워 둔다. Projects와
Exposed는 `2.1.0-SNAPSHOT`, AWS/Graph/Image/Javers/Leader/Text는
`1.1.0-SNAPSHOT`을 사용한다. 8개 internal BOM의 SNAPSHOT 공개 검증이 끝난
뒤 dependencies `2.1.0-SNAPSHOT`을 발행하고 downstream catalog ref를 한 번만
전환한다.

## 1.4.0 완료 증거

- Release PR #174 merge: `8a738f084de98323b5651c548b9d2c354fb22329`.
- PR CI `31079582802`, post-merge CI `31080318880`: PASS.
- GitHub-valid signed tag: `1.4.0`, exact merge로 peel 확인.
- Publish Release run `31081143359`: PASS.
- Maven Central POM/module: HTTP 200.
- 공개 POM: 77 dependency-management entries, 18 imported BOMs,
  missing version 0, SNAPSHOT 0, SHA-256
  `d6b4305d5fba5ec960532b34864254fd9ed844cb67adbecff1d00eca8f0eb967`.
- Central-only consumer: 8개 대표 Bluetape 모듈의 versionless resolution PASS.
- Type P receipt: `20260806T074128Z-5d92140b`, sequence 14, checksum
  `733c25592a3d02437e1b0686769cf93152b30c3c1c78035628389a1d7161c69c`.

## 다음 우선순위

1. 외부 dependency/plugin 변경은 중앙 catalog authority와 delta receipt를 먼저
   갱신한다.
2. 내부 라이브러리 저장소는 immutable snapshot catalog ref를 사용하고,
   workshop/example/application은 공식 배포 BOM을 사용한다.
3. 다음 stable train은 새 release checklist와 explicit publication authority를
   확보한 뒤 시작한다.

`bluetape4k-workshop`과 예제/application 저장소는 stable publication 및
snapshot catalog scope에서 계속 제외하고 공식 배포 BOM을 사용한다.
`bluetape4k-experimental`은 catalog-only snapshot consumer로 유지한다.
