# Issue #189 Kotlin 2.4.10 / Detekt alpha.6 카탈로그 체크리스트

상태: **PR 준비 / 병합 승인 대기**

## 고정 범위

- 대상 저장소: `bluetape4k/bluetape4k-dependencies`
- 기준: `develop` ← `build/kotlin-2.4.10-detekt-alpha6`
- 이슈: [#189](https://github.com/bluetape4k/bluetape4k-dependencies/issues/189)
- 대상: 중앙 catalog와 게시 가능한 `bluetape4k-*` 라이브러리 8곳
- 대상 라이브러리: `projects`, `aws`, `exposed`, `graph`, `image`, `javers`, `leader`, `text`
- 제외: `bluetape4k-experimental`, workshop, clinic/application 및 기타 예제 저장소
- 금지: merge, tag, catalog tag, publication, release, branch/worktree 삭제

## 버전 결정

- `kotlin`: `2.4.0` → `2.4.10`
- `detekt-dev`: `2.0.0-alpha.5` → `2.0.0-alpha.6`
- `dev.detekt:detekt-rules-ktlint-wrapper`: `alpha.6`으로 동행
- `detekt-legacy`: `1.23.8` 유지
- `io.gitlab.arturbosch.detekt:detekt-formatting`: `1.23.8` 유지
- `kotlin20`: `2.0.21` 유지; Leader의 레거시 Detekt compiler/stdlib 고정과 ABI fixture를 보존

`io.gitlab.arturbosch.detekt` 좌표에는 `2.0.0-alpha.6` artifact가 없으므로 레거시
formatting alias를 신규 `dev.detekt` 좌표로 바꾸지 않는다. Detekt 제거도 하지 않는다.

## 검증 증거

- [x] `audit-latest-stable.py --write` 및 `--refresh-audit`: authority 518, line 552, metadata unavailable 0
- [x] 최신 안정 버전 감사: Kotlin 2.4.10 `current`, Detekt alpha.6 preview-only `hold-unavailable`, legacy Detekt 1.23.8 `current`
- [x] governance Python tests: 64개 통과
- [x] managed catalog: aliases 168, sub-BOMs 8, clean
- [x] shared-version adoption: clean (8개 게시 library 명시 검사)
- [x] Dependabot ignore sync: clean (8개 게시 library 명시 검사)
- [x] publication POM gate: repositories 9, files/models 173, dependencies 45,217, failures 0
- [x] dependencies `./gradlew build`: 성공
- [x] text `./gradlew detekt` with candidate catalog: 성공
- [x] leader `:bluetape4k-leader-core:detekt` with candidate catalog: 성공
- [x] checksum 및 catalog audit check: 성공

## 분리된 기존 실패

Leader 전체 `./gradlew detekt`는 기준 catalog에서도
`build.gradle.kts:501`의 `detektProductionSourceGuard`가 Gradle script receiver null을
참조해 실패한다. 후보 catalog에서 새로 발생한 회귀가 아니므로 이번 중앙 catalog 변경에
downstream 소스 수정을 섞지 않고, 모듈 단위 Detekt 성공으로 레거시 plugin 해석을 검증했다.

## 남은 게이트

- [ ] commit, push, PR 생성 및 live metadata/CI 확인
- [ ] 사용자 별도 승인 후 exact-head merge
- [ ] merge 후에만 branch/worktree cleanup 검토
