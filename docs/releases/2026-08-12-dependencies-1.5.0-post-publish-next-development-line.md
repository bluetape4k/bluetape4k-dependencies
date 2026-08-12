# bluetape4k-dependencies 1.5.0 게시 후 다음 개발선 체크리스트

상태: **외부 전달 진행 중 / JDK 25 단일선 closeout 보강**
대상: `bluetape4k-dependencies` 1.5.0 게시 이후 개발선
실행 범위: publish 후속 계약과 검증 보강, 중앙 catalog snapshot 참조 정렬,
library/example JDK 25 전환과 exact-head CI 복구

실행 권한: 사용자의 2026-08-12 지시 “AWS/Image 모두 JDK 25로 올려,
나머지도 모두 해결”에 따라 기존 전달 branch의 수정, commit, push, PR 갱신과
CI 재검증까지 수행한다. merge, tag, snapshot/stable publication, GitHub Release,
worktree/branch cleanup은 별도 승인 전까지 수행하지 않는다.

## 결정된 계약

- 각 publish 대상 repo는 다음 `baseVersion`을 소스에 기록하고
  `snapshotVersion=`은 비워 둔다.
- snapshot suffix는 소스가 아니라 workflow의
  `-PsnapshotVersion=-SNAPSHOT` runtime property로 주입한다.
- 중앙 catalog의 child BOM ref만 `baseVersion + -SNAPSHOT`으로 전환한다.
- 새 immutable snapshot catalog commit은 내부 라이브러리 9개에만 전달한다.
- workshop/example/application 5개는 로컬 version catalog에서 공식 배포
  `bluetape4k-dependencies:1.4.0`을 유지한다.
- 안정 release workflow는 중앙 catalog에 `-SNAPSHOT` ref가 남아 있으면
  fail-closed로 중단한다.
- 안정 tag, Maven Central publication, GitHub Release, workflow dispatch,
  merge와 cleanup은 이 작업 범위에 포함하지 않는다.

## 대상

| Repository | `baseVersion` | 중앙 catalog ref |
|---|---:|---:|
| `bluetape4k-projects` | `1.13.0` | `1.13.0-SNAPSHOT` |
| `bluetape4k-aws` | `0.6.0` | `0.6.0-SNAPSHOT` |
| `bluetape4k-exposed` | `1.13.0` | `1.13.0-SNAPSHOT` |
| `bluetape4k-graph` | `0.7.0` | `0.7.0-SNAPSHOT` |
| `bluetape4k-image` | `0.5.0` | `0.5.0-SNAPSHOT` |
| `bluetape4k-javers` | `0.4.0` | `0.4.0-SNAPSHOT` |
| `bluetape4k-leader` | `0.6.0` | `0.6.0-SNAPSHOT` |
| `bluetape4k-text` | `0.4.0` | `0.4.0-SNAPSHOT` |

`bluetape4k-experimental`은 게시자는 아니지만 내부 snapshot catalog
consumer다. workshop/example/application 저장소는 snapshot publisher와
snapshot catalog consumer 범위에서 모두 제외한다.

| 소비 정책 | Repository | 참조 |
|---|---|---|
| 내부 snapshot catalog | `bluetape4k-projects`, `bluetape4k-aws`, `bluetape4k-experimental`, `bluetape4k-exposed`, `bluetape4k-graph`, `bluetape4k-image`, `bluetape4k-javers`, `bluetape4k-leader`, `bluetape4k-text` | `45235aa22184b6a2280f530fb90c82a94e31c59d` |
| 공식 배포 BOM | `bluetape4k-workshop`, `clinic-appointment`, `exposed-r2dbc-workshop`, `exposed-workshop`, `timefold-workshop` | `bluetape4k-dependencies:1.4.0` |

## 검증 gate

- [x] `config/post-publish-next-development-line.json`에 publish 대상, 내부
      snapshot catalog consumer, 공식 배포 BOM consumer, runtime suffix
      계약을 서로 분리해 고정했다.
- [x] `scripts/verify-post-publish-next-development-line.py`를 개발선 CI와
      snapshot publish workflow에 연결했다. CI/snapshot preflight는
      metadata 존재를 요구하지 않고, publication 직후 step만
      `--require-artifacts`로 Central metadata를 확인한다.
- [x] stable `main` push에서는 개발선 verifier를 건너뛰고, stable release
      workflow가 `--stable-release` 경계 검사를 수행하도록 분리했다.
- [x] 중앙 BOM과 child BOM 8개의 Central snapshot metadata가 HTTP 200임을
      확인했다.
- [x] 중앙 `./gradlew build` 성공.
- [x] Python 전체 테스트 `271개 통과(2 skipped)`, py_compile, 새 verifier 및
      CI governance/checksum/managed-catalog 회귀 테스트 성공.
- [x] `sync-shared-versions.py --workspace .. --check --summary` 성공.
- [x] `sync-managed-catalog.py --write --check --summary` 성공 — 이미
      커밋된 `bluetape4k-graph-io-micrometer` alias를 생성된 catalog에 반영
      (`aliases=169`, `sub-boms=8`).
- [x] catalog checksum과 latest-stable inventory/audit를 alias 추가 후
      재생성하고 `--check --check-audit` 성공.
- [x] 전체 publication-POM gate — `failures=0`, `repositories=9`, `files=174`,
      `dependencies=45334`, `maven_models=174`.

## JDK 25 일회성 전환

- [x] 중앙 저장소와 downstream 14개 저장소의 GitHub Actions Java 실행
      버전을 25로 재점검했다. `JAVA_VERSION`, `java-version`, `jdk-version`의
      활성 21 참조는 0건이다.
- [x] downstream 14개 저장소의 기존 `.java-version`은 모두 `25`다.
- [x] `clinic-appointment`의 `.java-version`도 JDK25 격리 worktree에서
      25로 전환했고, Gradle Java/Kotlin/Gatling target도 25로 정렬했다.
- [x] `exposed-r2dbc-workshop`, `exposed-workshop`, `timefold-workshop`의
      workflow, Java/Kotlin toolchain, atomicfu target을 각 JDK25 격리
      worktree에서 25로 정렬했다.
- [x] `bluetape4k-workshop`의 21/25 matrix와 `JAVA_HOME_21_X64`를 별도
      `chore/jdk25-workflows` worktree에서 25 전용으로 정렬했다.
- [x] `exposed-workshop`의 `StructuredTaskScope` 테스트 소비자 4곳은 공식
      배포된 `bluetape4k-virtualthread-jdk25` runtime provider를 사용한다.
      직접 JDK API 우회는 사용하지 않았다.
- [x] 활성 Gradle build target의 JDK 21 참조는 0건이다. 역사 문서와 legacy
      artifact/backend selector 이름은 실행 계약이 아니므로 보존했다.
- [x] 변경된 worktree의 GitHub Actions YAML은 `actionlint`를 통과했다.
- [x] JDK 25 전체 빌드: AWS 87 tasks, Image 236 tasks, Leader 262 tasks,
      Workshop 1274 tasks, Clinic 96 tasks, Exposed R2DBC 477 tasks,
      Exposed 900 tasks, Timefold 33 tasks 성공.
- [x] 15개 downstream branch를 push하고 PR을 생성했다. 현재 exact-head
      집계는 갱신 전 기준이며, local repair 반영 후 exact-head CI를 다시
      확인한다.

## 후속 전달 gate

중앙 snapshot catalog content commit
`45235aa22184b6a2280f530fb90c82a94e31c59d`는 원격에 공개됐고,
`bluetape4k-dependencies` PR #192의 exact head는
`9b740e415b4ad27ce7d5fc62fadde17a9df6ce19`이다. 내부 라이브러리 9개
branch/PR은 이 immutable ref를 settings와 CI에서 동일하게 사용한다.

2026-08-12T08:24Z에 격리 worktree를 정확한 repository 이름으로 매핑한
candidate workspace에서 다음 preflight를 다시 실행했다.

```text
Verified post-publish development line: 8 publishers
Verified consumer boundary: 9 snapshot libraries, 5 official-release examples
Verified snapshot metadata for the central BOM and all child BOMs
```

최신 외부 버전 기준은 안정 BOM `bluetape4k-dependencies:1.4.0`과 중앙 BOM
`1.5.0-SNAPSHOT`, child BOM 8개의 다음 개발선 snapshot metadata다. 예제 5개는
공식 안정 BOM `1.4.0`을 유지하며 내부 `-SNAPSHOT`을 참조하지 않는다.

현재 dispatch hold는 명시적으로 닫혀 있다. 이번 closeout은 build/CI repair와
기존 PR 갱신까지만 허용하며 merge, snapshot/stable workflow dispatch, tag,
publication, Release, cleanup은 새로운 live-state 확인과 별도 승인이 필요하다.
