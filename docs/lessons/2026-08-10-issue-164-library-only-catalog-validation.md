# Library-only catalog train 검증 범위를 명시한다

## 배경

Issue #164는 게시 가능한 `bluetape4k-*` 라이브러리만 대상으로 하고
`bluetape4k-experimental`, workshop, example 및 application repository를
명시적으로 제외했다.

## 발견

`sync-shared-versions.py`와 일부 catalog helper의 기본 repository 목록은
`bluetape4k-experimental`을 포함한다. 제외된 repository checkout이 없을 때
기본 목록으로 실행하면 실제 catalog 결함이 아닌 경로 탐색 실패가 발생한다.
또한 nested worktree에서 workspace 경로를 생략하면 `.worktrees`를 sibling
workspace로 오인할 수 있다.

## 결정

Library-only train에서는 다음을 명시한다.

- `sync-managed-catalog.py`에는 실제 workspace root를 전달한다.
- shared-version 및 Dependabot ignore 검사에는 승인된 library repository를
  `--repo`로 열거한다.
- publication POM gate는 repo-local verifier의 publisher inventory 9곳을 그대로
  사용한다.
- 제외 repository의 경로 실패를 code/test 실패로 보고하지 않고, scope를
  바로잡은 뒤 영향을 받는 gate부터 다시 실행한다.

## 결과와 검증

- managed catalog: aliases 168, sub-BOMs 8
- shared-version adoption: clean
- Dependabot ignore sync: clean
- publication POM gate: repositories 9, files/models 173, failures 0

향후 library-only catalog train도 사용자 승인 범위를 helper의 기본 inventory와
동일시하지 말고, 명시적 repository 목록과 workspace root로 검증해야 한다.
