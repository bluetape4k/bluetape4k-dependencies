# JDK 25 전용선 major `SNAPSHOT` train 체크리스트

상태: **계획 승인 / 변경 진행 중 / dispatch hold**

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

최종 candidate SHA는 각 변경 commit과 merge 뒤에 이 표의 기준 SHA와 별도로
기록한다. 버전은 catalog train tag에서 추론하지 않는다.

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

- upstream과 dependencies candidate commit이 아직 없다.
- PR CI와 exact-head merge 승인이 아직 없다.
- 새 upstream `SNAPSHOT` artifact가 아직 공개되지 않았다.
- 각 `.github/workflows/publish-snapshot.yml`의 정확한 dispatch inputs를 실행
  직전에 다시 읽어야 한다.

따라서 현재 `SNAPSHOT` dispatch는 **BLOCKED**다. 위 선행 조건을 순서대로
충족하기 전에는 어떤 workflow도 실행하지 않는다.
