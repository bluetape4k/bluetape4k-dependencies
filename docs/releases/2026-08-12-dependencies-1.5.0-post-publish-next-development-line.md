# bluetape4k-dependencies 1.5.0 게시 후 다음 개발선 체크리스트

상태: **로컬 보강 완료 / 외부 전달 보류**
대상: `bluetape4k-dependencies` 1.5.0 게시 이후 개발선
실행 범위: publish 후속 계약과 검증 보강, 중앙 catalog snapshot 참조 정렬

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
  push/merge는 이 작업 범위에 포함하지 않는다.

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

- [x] 주요 `bluetape4k-*` library workflow의 Java 실행 버전을 25로 재점검했다.
- [x] `clinic-appointment`의 `.java-version`도 JDK25 격리 worktree에서
      25로 전환했다(워크플로는 이미 25).
- [x] `exposed-r2dbc-workshop`, `exposed-workshop`, `timefold-workshop`의
      21 workflow를 각 JDK25 격리 worktree에서 25로 정렬했다.
- [x] `bluetape4k-workshop`의 21/25 matrix와 `JAVA_HOME_21_X64`를 별도
      `chore/jdk25-workflows` worktree에서 25 전용으로 정렬했다.
- [x] 변경된 네 worktree의 GitHub Actions YAML은 `actionlint`를 통과했다.
- [ ] 위 worktree 변경의 downstream PR/push/merge는 별도 전달 gate다.

## 후속 전달 gate

중앙 snapshot catalog content commit은
`45235aa22184b6a2280f530fb90c82a94e31c59d`이고 아직 원격에 없다. 내부
라이브러리 9개에는 이 SHA를 사용하는 로컬 격리 branch를 준비했다. 원격
catalog를 먼저 공개하지 않았으므로 실제 Gradle remote resolution은 아직
수행하지 않는다.

다음 순서는 중앙 exact head를 원격에 push해 catalog SHA를 공개하고, 내부
라이브러리 9개 branch/PR에서 remote resolution을 검증한 뒤 별도 승인으로
push, PR, merge, publication을 진행하는 것이다. 예제 5개는 이 전달 단계에
포함하지 않으며 공식 배포 BOM `1.4.0`을 계속 사용한다.
