# Kafka Consumer Lag Remediation

## Overview
A consumer group falls behind its producers on one or more partitions: group
lag grows while per-message processing time and/or missing parallelism throttle
throughput. Lag and the throughput imbalance are directly observed; whether
scaling consumers alone resolves it depends on whether per-message processing
time is the true bottleneck.

## Solution
1. Identify whether processing latency or insufficient parallelism is the
   limiting factor.
2. Scale consumers where partitioning allows.
3. Review `max.poll.interval.ms` and batch size against measured processing time.
4. Monitor lag/throughput after the change.

## Troubleshooting
- Growing `groupLag` + `processingTime` at/above threshold → per-message
  latency limited; fix the slow processing path first.
- `groupLag` growing with `processingTime` well below threshold → parallelism
  limited; scale consumers.