# WIP - bluetape4k-dependencies

Snapshot: 2026-09-02 KST
Scope: dependencies 2.0.0 정식 배포 train.

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

현재 `baseVersion`은 `2.0.0`이고 `snapshotVersion`은 비워 둔다. Projects
2.0.0, Graph/Image/Text 1.0.0, Exposed 2.0.0을 stable로 승격했으며 AWS,
Leader, Javers는 각 정식 공개와 검증이 끝날 때까지 SNAPSHOT line을 유지한다.
모든 internal BOM이 stable이 되기 전에는 dependencies 2.0.0 tag나
publication을 만들지 않는다.

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
