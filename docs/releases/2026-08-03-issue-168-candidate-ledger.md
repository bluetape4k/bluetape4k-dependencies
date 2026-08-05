# Issue #168 후보 검증 ledger

이 문서는 `bluetape4k-dependencies 1.4.0` 후보의 사람이 읽을 수 있는 상태 기록이다.
기계 판독 가능한 manifest와 chained receipt가 생성되기 전에는 어떤 downstream 변환도
`candidate-ready`로 판정하지 않는다.

## 현재 상태

- Candidate: `issue-168-central-catalog-authority`
- Central base: `2d0b9185f4e8f4d1989fd934f40a96cccb8b4f62`
- Repository map: `build/catalog-authority/prepare/candidate-repositories.json`
- State: `preparing`
- Publication/dispatch: `HOLD`

## 불변 조건

- 중앙과 9개 downstream worktree의 origin, branch, base, HEAD, clean state를 exact match로 검증한다.
- catalog, disposition, cache manifest는 raw byte SHA-256으로 manifest에 고정한다.
- stage receipt는 단조 증가 sequence, 이전 record SHA-256, fencing token을 가진다.
- push, PR, tag, workflow dispatch, Maven publication은 별도 승인 전까지 실행하지 않는다.
