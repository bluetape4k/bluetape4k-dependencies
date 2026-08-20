# JDK 25 전용선 major `SNAPSHOT` train 체크리스트

상태: **upstream 7개 병합 완료 / 6개 Nightly dispatch 준비 / Leader 복구 hold**

기준 시각: 2026-08-20 KST  
선택 흐름: `catalog-train-snapshot`  
향후 안정 릴리스 분류: `dependencies-major-train`  
기준 branch: 모든 저장소 `develop`  
작업 branch: 모든 저장소 `chore/jdk25-version-train`

## 권한과 범위

- 사용자는 JDK 25 이상만 지원하는 현재 개발선의 SemVer를 다음과 같이
  변경하는 계획을 승인했다.
- 현재 권한은 source version과 열린 milestone 변경, `SNAPSHOT` 게시 및 공개
  metadata/artifact 검증까지다.
- merge는 각 PR의 정확한 head, CI, review, mergeability를 다시 확인한 뒤 별도
  승인을 받아야 한다.
- 안정 tag, 안정 Maven Central 게시, GitHub Release, milestone close, consumer
  BOM 전환, Pages와 버전 매뉴얼 발행은 범위 밖이다.
- `baseVersion`에는 안정 버전 번호를 기록하고 `snapshotVersion=`은 비워 둔다.
  `publish-snapshot` workflow가 runtime에 `-PsnapshotVersion=-SNAPSHOT`을 주입한다.

## 고정된 버전과 기준 SHA

| Repository | 기준 `origin/develop` SHA | 변경 전 | 목표 `baseVersion` | `SNAPSHOT` 검증 좌표 |
| --- | --- | ---: | ---: | --- |
| `bluetape4k-projects` | `846a804b9287c61bbf802d0573909005e1a66f8f` | `2.0.0` | `2.0.0` | `io.github.bluetape4k:bluetape4k-bom:2.0.0-SNAPSHOT` |
| `bluetape4k-exposed` | `ea19b9e0c6d5135d2447c9a95435c85c1127e3b3` | `1.13.0` | `2.0.0` | `io.github.bluetape4k.exposed:bluetape4k-exposed-bom:2.0.0-SNAPSHOT` |
| `bluetape4k-aws` | `91feafa97fd289d0dbd22f59d7a518bb80b8143c` | `0.6.0` | `1.0.0` | `io.github.bluetape4k.aws:bluetape4k-aws-bom:1.0.0-SNAPSHOT` |
| `bluetape4k-graph` | `0bb4b6f0ddd6b8bf456fd4df8240863ae0a9d05d` | `0.7.0` | `1.0.0` | `io.github.bluetape4k.graph:bluetape4k-graph-bom:1.0.0-SNAPSHOT` |
| `bluetape4k-image` | `ceb009718c292023d0e12177a395d0895bff7f62` | `0.5.0` | `1.0.0` | `io.github.bluetape4k.image:bluetape4k-image-bom:1.0.0-SNAPSHOT` |
| `bluetape4k-javers` | `bea957106293957f2014fe2769ac6ec26a67aa34` | `0.4.0` | `1.0.0` | `io.github.bluetape4k.javers:bluetape4k-javers-bom:1.0.0-SNAPSHOT` |
| `bluetape4k-leader` | `a9d205be3746a0e535175d17eaadb3fd60110d7a` | `0.6.0` | `1.0.0` | `io.github.bluetape4k.leader:bluetape4k-leader-bom:1.0.0-SNAPSHOT` |
| `bluetape4k-text` | `89bf8fdebbb8567ac4b5f3620b3719466ef141b0` | `0.4.0` | `1.0.0` | `io.github.bluetape4k.text:bluetape4k-text-bom:1.0.0-SNAPSHOT` |
| `bluetape4k-dependencies` | `298dc7cab27c767b0f78aab2b701f6604fd2c559` | `1.5.0` | `2.0.0` | `io.github.bluetape4k:bluetape4k-dependencies:2.0.0-SNAPSHOT` |

버전은 catalog train tag에서 추론하지 않는다.

## 검증한 후보 SHA

| Repository | Candidate SHA | 비고 |
| --- | --- | --- |
| `bluetape4k-projects` | `846a804b9287c61bbf802d0573909005e1a66f8f` | `develop`이 이미 `2.0.0`이므로 source 변경 없음 |
| `bluetape4k-exposed` | `6de6a0eb3363b61ceb3dddee469d7d9b7aeafff5` | `baseVersion=2.0.0` |
| `bluetape4k-aws` | `11bc7752ee0d5a08c0d427a2e4c8c4ce5e1a82af` | `baseVersion=1.0.0` |
| `bluetape4k-graph` | `67e56b95bf8fa282cd6c2afc46c4f42de83e9583` | `baseVersion=1.0.0` |
| `bluetape4k-image` | `4d663bcbdb769521853bfe76b55f6913c74de19d` | `baseVersion=1.0.0`, Ruby 3.4 manifest 직렬화 호환성 수정 포함 |
| `bluetape4k-javers` | `2da8004fef773b6266eed706583103f50cdfe04c` | `baseVersion=1.0.0` |
| `bluetape4k-leader` | `356c8c322c2144f64ea1a219096d0da67d87ea76` | `baseVersion=1.0.0` |
| `bluetape4k-text` | `7f356c60df857f3f848e9c392bc0886ca6d84584` | `baseVersion=1.0.0` |
| `bluetape4k-dependencies` | `7c69d5795b1c83526d884ac7609909b7f9adcf95` | `baseVersion=2.0.0`, 아래 검증 증거 기록 전 SHA |

각 merge 뒤의 `develop` SHA와 게시 workflow 대상 SHA는 dispatch 직전에 다시
고정한다.

## 저장소 분류와 경계

- 안정 publishable upstream: projects, exposed, aws, graph, image, javers,
  leader, text.
- 최종 BOM과 catalog authority: dependencies.
- catalog-only `SNAPSHOT` consumer: experimental.
- 공식 안정 BOM을 계속 사용하는 범위 밖 consumer: workshop,
  clinic-appointment, exposed-r2dbc-workshop, exposed-workshop,
  timefold-workshop.
- Pages, README 설치 버전, 정식 CHANGELOG와 버전 매뉴얼은 안정 게시 이후
  별도 handoff로 유지한다.

## 실행 DAG

1. upstream 8개 저장소의 개발선 버전과 열린 milestone을 변경하고 각 후보를
   빌드·POM 검증한다.
2. exact-head merge 승인을 받은 upstream만 `develop`에 반영한다.
3. upstream `publish-snapshot` workflow schema를 다시 읽고 8개 `SNAPSHOT`을 게시한 뒤
   metadata, BOM POM과 대표 module POM을 검증한다.
4. dependencies catalog child BOM ref를 공개된 upstream `SNAPSHOT`으로 변경하고
   `baseVersion=2.0.0`으로 올린다.
5. 9개 publisher 전체 publication POM gate와 중앙 빌드·governance 검증을
   통과시킨다.
6. exact-head merge 승인 뒤 dependencies `SNAPSHOT`을 게시하고
   `2.0.0-SNAPSHOT` metadata, BOM POM과 대표 versionless resolution을 검증한다.

이 DAG에는 안정 release edge가 없다. 공개 upstream `SNAPSHOT`이 확인되기 전에는
dependencies `SNAPSHOT`을 dispatch하지 않는다.

## 차단 체크리스트

- [x] **PUB-01** — 흐름, 대상 저장소, 버전, 기준 SHA, artifact matrix, 소비자
      경계와 `SNAPSHOT` 게시 권한을 고정했다.
- [x] **PUB-02** — 9개 publisher와 `SNAPSHOT` DAG를 분류했다. 안정 게시와
      milestone closeout은 제외했다.
- [ ] **PUB-03** — 정확한 candidate SHA와 catalog bytes로 전체 publisher POM,
      Maven effective model, 빌드와 `SNAPSHOT` artifact를 증명한다.
- [ ] **PUB-04** — 안정 preflight는 N/A다. `SNAPSHOT`에 필요한 build, POM,
      signing diagnostics와 workflow schema 항목만 실행 증거로 남긴다.
- [ ] **PUB-05** — 각 `SNAPSHOT` dispatch 직전에 exact workflow SHA와 inputs,
      target develop SHA, artifact 부재/현재 metadata를 새로 확인한다.
- [ ] **PUB-06** — 승인된 `SNAPSHOT` workflow만 dispatch하고 run URL과 공개
      metadata/artifact matrix를 확인한다.
- [x] **PUB-07** — GitHub Release와 milestone closeout은 현재 범위 밖이다.
- [x] **PUB-08** — consumer BOM 및 immutable catalog ref 전환은 안정 게시 이후다.
- [x] **PUB-09** — 이번 변경 자체가 승인된 다음 `SNAPSHOT` 개발선이다.
- [x] **PUB-10** — Pages와 안정 버전 매뉴얼 handoff는 현재 범위 밖이다.
- [ ] **PUB-11** — 완료 시 SHA, workflow URL, artifact matrix, 제외 범위와 잔여
      위험을 수치로 보고한다.

## 현재 dispatch hold

### 2026-08-20 중앙 후보 진행 증거

- `bluetape4k-dependencies` 열린 milestone #10을 `1.5.0`에서 `2.0.0`으로
  변경하고 open issue 3개, closed issue 28개가 보존됐음을 GitHub API로
  read-back했다.
- `gradle.properties`의 `baseVersion`과 catalog self version은 `2.0.0`이며,
  공개 예정 `SNAPSHOT` 좌표는
  `io.github.bluetape4k:bluetape4k-dependencies:2.0.0-SNAPSHOT`이다.
- catalog SHA-256은
  `b3a2dd00183dad3309ec223f0c8db01080371047be76d9f5c557974151d2da28`이다.
- 새 inventory는 기존 authority 519개의 내용과 동일하고 catalog provenance만
  달라졌다. 범위 밖 외부 업그레이드 후보는 채택하지 않고 기존 검증 audit
  records 519개를 보존해 새 catalog/inventory SHA에 결합했다.
- `audit-latest-stable.py --check --check-audit`: metadata verified 514,
  unavailable 0.
- Python 전체 테스트 283개와 `./gradlew build`, managed catalog 169 aliases 및
  8 sub-BOM 검증, `git diff --check`가 통과했다.
- 중앙 후보 맵이 central과 9개 관리 저장소의 origin, branch, base SHA,
  candidate HEAD, clean 상태를 fail-closed로 검증했다.
- `sync-shared-versions.py`, `sync-managed-catalog.py`,
  `sync-dependabot-ignores.py`의 candidate-map 검증이 모두 통과했다.
- 9개 publisher에서 publication POM 174개와 dependency 항목 45,338개를
  검사했고, Maven effective model 174개가 모두 통과했다(`failures=0`).
- upstream 7개 변경 저장소와 dependencies candidate commit이 존재한다.
  `bluetape4k-projects`는 이미 목표 `2.0.0`이어서 source commit이 필요 없다.
- 9개 열린 milestone의 이름과 open 상태를 GitHub API로 read-back했다.

- PR CI와 exact-head merge 승인이 아직 없다.
- 새 upstream `SNAPSHOT` artifact가 아직 공개되지 않았다.
- 각 `.github/workflows/publish-snapshot.yml`의 정확한 dispatch inputs를 실행
  직전에 다시 읽어야 한다.

따라서 현재 `SNAPSHOT` dispatch는 **BLOCKED**다. 위 선행 조건을 순서대로
충족하기 전에는 어떤 workflow도 실행하지 않는다.

### 2026-08-20 upstream 병합 후 dispatch preflight

- 사용자는 upstream 7개 PR의 exact-head 병합을 승인했다. Exposed, AWS,
  Graph, Image, Javers, Leader, Text는 승인된 head로 `develop`에 반영됐고,
  원격 branch SHA를 병합 결과와 대조했다.
- 병합 후 exact-`develop` CI는 Exposed, AWS, Graph, Image, Javers, Text에서
  성공했다. Leader는 모든 빌드와 module test가 성공했지만 Ruby 3.4의 빈 배열
  pretty JSON 차이로 manual manifest byte contract만 실패했다.
- Leader 복구는 별도 local branch `fix/ruby34-manifest-serialization`의
  `87d1eeb5`에 준비했다. JSON 의미, `releaseRef=0.5.0`, release commit은
  그대로이며 Ruby 2.6/3.4와 전체 manual/release contract가 통과했다. 새 PR과
  병합 전에는 Leader Nightly를 dispatch하지 않는다.
- dispatch 대상 6개 저장소의 target `SNAPSHOT` metadata는 모두 HTTP 404로
  아직 존재하지 않는다. latest stable은 Exposed `1.12.1`, AWS `0.5.0`,
  Graph `0.6.0`, Image `0.4.0`, Javers `0.3.0`, Text `0.3.0`이다.
- Nightly workflow 입력은 Exposed/AWS/Graph/Image/Javers가 `scope=full`,
  Text가 입력 없음이다. 성공한 Nightly의 `workflow_run`만 각
  `publish-snapshot.yml`을 자동 실행한다.
- dispatch 대상 `develop` SHA는 Exposed `9571487b`, AWS `7e97398f`, Graph
  `37c62769`, Image `50701b8d`, Javers `1ceff1aa`, Text `0b213374`다.
- Nightly/publish workflow blob SHA는 각각 Exposed `e05b932f`/`5dca94d1`,
  AWS `9fb960f0`/`df2ce9bd`, Graph `7619df0b`/`8cc66a5f`, Image
  `6cf188c2`/`04fb1b97`, Javers `18cded52`/`26e2778c`, Text
  `b4dddc01`/`ceeeaf1e`다.
- Image는 full Nightly run ID를 publish workflow가 검증하며 수동 override를
  사용하지 않는다.

따라서 Exposed, AWS, Graph, Image, Javers, Text의 full Nightly dispatch hold는
해제한다. Leader, dependencies, 안정 게시, consumer 전환, Pages와 버전 매뉴얼은
계속 **BLOCKED**다.
