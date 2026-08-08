# 조직 의존성 거버넌스

## 배경

독립적으로 생성된 Dependabot PR은 bluetape4k 조직의 다른 저장소를 업데이트하지
않은 채 한 저장소의 동일한 공유 의존성 별칭만 변경할 수 있다. 이로 인해
`spring-kafka4`와 같은 호환성 라인 별칭도 깨질 수 있다.

## 결정

`bluetape4k-dependencies`가 전체 공유 버전 매트릭스를 관리해야 하며, CI는 동기화
스크립트와 동일한 저장소 목록을 사용해 조직에서 설정한 저장소를 검사해야 한다.

## 결과

공유 버전 동기화 스크립트가 이제 활성 Gradle 저장소를 모두 포함하고 호환성 라인
별칭의 메이저 버전을 검증한다. Dependabot PR을 반복해서 유발한 중앙 의존성 라인은
이제 중앙 카탈로그에 반영되며, 다운스트림 Dependabot ignore 블록은 하나의
매니페스트에서 생성된다.

## 검증

- 저장소 목록 출력과 호환성 라인 검증을 위한 단위 테스트를 추가했다.
- 생성된 다운스트림 Dependabot ignore 블록을 검증하는 단위 테스트를 추가했다.
- CI에서 복제할 저장소 목록은 `scripts/sync-shared-versions.py --print-default-repositories`를
  사용한다.
- CI는 `scripts/sync-dependabot-ignores.py --workspace .. --check --summary`도
  검사한다.

## 향후 방어 규칙

워크플로 YAML에 하드코딩한 저장소 목록을 별도로 관리하지 않는다. 거버넌스
스크립트에서 목록을 생성해 CI와 로컬 검사가 동일한 범위를 다루도록 한다.
중앙에서 관리하는 의존성에 대한 다운스트림 Dependabot PR을 먼저 병합하지 않는다.
`bluetape4k-dependencies`를 먼저 업데이트하고, 카탈로그를 동기화한 다음,
Dependabot ignore 블록을 동기화한다.
