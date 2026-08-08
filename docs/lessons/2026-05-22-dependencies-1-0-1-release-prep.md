# Dependencies 1.0.1 릴리스 준비

## 배경

업스트림 bluetape4k 생태계 릴리스 트레인에서 projects, AWS, Exposed, image,
Javers, text, graph의 새 아티팩트가 발행되었다. 중앙 BOM/카탈로그는 여전히 여러
스냅샷과 이전 릴리스 라인을 참조하고 있었다.

## 결정

현재 생태계 트레인을 위한 조정된 BOM/카탈로그 릴리스로
`bluetape4k-dependencies` 1.0.1을 준비한다. leader 저장소의 릴리스를 의도적으로
연기했으므로 `bluetape4k-leader`는 0.1.0으로 유지한다.

## 결과

1.0.1 릴리스 게이트를 위해 릴리스 메타데이터, 버전 카탈로그, CHANGELOG, WIP 및
릴리스 준비용 release-prep lesson을 업데이트했다.

## 검증

릴리스 PR을 열기 전에 Gradle 릴리스 버전, 관리 카탈로그 생성, 공유 버전 정렬,
발행 POM 생성, 오래된/스냅샷 POM 부재, 빌드 및 로컬 Maven 발행을 검증했다. 관리
카탈로그 생성기는 연기된 leader 릴리스가 발행될 때까지 발행되지 않은 leader 모듈
(`consul`, `etcd`, `k8s`)을 제외한다.

## 향후 참고

Maven Central에서 1.0.1 BOM을 확인하고 해당 버전 카탈로그 소스를 의도한 git
ref에서 사용할 수 있을 때까지 다음 거버넌스 또는 주요 의존성 업그레이드 작업을
승격하지 않는다.
