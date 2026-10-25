# 중앙 catalog rollout 증거의 불변성

## 배경

Issue #261의 Kover 전용 후보를 준비하는 동안 resolved-graph 승격 후 다음 audit이
기존 verified delta ledger를 다시 읽은 뒤 pending 경로에 쓰려 했다. 그 경로는 이미
불변 증거를 가리키므로 정상적인 재실행도 실패했다. audit 파일을 직접 덮어쓰는 방식은
실패 시 일부 바이트만 남겨 이후 해시 검증까지 깨뜨릴 수 있었다. 승격 도중 프로세스가
중단되면 authority ledger와 central ledger가 서로 다른 lifecycle 상태로 남을 수도 있었다.

## 원인과 결정

- Central rollout row의 파일 경로와 SHA-256은 한 시점의 증거를 식별한다. verified
  ledger는 pending ledger의 같은 파일을 수정해서 표현할 수 없다.
- 기존 rollout row를 읽을 때는 row가 선언한 파일을 읽고 두 해시를 확인한다. 이미
  immutable revision을 가리키면 그 경로를 재사용한다.
- candidate audit가 바뀌면 catalog SHA와 audit SHA로 결정한 새 revision 경로에 기록한다.
  같은 경로에 다른 바이트를 쓰지 않는다.
- resolved-graph 승격은 receipt SHA로 식별되는 새 snapshot을 만든다. mutable authority
  ledger와 central index에는 검증된 파일 내용을 담은 transaction journal을 먼저 기록한
  다음 적용한다. transaction journal v2는 원본 바이트, 파일 모드, SHA-256, transaction
  ID를 함께 보존한다. journal identity sidecar가 원본 journal digest를 고정하므로
  rollback tombstone이 변조된 경우에는 이를 복구 권한으로 채택하지 않는다.
- 여러 파일을 갱신하는 동안에는 repository root와 각 parent directory를 descriptor로
  고정하고 `O_NOFOLLOW`로 symlink 경로를 거부한다. target별 lock, expected-state 검사,
  descriptor 기반 `rename`/`link`, parent directory `fsync`를 함께 사용해 마지막 검사와
  교체 사이의 외부 변경도 감지한다. tombstone 삭제는 private quarantine 디렉터리로
  검증된 inode를 옮긴 뒤 quarantine FD에서 제거하고, 중단된 quarantine도 다음 복구에서
  rollback 증거로 되돌린다. rollback 충돌이 생기면 외부 바이트를 보존하고 journal을
  남겨 재시도 증거로 유지한다. missing-target rollback tombstone, identity tombstone,
  journal 복구 뒤의 duplicate tombstone도 다음 실행에서 정리한다.
- v2 journal은 유효한 transaction ID와 identity sidecar를 필수로 요구한다. target 적용이 끝나면 journal digest와
  transaction ID를 담은 finalization marker를 먼저 남기고 identity 및 tombstone을
  검증·정리한 뒤 canonical journal을 마지막에 제거한다. identity 삭제나 journal 삭제
  중 중단되어도 marker가 남아 finalization을 재개할 수 있으며, marker가 있는 상태에서
  target이 desired 바이트가 아니면 재적용하지 않고 중단한다.
- private quarantine은 rollback 이름의 regular-file 증거만 복구하고 canonical journal·identity
  파일을 위조한 디렉터리는 거부한다. quarantine 복구는 no-replace hardlink 후 source
  unlink를 사용해 경합 중 외부 파일을 덮어쓰지 않는다.
- snapshot은 `config/rollouts` 부모를 descriptor와 `O_NOFOLLOW`로 고정한 뒤 staging
  디렉터리를 완성해 atomic rename으로 노출한다. symlink 부모는 거부하며 쓰기 도중
  실패해도 불완전한 파일을 immutable 경로에 남기지 않는다.

## 결과

rollout evidence helper는 선언된 snapshot을 다시 사용하고, 변경된 candidate 증거와
verified 승격 증거를 별도 revision으로 보존한다. 승격의 두 mutable ledger는 재실행 시
복구 가능한 journal을 통해 함께 갱신된다. pending snapshot은 그대로 유지한다.

## 검증

- transaction journal, rollback, symlink, missing-target, identity orphan, quarantine,
  finalization marker, special-mode, fsync 및 immutable snapshot 회귀를 포함한 중앙 ledger
  테스트 62개 통과.
- Issue #260 후보에서 catalog audit, authority policy, checksum, rollout lifecycle,
  publication POM 테스트 등 연관 Python 테스트 127개 통과.
- 후보 전체 Python 테스트 576개 통과, 2개는 외부 SNAPSHOT 저장소의 403 응답으로
  스킵되었다.
- 변경된 Python 파일의 `ruff check`, `py_compile`, `git diff --check`가 통과했다.
- Issue #260 후보의 `./gradlew build --no-daemon --console=plain` 통과.
- managed catalog sync와 Dependabot ignore sync 통과.
- `sync-shared-versions.py --check`는 Projects checkout의 기존 alias 중복 7건으로
  실패했다. 이는 이번 후보의 version refs와 다른 기존 정합성 문제로 남겼다.
- publication POM 검증은 후보 worktree와 `bluetape4k-exposed` checkout의 dirty gate에서
  중단되므로, clean candidate 및 downstream checkout에서 다시 확인한다.
- downstream repositories의 새 immutable catalog ref를 생성하거나 검증하지 않았다.

## 향후 지침

central rollout 증거를 갱신할 때 mutable input을 immutable snapshot 경로로 직접 복사하지
않는다. central row가 가리키는 파일을 먼저 읽고 해시를 확인한다. lifecycle 상태나 audit
증거가 바뀌면 새 revision을 만들고 row의 경로와 해시를 함께 갱신한다. 여러 파일의
상태 전이가 interruption에 민감하면 journal을 남기고 다음 실행에서 검증·복구한다.
검증된 receipt 경로나 기존 pending snapshot을 재사용하거나 덮어쓰지 않는다.

GNO canonical indexing은 이 lesson이 integration branch에 포함되고 canonical checkout이
동기화된 뒤 CG-18에서 수행한다. 현재 feature candidate에서 인덱싱하지 않는다.
