# dependencies 2.0.0 SNAPSHOT 소비자 검증 체크리스트

## 범위

- 대상 개발선: `2.0.0-SNAPSHOT`
- 중앙 BOM: `io.github.bluetape4k:bluetape4k-dependencies:2.0.0-SNAPSHOT`
- 중앙 catalog 기본 minimum ref: `91f9ea9336b5ea991f5675323a1cf25ccfd6f5ed`
- 중앙 catalog minimum ref 예외: `bluetape4k-exposed`, `bluetape4k-graph`는
  `df64293753a9491b337852a158f89d4a93a1734a`
- SNAPSHOT consumer 실제 ref: 저장소별 minimum과 같거나 그 후속이며, 현재
  중앙 candidate `HEAD`의 조상이어야 함
- 안정 버전 publish/tag/GitHub Release/milestone close: 이 체크리스트의 범위 밖

## Issue #213 후보 경계

- 대상 저장소/기준 SHA: `bluetape4k-dependencies` / `df64293753a9491b337852a158f89d4a93a1734a`
- 대상 branch: `feat/issue-213-tenant-catalog` → `develop`
- version authority: `gradle/libs.versions.toml`의 `bluetape4k-bom=2.0.0-SNAPSHOT`
- artifact 범위: `bluetape4k-tenant`, `bluetape4k-tenant-reactor`, `bluetape4k-ktor-tenant`
- 공개 upstream 증거: 2026-08-30 KST 조회에서 BOM과 세 tenant artifact의 SNAPSHOT metadata가 모두 HTTP 200
- consumer 범위: `exposed-workshop#255`와 `exposed-r2dbc-workshop#215`; 후자는 갱신된 dependencies SNAPSHOT 공개 후 진행
- 승인 범위: catalog/BOM 계약 구현, 검증, commit, push, PR 생성
- dispatch hold: dependencies SNAPSHOT publish, stable release, merge, downstream 저장소 변경은 별도 승인 전까지 실행하지 않음

현재 generator는 세 tenant alias와 함께 이미 `develop`에 병합된 Exposed publishable
artifact 8개의 누락도 감지합니다. `sync-managed-catalog --check`의 전체 inventory
계약을 통과시키기 위해 generator-owned alias를 함께 동기화하되, 외부 버전이나 BOM
version authority는 변경하지 않습니다.

### 후보 검증 상태

- [x] tenant alias 계약 RED: 세 alias 누락으로 3개 subtest가 실패함
- [x] tenant alias 계약 GREEN: 2 tests, failures/errors/skipped=0
- [x] managed catalog: 181 aliases, 8 sub-BOMs, checksum `a1d06b4c90a691cb7487647af9b2a6733765775e234dae043744f95170d5ce39`
- [x] Python 3.13 전체 suite: 288 tests, failures/errors=0; worktree 경로에서 sibling을 찾지 못하는 기존 real-workspace 검사 2개는 exact repository-map 검사로 대체함
- [x] latest-stable audit: authority 515, metadata verified 510, preview-only 5, unavailable 0
- [x] managed artifact 공개 확인: 181개 확인, self artifact 제외
- [x] `./gradlew build --no-daemon --no-configuration-cache`: 성공
- [x] exact candidate repository-map: 181 aliases, 8 sub-BOMs, shared-version adoption clean
- [x] 실제 workspace 소비자 정책: 9 SNAPSHOT libraries, 3 official-release examples, 2 development-SNAPSHOT examples
- [x] 9 publisher publication POM gate: 186 POMs, 49,423 dependencies, failures=0
- [x] 사용자 지시에 따른 exact-head inline review: P0/P1=0; 독립 review lane 대체 사실을 PR에 명시
- [ ] exact-head PR CI

## 버전 계약

| 항목 | 기대값 |
| --- | --- |
| `bluetape4k-bom` | `2.0.0-SNAPSHOT` |
| `bluetape4k-exposed-bom` | `2.0.0-SNAPSHOT` |
| AWS/Image/Text/Graph/Leader/Javers child BOM | `1.0.0-SNAPSHOT` |
| source `snapshotVersion` | 빈 값; workflow가 `-PsnapshotVersion=-SNAPSHOT` 주입 |
| SNAPSHOT catalog | manifest의 immutable SHA를 저장소별 minimum으로 사용하고, settings/CI가 일치하는 `minimum <= actual <= candidate HEAD`만 허용 |
| example catalog | 안정 예제 3개는 `1.4.0`, 개발 검증 예제 2개는 `2.0.0-SNAPSHOT` 사용 |

## 완료 증거

- [x] dependencies PR #210이 `91f9ea9336b5ea991f5675323a1cf25ccfd6f5ed`로 병합됨
- [x] 중앙 SNAPSHOT metadata와 timestamped POM이 HTTP 200임
- [x] 중앙 POM의 `bluetape4k-bom`/`bluetape4k-exposed-bom` 및 6개 child BOM 버전이 위 계약과 일치함
- [x] 8개 publishable library 소비자 PR이 exact-head로 병합됨: Projects #1461, Exposed #709, AWS #532, Graph #529, Image #556, Javers #331, Leader #751, Text #293
- [x] managed catalog(169 aliases, 8 sub-BOMs) 및 shared-version adoption 검증 성공
- [x] post-publish preflight가 8 publishers, 9 SNAPSHOT libraries, 3 official-release examples, 2 development-SNAPSHOT examples 경계를 통과함
- [x] `bluetape4k-experimental` 소비자 ref 갱신 PR #97의 wrapper/catalog governance/build가 성공함

## 진행 중인 SNAPSHOT 검증

- [ ] 중앙 소비자 정책 PR #211 exact-head CI 및 병합 승인
- [ ] 실험 저장소 PR #97 exact-head CI 및 병합 승인
- [x] 8개 library의 SNAPSHOT publish workflow에서 POM validation 및 Maven Central metadata 갱신
  Projects #32437154283, Exposed #32437162677, AWS #32437171319, Graph #32437181769,
  Image #32437937942, Javers #32437199766, Leader #32437207868, Text #32437216102
- [x] Image full Nightly #32437276673 및 자동 SNAPSHOT publication 완료
- [x] 8개 child BOM의 timestamped POM HTTP 200과 중앙 BOM dependency-management 계약 확인
- [x] Projects merged develop archive에서 `:bluetape4k-core:dependencies --configuration compileClasspath` 대표 해석 성공

## 안정 release 이후 작업

- [ ] 각 repository의 manual/pages/README 및 release-facing 문서를 `2.0.0`/`1.0.0` 안정 좌표로 갱신
- [ ] stable tag, GitHub Release, milestone close, stable publication 및 공식 배포 POM 검증
