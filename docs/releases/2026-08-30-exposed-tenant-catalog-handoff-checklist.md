# Exposed tenant adapter catalog 인계 체크리스트

## 배포 계약

- 흐름: `catalog-train-snapshot`
- upstream 저장소: `bluetape4k/bluetape4k-exposed`
- upstream 기준 브랜치: `develop`
- 승인 시점 HEAD: `315d342cb42a3f58a937254207d57ea7d907bb91`
- 대상 버전: `2.0.0-SNAPSHOT`
- 실행 권한: `Nightly`의 `workflow_dispatch`에서 `scope=full`
- 후속 동작: 성공한 `Nightly`의 `workflow_run`으로 `Publish Snapshot` 자동 실행
- 소비자 범위: `bluetape4k-dependencies` 중앙 catalog와 BOM 검증
- 중앙 version key: `bluetape4k-exposed`
- 중앙 group: `io.github.bluetape4k.exposed`

## 공개 상태 기준선

승인 직전 Maven Central Snapshots에서 확인한 기준선이다.

| artifact | 승인 직전 상태 | 최신 확인 값 |
| --- | --- | --- |
| `bluetape4k-exposed-core` | 공개됨 | `20260829.215700-12` |
| `bluetape4k-exposed-bom` | 공개됨 | `20260829.215700-12` |
| `bluetape4k-exposed-ktor-jdbc` | 공개됨 | `20260829.215700-3` |
| `bluetape4k-exposed-ktor-tenant-jdbc` | 미공개 | metadata HTTP `404` |
| `bluetape4k-exposed-ktor-tenant-r2dbc` | 미공개 | metadata HTTP `404` |

## 순서와 완료 조건

- [x] Exposed PR #764가 `develop`에 반영된 것을 확인한다.
- [x] `Nightly`가 `scope=full` 입력을 지원하고 성공 시 `Publish Snapshot`이 자동 실행되는 것을 workflow YAML에서 확인한다.
- [x] dependencies Issue #217을 생성하고 담당자, milestone, labels를 지정한다.
- [x] Exposed의 정확한 `develop` HEAD에서 Full Nightly를 성공시킨다.
- [x] 같은 HEAD의 자동 `Publish Snapshot`을 성공시킨다.
- [x] 두 tenant adapter의 `2.0.0-SNAPSHOT` metadata와 timestamped POM이 공개적으로 조회되는지 확인한다.
- [x] `scripts/sync-managed-catalog.py` 생성 경로로 두 alias와 BOM constraint를 반영한다.
- [x] catalog checksum, shared-version, Dependabot ignore, publication POM, Gradle build 검증을 통과한다.
- [x] dependencies PR #218을 `develop` 대상으로 생성한다.
- [ ] PR #218의 exact-head CI를 통과한다.
- [ ] dependencies PR 병합 전 fresh approval에서 멈춘다.
- [ ] #217 병합 후 PR #216을 최신 `develop`에 맞춰 재검증한다.

## 변경 중지 조건

- 이 체크리스트에서는 tag를 만들지 않는다.
- dependencies의 수동 Snapshot 배포를 실행하지 않는다.
- dependencies PR을 병합하거나 auto-merge를 설정하지 않는다.
- #217이 병합되기 전에는 PR #216의 catalog/report 변경을 재정렬하지 않는다.
- Exposed의 dispatch HEAD가 달라졌거나 새 tenant artifact 공개가 확인되지 않으면 catalog 변경을 PR로 전달하지 않는다.

## 재발 방지

- 놓친 가정: alias-only catalog 변경도 `--refresh-audit`로 전체 latest-version audit를 다시 만들어야 한다고 판단했다.
- 발견 증거: 전체 refresh는 catalog SHA뿐 아니라 authority `515`개의 record와 disposition을 변경해 별도 #206 report regeneration 범위를 흡수했다.
- 결정: #217에서는 inventory와 audit의 catalog/inventory SHA 연결만 갱신하고 기존 record와 summary를 보존한다.
- 검증: refresh 결과를 제거한 뒤 before/after JSON 비교에서 두 파일의 record와 summary가 모두 동일했고 `--check-audit`가 통과했다.
- 향후 guard: alias-only handoff에서 audit refresh를 실행하기 전에 report regeneration의 이슈 소유권을 확인한다. 별도 이슈가 소유하면 SHA 연결만 갱신하고 record/summary 불변성을 검증한다.
- 재사용 규칙: linked worktree의 catalog helper에는 `docs/lessons/2026-08-10-issue-164-library-only-catalog-validation.md`에 따라 절대 workspace root를 전달한다.
- 놓친 가정: `bluetape4k-workshop`은 계속 안정 BOM `1.4.0`을 소비한다고 분류했다.
- 발견 증거: PR #218의 fresh-clone CI가 `bluetape4k-workshop` `develop`의 `2.0.0-SNAPSHOT`을 확인했고, 전환 커밋 `952804db1be3cd6832abaa990473695f8cdfc46d`는 중앙 SNAPSHOT 소비자 열차에 맞추려는 의도를 명시했다.
- 결정: workshop을 `official-release-repositories`에서 `development-snapshot-repositories`로 이동하고, 안정 예제는 `clinic-appointment`와 `timefold-workshop`만 유지한다.
- 향후 guard: consumer가 공식 release와 development SNAPSHOT 사이를 전환하면 해당 consumer PR과 같은 순서에서 중앙 manifest 분류 테스트도 갱신한다.

## 결과 기록

- Full Nightly run: [33312955245](https://github.com/bluetape4k/bluetape4k-exposed/actions/runs/33312955245), attempt 2, `51/51` 성공
  - attempt 1에서 `kover-jvm-agent:0.9.9` Maven Central `HEAD` 요청이 `403 Forbidden`으로 실패했다.
  - 실패 job만 제한 재실행해 같은 HEAD의 전체 run을 성공시켰다.
- 자동 Publish Snapshot run: [33314212381](https://github.com/bluetape4k/bluetape4k-exposed/actions/runs/33314212381), 성공
- 공개 metadata/POM:
  - `bluetape4k-exposed-ktor-tenant-jdbc`: `lastUpdated=20260830133341`, POM `2.0.0-20260830.133341-1`, metadata/POM HTTP `200`
  - `bluetape4k-exposed-ktor-tenant-r2dbc`: `lastUpdated=20260830133341`, POM `2.0.0-20260830.133341-1`, metadata/POM HTTP `200`
- local 검증:
  - managed catalog: aliases `183`, sub-BOMs `8`
  - Python: `297` 통과, 외부 `bluetape4k-core:1.9.2-SNAPSHOT` 조회 `403`에 따른 명시적 skip `2`
  - managed artifacts: `183`개 확인
  - publication POM: 저장소 `9`, POM/Maven model `188`, dependency `50,015`, 실패 `0`
  - Gradle: `BUILD SUCCESSFUL`
  - latest-stable inventory/audit: SHA 연결만 갱신, record와 summary 보존
  - post-publish next line: PR #218 CI에서 workshop의 의도적 `2.0.0-SNAPSHOT` 전환과 중앙 manifest의 오래된 안정 소비자 분류가 충돌함을 확인
- dependencies PR: [#218](https://github.com/bluetape4k/bluetape4k-dependencies/pull/218), 첫 exact-head CI [33315729695](https://github.com/bluetape4k/bluetape4k-dependencies/actions/runs/33315729695)는 위 consumer 분류 불일치로 실패
