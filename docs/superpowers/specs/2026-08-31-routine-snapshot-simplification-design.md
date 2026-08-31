# 반복 가능한 SNAPSHOT 배포 단순화 설계

## 문제

`2.0.0-SNAPSHOT`은 개발 중인 동일 버전을 여러 번 발행할 수 있어야 한다.
그러나 현재 일부 저장소의 `Publish Snapshot`은 이미 성공한 CI run ID, 사용자가
복사한 expected head SHA, handoff issue 번호를 다시 입력하고 environment reviewer
승인까지 받아야 한다. `bluetape4k-projects`는 이 계약에 특정 기능 이슈
`#1562`까지 고정한다.

이 절차는 stable release candidate의 단일성 검증을 일상 SNAPSHOT에 적용한
것이다. 그 결과 문서, 이슈, 다른 기능 PR이 개발선 HEAD를 바꿀 때마다 기존
증거가 무효가 되고, 같은 SNAPSHOT을 다시 발행하는 정상 작업이 release
handoff처럼 취급된다. 반대로 `workflow_run`에서 checkout ref를 명시하지 않은
저장소는 트리거한 CI commit이 아닌 실행 시점의 기본 브랜치 HEAD를 발행할 수
있다.

## 목표

- 같은 SNAPSHOT 버전의 반복 발행을 정상 동작으로 취급한다.
- 사용자가 SHA, CI run ID, handoff issue 번호를 전달하지 않게 한다.
- 자동 실행은 성공한 CI가 검증한 commit을, 수동 실행은 사용자가 선택한 ref의
  dispatch commit을 발행한다.
- 공개 artifact와 provenance가 가리키는 source SHA를 workflow가 자동으로
  일치시킨다.
- stable release의 immutable candidate 검증은 그대로 유지한다.
- repository environment에 저장된 publishing secret과 branch policy는
  유지한다.

## 비목표

- Maven Central의 동일 SNAPSHOT 좌표를 immutable artifact로 만들지 않는다.
- `2.0.0` stable release의 exact candidate, catalog checkpoint, release receipt를
  완화하지 않는다.
- 2.0.0 배포 전에 중앙 reusable workflow를 새로 도입하지 않는다.
- action commit SHA pin을 tag 참조로 되돌리지 않는다.

## 검토한 방식

### 1. 기존 수동 증거 전달 유지

매번 CI run ID와 SHA를 복사하면 실행 대상을 명시적으로 볼 수 있다. 하지만
workflow event 자체에 이미 source run과 SHA가 있으며, 사람이 같은 값을 다시
전달하는 과정은 보안을 추가하지 않고 불일치와 재작업만 만든다. 이 방식은
제외한다.

### 2. source SHA 검증 전체 제거

입력은 가장 단순해지지만 `workflow_run`의 기본 checkout이 나중의 기본 브랜치
HEAD를 발행하는 문제를 막지 못한다. 어느 commit을 발행했는지 검증 가능한
계약도 약해지므로 제외한다.

### 3. event에서 source SHA를 자동 결정

`workflow_run`은 `github.event.workflow_run.head_sha`를 사용하고,
`workflow_dispatch`는 dispatch context의 `github.sha`를 사용한다. workflow는
계산한 SHA를 checkout하고 `git rev-parse HEAD`로 일치 여부를 확인한다. 사용자가
입력할 값은 없지만 발행 대상은 immutable SHA로 고정된다. 이 설계에서 이
방식을 사용한다.

## 실행 계약

### 자동 실행

`workflow_run`은 지정한 CI 또는 Nightly workflow가 성공한 경우에만 실행한다.
발행 SHA는 `github.event.workflow_run.head_sha`다. checkout, build, publication,
provenance에서 동일한 값을 사용한다. CI 완료 뒤 develop HEAD가 더 전진해도
해당 실행은 원래 검증한 commit을 발행한다.

### 수동 실행

`workflow_dispatch`는 GitHub UI나 API에서 선택한 ref의 `github.sha`를 발행
SHA로 사용한다. 별도 `expected_head_sha`, `verified_ci_run_id`,
`handoff_issue_number` 입력을 받지 않는다. 수동 실행은 운영자 복구와 필요 시
반복 발행을 위한 경로이며, 같은 SNAPSHOT version을 다시 발행하는 것을
오류로 간주하지 않는다.

### 공통 검증

모든 저장소에서 다음 순서를 적용한다.

1. event 종류에 따라 발행 SHA를 계산한다.
2. 계산한 SHA를 `actions/checkout`의 `ref`로 사용한다.
3. checkout 직후 `git rev-parse HEAD`와 계산한 SHA가 같은지 확인한다.
4. 이후 build, publication, provenance가 같은 checkout을 사용한다.
5. 실행 summary에 event 종류와 발행 SHA를 기록한다.

`workflow_run` payload에 SHA가 없거나 checkout 결과가 다르면 발행 전에
실패한다. 이미 실행 중이거나 approval 대기 중인 SNAPSHOT run은 취소하지
않는다. 각 run은 자기 event가 가리킨 commit을 독립적으로 발행할 수 있다.

## 저장소별 변경 범위

다음 9개 publisher 저장소의 `.github/workflows/publish-snapshot.yml`을 같은
계약으로 정리한다.

| 저장소 | 변경 기준 |
| --- | --- |
| `bluetape4k-projects` | 수동 SHA/run/issue 입력과 TenantContext 전용 receipt를 제거하고 자동 SHA 계약을 적용한다. |
| `bluetape4k-dependencies` | 자동 SHA 계약과 action commit SHA pin을 함께 유지한다. |
| `bluetape4k-aws` | 기존 action pin PR에 자동 SHA checkout을 추가한다. |
| `bluetape4k-exposed` | `workflow_run`의 default-branch checkout을 source run SHA checkout으로 고친다. |
| `bluetape4k-graph` | 고정 `develop` checkout을 event source SHA checkout으로 바꾼다. |
| `bluetape4k-image` | 기존 run 검증을 자동 SHA 계약으로 단순화한다. |
| `bluetape4k-javers` | 기존 action pin PR에 자동 SHA checkout을 추가한다. |
| `bluetape4k-leader` | 기존 action pin PR에 자동 SHA checkout을 추가한다. |
| `bluetape4k-text` | 기존 action pin PR에 자동 SHA checkout을 추가한다. |

`bluetape4k-projects`의 `Full Nightly`는 publish workflow의 사용자 입력값이
아니다. SNAPSHOT 실행에 필요한 검증은 event가 직접 제공하는 source SHA와
Nightly conclusion으로 한정한다. 특정 기능 이슈 번호나 별도의 release handoff
receipt를 SNAPSHOT publication 조건으로 사용하지 않는다.

## Environment와 공급망 경계

9개 저장소의 `maven-central-release` environment에서 required reviewer를
제거한다. SNAPSHOT 발행마다 사람이 한 번 더 승인하는 절차만 제거하며 다음
보호는 유지한다.

- publishing credential은 environment secret에 둔다.
- deployment branch policy는 `develop`을 허용하는 현재 범위를 유지한다.
- `can_admins_bypass=false`를 유지한다.
- 외부 action은 검토한 commit SHA로 pin한다.
- workflow permission은 필요한 최소 범위만 허용한다.

Environment reviewer 제거와 secret 변경은 별개다. 이 작업은 secret 값을 읽거나
교체하지 않는다.

## Stable release 경계

반복 가능한 SNAPSHOT과 stable release candidate를 분리한다.

| 경계 | SNAPSHOT | Stable release |
| --- | --- | --- |
| 동일 version 재발행 | 허용 | 허용하지 않음 |
| source SHA 선택 | event에서 자동 계산 | 승인된 exact candidate |
| 사용자 SHA/run 입력 | 없음 | release checklist와 receipt에서 고정 |
| catalog SHA | 개발선의 검증된 forward drift 허용 | candidate checkpoint와 exact 일치 |
| 승인 | workflow dispatch/merge 권한 | candidate 검증 후 별도 publication 승인 |

따라서 README, `WIP.md`, `CHANGELOG.md`, 기능 이슈 처리로 develop HEAD가
전진하는 것은 SNAPSHOT을 막지 않는다. 최종 `2.0.0` candidate를 정할 때만 모든
저장소의 문서와 기능 작업을 마친 뒤 exact SHA를 한 번 고정한다.

## 기존 PR과 이슈 처리

action pin 작업이 이미 있는 저장소는 새 PR을 만들지 않고 기존 branch에 이
설계를 반영한다.

- AWS PR `#604`
- Dependencies PR `#222`
- Exposed PR `#773`
- Graph PR `#598`
- Image PR `#617`
- Javers PR `#361`
- Leader PR `#849`
- Text PR `#312`
- Projects는 `fix/routine-snapshot-workflow` branch에서 새 PR을 만든다.

이 구현으로 중복되거나 과도해진 이슈는 검증 증거를 남긴 뒤 닫는다.

- Dependencies `#217`: action pin PR 병합으로 이미 완료됐으므로 닫는다.
- Projects `#1582`: SNAPSHOT에 stable exact-head 절차를 적용하는 중복 강화이므로
  닫는다.
- Exposed `#769`: source run SHA checkout 수정 후 닫는다.
- Projects `#1578`: action pin과 environment reviewer 제거가 완료되면 닫는다.

Projects `#1451`은 2.0.0 이후 작업이므로 유지한다. Dependencies `#197`도 향후
Kotlin release 추적 이슈이므로 유지한다.

## 검증

각 저장소에서 다음을 확인한다.

- `actionlint`가 통과한다.
- workflow fixture 또는 정적 검증이 두 event의 SHA 선택을 확인한다.
- checkout `ref`와 검증 대상 SHA가 같은 expression을 사용한다.
- 제거하기로 한 수동 입력과 특정 이슈 번호가 workflow에 남아 있지 않다.
- action 참조가 immutable commit SHA다.
- repository의 기본 build 또는 workflow 관련 test가 통과한다.
- environment secret 이름과 branch policy가 변경되지 않았고 required reviewer만
  제거됐다.

Hosted 검증은 기존 PR의 exact head CI로 확인한다. 각 PR merge는 별도 승인
경계이며 auto-merge를 사용하지 않는다. Environment 변경과 issue close는
구현·CI 증거가 준비된 뒤 수행한다.

## 완료 조건

- 9개 publisher 모두 event source SHA를 자동 checkout하고 확인한다.
- 사용자 입력 SHA, CI run ID, handoff issue 번호가 없다.
- 동일 SNAPSHOT version의 반복 publication을 차단하거나 취소하는 절차가 없다.
- 기존 environment secret과 develop branch policy를 유지하면서 required
  reviewer만 제거한다.
- stable release exact-candidate 계약과 catalog checkpoint는 변경되지 않는다.
- 불필요한 이슈는 완료 증거와 함께 닫고, post-release 이슈는 열린 상태를
  유지한다.

## 근거

- 실패 run: <https://github.com/bluetape4k/bluetape4k-dependencies/actions/runs/33290856108>
- GitHub `workflow_run` event: <https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run>
- `actions/checkout` ref 동작: <https://github.com/actions/checkout/blob/main/README.md>
- 기존 catalog forward-drift 설계: <https://github.com/bluetape4k/bluetape4k-dependencies/issues/213>
