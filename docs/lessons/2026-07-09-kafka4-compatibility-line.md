# Lessons Learned - Kafka4 Compatibility Line (2026-07-09)

## Context

`bluetape4k-projects` Nightly(full) failed in the `kafka-resilience` group after the shared catalog moved `kafka4` to `4.3.1`.

## Decision

Keep the shared `kafka4` alias on `4.2.1` while `spring-kafka4` is `4.1.0`, because Spring Kafka embedded KRaft tests require the `KafkaClusterTestKit.clientProperties()` ABI available in Kafka `4.2.1`.

## Outcome

The source-of-truth catalog now documents the compatibility reason directly on the `kafka4` version line.

## Future Guard

Do not advance compatibility-line aliases by latest-version scraping alone. For `kafka4`, rerun downstream `:bluetape4k-kafka4:test` or equivalent dependency insight before promoting beyond `4.2.1`.
