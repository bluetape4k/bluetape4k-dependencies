# Snapshot 버전 매개변수화

배경: Central Portal 릴리스에서 `-SNAPSHOT`을 제거하기 위해서만
`gradle.properties`를 수정할 필요가 없어야 한다.

결정: 기본적으로 `snapshotVersion=`을 비워 두고,
`publish-snapshot.yml`에서 `-PsnapshotVersion=-SNAPSHOT`을 전달한다.

결과: `develop`은 릴리스 가능한 상태를 유지하고, 스냅샷 발행은 워크플로 명령에서
명시적으로 수행한다.

dependencies 관련 결과: 이제 생태계 BOM 카탈로그는 `bluetape4k-*` 좌표를 정식
릴리스 버전으로 유지한다. Central Portal 릴리스 전에 스냅샷 참조를 다시 추가해서는
안 된다. 버전 카탈로그에서는 `bluetape4k-dependencies`를 첫 번째 릴리스 트레인
별칭으로 유지한다. 릴리스 트레인 버전 별칭은 BOM 아티팩트 이름을 기준으로 정한다.
예를 들면 `bluetape4k-bom`, `bluetape4k-aws-bom`, `bluetape4k-exposed-bom`과
같이 지정한다.

릴리스 범위: `bluetape4k-experimental`과 `bluetape4k-workshop`은 Central Portal
릴리스 캠페인에서 제외한다. 따라서 기본 공유 버전 검증은 이 저장소들을 복제하거나
검증 게이트의 대상으로 삼아서는 안 된다.

검증: `actionlint .github/workflows/publish-snapshot.yml`;
`python3 -m unittest discover -s tests -p 'test_*.py'`.

향후 방어 규칙: `gradle.properties`의 기본값으로
`snapshotVersion=-SNAPSHOT`을 다시 추가하지 않는다.
