# bluetape4k BOM 스냅샷 정렬

## 배경

Fory 0.17 업그레이드로 인해 `bluetape4k-projects` 아티팩트를 새 Fory API에 맞춰
다시 빌드해야 했다. 다운스트림 저장소는 여전히 `bluetape4k-dependencies`에서
`bluetape4k-bom:1.8.0`을 해석했으므로 Fory 0.17과 이전 `bluetape4k-io`
바이너리를 혼용했고 `NoSuchMethodError`로 실패했다.

## 결정

중앙 `bluetape4k-bom` 카탈로그 항목을 발행된 `bluetape4k-projects` 스냅샷 라인에
맞춰 `1.8.1-SNAPSHOT`으로 변경한다.

## 결과

다운스트림 저장소는 저장소별 재정의 대신 중앙 BOM을 통해 다시 빌드된 1.8.1
아티팩트를 받아야 한다.

## 검증

`bluetape4k-io:1.8.1-SNAPSHOT`과 `bluetape4k-assertions:1.8.1-SNAPSHOT`의 Maven
스냅샷 메타데이터를 확인했다. projects 스냅샷 발행 후 두 아티팩트가 모두
존재한다.

## 향후 지침

`bluetape4k-dependencies`에서 공유 런타임 라이브러리를 업그레이드할 때는 다운스트림
저장소를 동기화하기 전에 핵심 bluetape4k BOM 버전을 발행된 스냅샷 라인에 맞춘다.
