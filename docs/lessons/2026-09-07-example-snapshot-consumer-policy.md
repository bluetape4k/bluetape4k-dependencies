# 예제 저장소의 개발 BOM 정책은 live ref와 함께 검증한다

## 배경

중앙 CI는 `bluetape4k-workshop/develop`이 이미
`bluetape4k-dependencies:2.1.0-SNAPSHOT`을 소비하는데도 예제 저장소를 안정
`2.0.0` 소비자로 분류해 실패했다. 초기 점검에서는 오래된 로컬 checkout을
기준으로 상태를 판단해 사용자의 정정을 받았다.

## 결정

다섯 예제·애플리케이션 저장소를 모두 다음 개발선 소비자로 관리한다.

- `bluetape4k-workshop`
- `clinic-appointment`
- `exposed-r2dbc-workshop`
- `exposed-workshop`
- `timefold-workshop`

중앙 정책은 이 저장소들을 `development-snapshot-repositories`에 두고
`2.1.0-SNAPSHOT`을 요구한다. 안정 소비자 목록이 비어 있는 상태도 유효한
정책으로 검증한다.

## 결과

정책 테스트는 예제 저장소 다섯 개의 분류와 버전을 함께 고정한다. cross-repo
검증은 로컬 checkout 상태가 아니라 각 저장소의 최신 `origin/develop`과 후보
worktree를 조합해 실행한다. 검증 과정에서 발견한 `bluetape4k-graph`의 새
catalog ref도 live 상태에 맞는 명시적 override로 기록했다.

## 놓친 점과 재발 방지

교차 저장소 정책을 판정할 때 로컬 working tree가 clean인지 여부만 확인하면
원격 기본 브랜치보다 오래된 상태를 현재 사실로 오인할 수 있다. 앞으로는 다음
순서를 지킨다.

1. `git fetch origin develop` 또는 live GitHub 조회로 현재 원격 ref를 고정한다.
2. 정책 manifest와 실제 `origin/develop`의 catalog/BOM ref를 비교한다.
3. 후보 변경은 별도 worktree로 덮어쓴 임시 workspace에서 검증한다.
4. 사용자가 상태를 정정하면 같은 작업의 lesson과 회귀 테스트에 반영한다.
