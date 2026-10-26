# 여러 저장소 Gradle wrapper train은 live inventory에서 시작한다

## 상황

Issue [#259](https://github.com/bluetape4k/bluetape4k-dependencies/issues/259)는
bluetape4k 라이브러리와 workshop 예제 저장소 전체의 Gradle wrapper를 `9.8.2`로
맞추는 작업이다. live GitHub의 `develop`을 조사한 결과 wrapper를 가진 저장소는
15개였고, Workshop과 Clinic은 이미 `9.8.2`로 병합되어 있었다. 나머지 13개는
`9.6.0`, `9.6.1`, `9.7.0`, `9.8.1`이 섞여 있었다.

기존 로컬 Issue #259 worktree에는 다른 작업의 커밋 기준과 dirty 파일이 함께 있었다.
그 상태에서 wrapper를 갱신하면 unrelated 변경을 PR에 포함하거나 오래된
`develop`을 기준으로 올릴 위험이 있었다.

## 결정 및 적용

- GNO는 과거 문서와 작업 흔적을 찾는 보조 자료로 사용하고, 대상 목록과 현재 버전은
  live GitHub API를 기준으로 확정한다.
- 각 남은 저장소를 최신 `origin/develop`에서 새
  `chore/issue-259-gradle-982-rollout` worktree로 분리한다. 기존 dirty worktree는
  보존한다.
- wrapper task에 Gradle distribution SHA-256
  `21bd5da2de49b642904077f38c0efdc7778e92b3ed0889392dca61b97e389607`을 사용하고,
  생성된 wrapper artifact만 포함한다.
- 중복 wrapper 레이아웃이 있는 Text는 두 properties와 두 JAR를 함께 갱신한다.
  Projects처럼 JAR와 Windows script가 이미 `9.8.2` wrapper와 일치하면 properties만
  변경한다.

## 결과

13개 isolated worktree의 모든 Gradle wrapper가 `9.8.2`를 가리킨다. 표준 wrapper
파일은 저장소별로 생성되었고 Text의 legacy 중복 경로도 같은 버전으로 맞췄다. Exposed의
첫 wrapper 실행은 기존 SHA-256 설정과 새 배포판이 일치하지 않아 실패했지만, 명시적인
`9.8.2` checksum으로 재실행해 통과했다. 아직 canonical checkout, 원격 branch, PR,
merge에는 side effect를 적용하지 않았다.

## 검증

- 각 저장소에서 `./gradlew wrapper --gradle-version 9.8.2` 또는 저장소의 동등한
  wrapper 갱신 명령이 `BUILD SUCCESSFUL`로 끝났다.
- 13개 worktree의 `./gradlew --version`이 모두 Gradle `9.8.2`를 보고했다.
- 모든 properties의 `distributionSha256Sum`이 위 checksum과 일치했고, 갱신된
  wrapper JAR의 SHA-256은
  `3b8a25775a69158b5ad2b1d17a80a88dc7b40a352a73eb27d06c612a7ce68e98`로 일치했다.
- 각 worktree에서 `git diff --check`가 통과했고 wrapper artifact 외 변경은 없었다.

## 향후 지침

다음 ecosystem-wide wrapper train에서는 먼저 GitHub 저장소 목록과 각
`gradle-wrapper.properties`를 조회해 target inventory를 고정한다. 기존 worktree의
branch 기준과 dirty 상태를 재사용하지 말고 최신 `origin/develop`에서 task worktree를
만든다. duplicate wrapper 경로와 기존 artifact의 호환 상태를 확인하고, 배포판
checksum을 명시한 뒤 properties, JAR, scripts의 exact diff를 확인한다. PR을 만든 뒤에는
각 exact head의 CI와 review/thread를 다시 읽고, merge와 canonical sync를 저장소별로
분리한다.
