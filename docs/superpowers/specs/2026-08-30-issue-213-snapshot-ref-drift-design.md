# Issue #213 SNAPSHOT catalog ref drift 처리 설계

## 문제

`bluetape4k-dependencies`의 개발선 검사는 모든 내부 라이브러리가 manifest에
기록된 catalog SHA와 정확히 같은 값을 사용하도록 강제한다. 라이브러리가
더 최신의 immutable catalog commit으로 정상 전진해도 중앙 manifest를 먼저
갱신하지 않으면 CI가 실패한다.

실패한 run `33290856108`에서 publication POM 검사는 9개 저장소와 186개
POM을 검증해 통과했다. `Build BOM`만 `bluetape4k-aws`가 기준
`91f9ea9336b5ea991f5675323a1cf25ccfd6f5ed`보다 최신인
`df64293753a9491b337852a158f89d4a93a1734a`를 사용한다는 이유로 실패했다.
AWS의 `settings.gradle.kts`와 CI ref는 서로 일치하며, `df642937...`는 기준
commit의 후속이자 현재 중앙 `develop`의 조상이다.

## 목표와 범위

- 개발선 SNAPSHOT consumer가 검증된 catalog history 안에서 앞으로 이동하는
  것을 허용한다.
- 각 consumer의 Gradle 설정과 CI가 같은 immutable SHA를 사용하도록 계속
  강제한다.
- 오래된 ref로의 rollback과 현재 candidate history 밖의 ref는 거부한다.
- stable release의 exact candidate pin과 publication gate는 변경하지 않는다.
- downstream 저장소나 공개 artifact를 이 변경에서 직접 수정·배포하지 않는다.

## 검토한 방식

### 1. 중앙 manifest의 exact SHA를 계속 갱신

현재 구현과 같아 변경이 작지만, 관련 없는 downstream merge가 중앙 CI를
계속 깨뜨린다. SNAPSHOT 개발선의 독립적인 전진을 허용하지 못하므로 제외한다.

### 2. SHA 형식과 settings/CI 일치만 검사

downstream 전진을 허용하지만, 기준보다 오래된 commit이나 중앙 develop에
병합되지 않은 commit도 통과할 수 있다. rollback과 재현성 경계를 충분히
보호하지 못하므로 제외한다.

### 3. immutable minimum ref와 ancestry를 검사

manifest ref를 저장소별 최소 허용선으로 해석한다. 실제 ref는 다음 조건을
모두 만족해야 한다.

1. `settings.gradle.kts`와 `.github/workflows/ci.yml`에서 동일하다.
2. 40자리 lowercase Git SHA다.
3. 해당 저장소의 최소 ref와 같거나 그 후속 commit이다.
4. 현재 중앙 candidate `HEAD`의 조상이다.

이 방식은 정상적인 forward drift를 허용하면서 rollback과 feature-branch-only
ref를 차단한다. 이 설계에서 이 방식을 사용한다.

## 구현 계약

`verify-post-publish-next-development-line.py`는 중앙 repository 경로를 받아
Git ancestry를 검사한다. `snapshot-catalog-ref`와 저장소별 override는 exact
값이 아니라 minimum ref로 해석한다. 호환성을 위해 manifest key는 유지하되
함수명, 오류 메시지, release checklist에서 minimum 의미를 명시한다.

CI의 `Build BOM` checkout은 ancestry 검사에 필요한 history를 가져오도록
`fetch-depth: 0`을 사용한다. `Publish Snapshot`은 이미 full history를
checkout하므로 별도 변경이 필요 없다.

검증 순서는 consumer별로 다음과 같다.

1. settings ref와 CI ref를 읽는다.
2. 두 값의 형식과 동일성을 검사한다.
3. 실제 ref와 minimum ref가 로컬 Git object로 존재하는지 검사한다.
4. `minimum <= actual <= candidate HEAD` ancestry를 검사한다.

한 조건이라도 실패하면 해당 consumer 이름, minimum ref, actual ref와 실패
경계를 포함한 오류를 반환한다.

## 실패 및 호환성 경계

- settings와 CI ref 불일치: 실패
- SHA가 아닌 branch/tag 문자열: 실패
- minimum ref보다 이전 commit: 실패
- 현재 candidate history 밖의 commit: 실패
- downstream repository HEAD만 변경되고 catalog ref가 유지됨: 통과
- catalog ref가 검증된 중앙 history 안에서 앞으로 이동함: 통과
- stable release candidate 비교: 기존 exact 정책 유지

## 테스트와 검증

- 기존 exact-ref mismatch fixture가 parity mismatch를 계속 거부하는지 확인한다.
- minimum ref와 같은 actual ref가 통과하는 테스트를 유지한다.
- minimum ref의 후속 actual ref가 통과하는 RED/GREEN 회귀 테스트를 추가한다.
- minimum ref 이전의 actual ref와 candidate history 밖의 actual ref가 실패하는
  테스트를 추가한다.
- Python 전체 suite, 실제 workspace consumer guard, catalog sync,
  cross-repository publication POM gate, Gradle build, `actionlint`,
  `git diff --check`를 실행한다.

## 실행 순서와 승인 경계

1. RED/GREEN으로 guard를 수정하고 로컬 검증을 완료한다.
2. `fix/issue-213-snapshot-ref-drift`에서 `develop` 대상 PR을 생성한다.
3. exact-head CI와 review가 끝나면 merge-ready에서 정지한다.
4. fresh merge 승인 뒤 병합한다. develop CI 성공은 자동
   `Publish Snapshot`을 시작하므로 merge 승인은 이 side effect를 포함해야 한다.
5. 공개 `bluetape4k-dependencies:2.0.0-SNAPSHOT` metadata/POM을 검증한 뒤
   `exposed-r2dbc-workshop#215`를 진행한다.
6. 두 consumer 증거가 모이면 dependencies #213과 Projects #1562를 재판정한다.

## 완료 조건

- AWS의 `df642937...` forward ref가 중앙 개발선 검사에서 통과한다.
- rollback, parity mismatch, history 밖 ref 회귀 테스트가 통과한다.
- publication POM gate가 failures=0을 유지한다.
- stable exact candidate 계약과 실제 publication state는 변경되지 않는다.
