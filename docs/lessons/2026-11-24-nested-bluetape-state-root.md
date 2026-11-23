# 중첩된 receipt 경로는 명시적 state-root로 확인한다

## 배경

2026-11-24 개발선 작업을 재개하며 `bluetape-flow.py`를 저장소 worktree
루트에서 실행했다. 기본 경로 `.bluetape`에는 `runs/`가 없었고, 실제 receipt는
그 아래 `.bluetape/snapshot-train-2026-11-23/`에 있었다. 기본 경로의 오류를
receipt 손상으로 잘못 판단해 사용자에게 먼저 알렸다. 이 과정에서 receipt 파일은
변경하지 않았다.

## 결정 및 발견

- 실행 전에 task handoff가 지정한 state root와 run ID를 확인한다.
- state root가 worktree의 `.bluetape` 아래에 중첩되어 있으면 각 helper 호출에
  `--state-root .bluetape/snapshot-train-2026-11-23`을 명시한다.
- 기본 경로에서 run 또는 manifest를 찾지 못했다는 응답만으로 receipt 손상을
  판정하지 않는다. 기록된 state root를 지정해 `verify`와 `resume-check`를 다시
  실행하고, 올바른 경로에서도 실패할 때만 `receipt-diagnose` 절차를 따른다.
- receipt와 owner file은 직접 열거나 수정하지 않고 `bluetape-flow.py`만 사용한다.

## 결과

명시적 state root를 지정한 `verify`는 57개 이벤트와 sequence 57을 확인했다.
`resume-check`는 topology gap과 관찰 대기 lane이 없음을 반환했다. 처음 결과는
경로 선택 오류였으며 receipt 복구는 필요하지 않았다.

## 검증

- `bluetape-flow.py --state-root .bluetape/snapshot-train-2026-11-23 verify --run-id 20261122T202522Z-80e7166d`: PASS (`event_count=57`, `sequence=57`).
- `bluetape-flow.py --state-root .bluetape/snapshot-train-2026-11-23 resume-check --run-id 20261122T202522Z-80e7166d`: PASS (`topology_gaps=[]`, `lanes_requiring_observation=[]`).
- Explicit-state-root `mutation-check` for the current session and task worktree: PASS (`target_count=3`, sequence 57).

## 향후 지침

재개 handoff에는 state root와 run ID를 함께 기록한다. helper가 기본 경로에서
receipt를 찾지 못하면 그 결과를 손상으로 해석하기 전에 기록된 state root를
명시해 다시 확인한다. 명시한 경로에서도 무결성 검증이 실패하면 helper가 안내하는
진단·복구 절차를 사용하고 receipt 내용을 직접 고치지 않는다.
