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

## 후속 CI 실패: signing 고정 ref와 개발선 checkout의 혼용

[PR #247의 CI](https://github.com/bluetape4k/bluetape4k-dependencies/actions/runs/34183939370)는
Graph의 catalog ref가 정책과 다르다는 오류로 실패했다. Graph의 `develop`은
정책과 같은 `55b5269bddd2bd041d5f282abcd0238dc242c171`을 사용했다. 반면 CI는
signing 검증용 고정 커밋 `062d0ecc718705893595a760552936d2372ea739`을 checkout했고,
이 커밋의 catalog ref는 `850959d0ea5f76ac7e2c442400f47653d5f95eed`였다.
그 checkout을 개발선 검사에도 전달한 것이 원인이었다.

초기에는 Graph의 최신 ref가 바뀐 것으로 판단했지만, 두 checkout을 직접 비교한
뒤 이를 정정했다. 정책을 과거 signing ref에 맞추면 실제 `develop`과 Publish
Snapshot의 사전 검증이 반대로 실패하므로 Graph override와 signing manifest는
변경하지 않는다.

개발선 검증용 저장소는 `$RUNNER_TEMP/development-workspace`에 별도로 clone하고
검증기의 기존 `--workspace` 옵션으로 전달한다. Snapshot 소비자는 Publish
Snapshot과 동일하게 후보 브랜치를 우선하며, HTTP 404일 때만 `develop`을
선택한다. 다른 API 오류는 즉시 실패한다. signing checkout과 exact repository
map은 기존 경로에 보존한다.

회귀 테스트는 CI의 실제 shell 단계를 추출해 로컬 Git 저장소로 실행한다. 후보
브랜치 선택, 404 대체 경로, 403 중단, signing HEAD와 clean 상태 보존을 검증한다.
로컬 테스트 성공은 hosted CI 또는 Snapshot 게시 성공을 의미하지 않는다.
