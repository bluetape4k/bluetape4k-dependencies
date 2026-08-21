# dependencies 2.0.0 SNAPSHOT 소비자 검증 체크리스트

## 범위

- 대상 개발선: `2.0.0-SNAPSHOT`
- 중앙 BOM: `io.github.bluetape4k:bluetape4k-dependencies:2.0.0-SNAPSHOT`
- 중앙 catalog 소비자 ref: `91f9ea9336b5ea991f5675323a1cf25ccfd6f5ed`
- 안정 버전 publish/tag/GitHub Release/milestone close: 이 체크리스트의 범위 밖

## 버전 계약

| 항목 | 기대값 |
| --- | --- |
| `bluetape4k-bom` | `2.0.0-SNAPSHOT` |
| `bluetape4k-exposed-bom` | `2.0.0-SNAPSHOT` |
| AWS/Image/Text/Graph/Leader/Javers child BOM | `1.0.0-SNAPSHOT` |
| source `snapshotVersion` | 빈 값; workflow가 `-PsnapshotVersion=-SNAPSHOT` 주입 |
| snapshot catalog | 모든 내부 소비자가 동일한 immutable SHA 사용 |

## 완료 증거

- [x] dependencies PR #210이 `91f9ea9336b5ea991f5675323a1cf25ccfd6f5ed`로 병합됨
- [x] 중앙 SNAPSHOT metadata와 timestamped POM이 HTTP 200임
- [x] 중앙 POM의 `bluetape4k-bom`/`bluetape4k-exposed-bom` 및 6개 child BOM 버전이 위 계약과 일치함
- [x] 8개 publishable library 소비자 PR이 exact-head로 병합됨: Projects #1461, Exposed #709, AWS #532, Graph #529, Image #556, Javers #331, Leader #751, Text #293
- [x] managed catalog(169 aliases, 8 sub-BOMs) 및 shared-version adoption 검증 성공
- [x] post-publish preflight가 8 publishers, 9 snapshot libraries, 5 official-release examples 경계를 통과함
- [x] `bluetape4k-experimental` 소비자 ref 갱신 PR #97의 wrapper/catalog governance/build가 성공함

## 진행 중인 SNAPSHOT 검증

- [ ] 중앙 소비자 정책 PR #211 exact-head CI 및 병합 승인
- [ ] 실험 저장소 PR #97 exact-head CI 및 병합 승인
- [x] 8개 library publish-snapshot workflow의 POM validation 및 Maven Central metadata 갱신
  Projects #32437154283, Exposed #32437162677, AWS #32437171319, Graph #32437181769,
  Image #32437937942, Javers #32437199766, Leader #32437207868, Text #32437216102
- [x] Image full Nightly #32437276673 및 자동 SNAPSHOT publication 완료
- [x] 8개 child BOM의 timestamped POM HTTP 200과 중앙 BOM dependency-management 계약 확인

## 안정 release 이후 작업

- [ ] 각 repository의 manual/pages/README 및 release-facing 문서를 `2.0.0`/`1.0.0` 안정 좌표로 갱신
- [ ] stable tag, GitHub Release, milestone close, stable publication 및 공식 배포 POM 검증
