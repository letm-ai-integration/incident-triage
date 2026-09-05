"""The ``model-data`` directory as the single source for RAG collections.

The investigation agents must be grounded in the *actual* mock data under
``incident-triage/ai-incident-triage/model-data``, never in a separate
hard-coded copy inside the agent code. This module is the only bridge between
those raw files and the FAISS vector store:

    model-data/*                                  model-data/k8s_logs.json
         │                                                 │
         ▼                                                 ▼
   ``logs`` collection                            ``k8s`` collection
   (db / third-party / app log lines)             (pod-level events)

They are loaded, grouped into retrieval-sized chunks per *service*, and pushed
into the shared vector store by ``scripts/ingest_model_data.py``. Every chunk
is tagged with the service (and source file + kind) so the Log and Kubernetes
agents retrieve incident-specific evidence by querying with the incident's
service + description.

No file here hard-codes incident content: it reads whatever physical files
exist under ``model-data`` at ingestion time and turns each row/line into a
chunk. Adding a new incident means adding its mock telemetry under
``model-data`` (and an incident JSON under ``data/incidents``) and re-running
the ingestion script -- no agent changes required.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

MODEL_DATA_DIR_NAME = "model-data"

# Files under model-data that belong to the *logs* collection.
LOG_PLAIN_FILES = (
    "db_logs.txt",
    "external_api_logs.txt",
    "logs_traces.txt",
    "incident_telemetry_logs.txt",
)


@dataclass(frozen=True)
class SourceChunk:
    """A single retrieval-ready chunk with the metadata the agents surface."""

    doc: str
    metadata: dict
    doc_id: str


def _model_data_dir() -> Path:
    # repo root = parent of the ``app`` package directory, i.e. ai-incident-triage/
    repo_root = Path(__file__).resolve().parent.parent.parent
    return repo_root / MODEL_DATA_DIR_NAME


def _service_from_pod(pod_name: str) -> str:
    """Map a pod name like ``backend-api-02`` to its service ``backend-api``."""
    return re.sub(r"-\d+$", "", pod_name or "")


def _service_from_txt(line: str) -> str | None:
    """Best-effort service id from a raw log/telemetry line.

    Prefers an explicit ``[service]`` token (db_logs) or a class/net-per-service,
    and falls back to the service embedded in a JSON envelope.
    """
    bracket = re.search(r"\[([a-z][a-z0-9-]+)\]", line)
    if bracket:
        return bracket.group(1)
    json_match = re.search(r'"service"\s*:\s*"([^"]+)"', line)
    if json_match:
        return json_match.group(1)
    # nginx-style ``"GET /api/v1/..."`` has no service label -- keep under a
    # gateway bucket so it stays retrievable for web/gateway incidents.
    if re.search(r'"\s*(GET|POST|PUT|DELETE|PATCH)\s+/', line):
        return "web-gateway"
    # Class logger like ``com.ecommerce.order.OrderController``.
    class_match = re.search(r"(?:ERROR|WARN|INFO|DEBUG)\s+com\.\w+\.(\w+)\.", line)
    if class_match:
        return class_match.group(1).lower()
    return None


def _chunk_by_service(
    lines: list[str],
    source: str,
    bucket_size: int = 40,
) -> list[SourceChunk]:
    """Group raw lines into coarse service-aligned chunks of bounded size.

    Bucketing per service keeps each chunk self-contained (retrieval finds the
    whole incident log story, not one isolated line) while bounding the number
    of embedded vectors so first-time ingestion stays fast.
    """
    buckets: dict[str, list[str]] = {}
    for line in lines:
        if not line.strip():
            continue
        service = _service_from_txt(line) or "unknown"
        buckets.setdefault(service, []).append(line)

    chunks: list[SourceChunk] = []
    for service, service_lines in sorted(buckets.items()):
        for i in range(0, max(1, len(service_lines)), bucket_size):
            part = service_lines[i : i + bucket_size]
            chunks.append(
                SourceChunk(
                    doc="\n".join(part),
                    metadata={
                        "source": "logs",
                        "source_file": source,
                        "service": service,
                        "kind": "logs",
                    },
                    doc_id=f"model-data:logs:{source}:{service}:{i // bucket_size}",
                )
            )
    return chunks


def _load_log_chunks() -> list[SourceChunk]:
    chunks: list[SourceChunk] = []
    for filename in LOG_PLAIN_FILES:
        path = _model_data_dir() / filename
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        chunks.extend(_chunk_by_service(text.splitlines(), source=filename))
    return chunks


def _load_metrics_chunks() -> list[SourceChunk]:
    chunks: list[SourceChunk] = []
    for filename in ("metrics.json", "incident_metrics.json"):
        path = _model_data_dir() / filename
        if not path.exists():
            continue
        rows = json.loads(path.read_text(encoding="utf-8"))
        grouped: dict[str, list[str]] = {}
        for row in rows:
            service = str(row.get("service") or "unknown")
            metric = f"{row.get('timestamp')} {service} {row.get('metric_name')}={row.get('value')}"
            grouped.setdefault(service, []).append(metric)
        for service, lines in sorted(grouped.items()):
            chunks.append(
                SourceChunk(
                    doc="\n".join(lines),
                    metadata={
                        "source": "metrics",
                        "source_file": filename,
                        "service": service,
                        "kind": "metrics",
                    },
                    doc_id=f"model-data:metrics:{filename}:{service}",
                )
            )
    return chunks


def _load_k8s_chunks() -> list[SourceChunk]:
    chunks: list[SourceChunk] = []
    for filename in ("k8s_logs.json", "incident_k8s.json"):
        path = _model_data_dir() / filename
        if not path.exists():
            continue
        rows = json.loads(path.read_text(encoding="utf-8"))
        indexed_by_key: dict[tuple[str, str], list[tuple[int, str]]] = {}
        for idx, row in enumerate(rows):
            pod = str(row.get("pod_name") or "unknown")
            namespace = str(row.get("namespace") or "default")
            service = _service_from_pod(pod)
            line = (
                f"[{row.get('timestamp')}] {row.get('log_level', 'INFO')} "
                f"{pod}/{namespace} {row.get('message')}"
            )
            indexed_by_key.setdefault((namespace, service), []).append((idx, line))

        # 1. Coarse per-(namespace, service) context chunk (the pod timeline).
        for (namespace, service), indexed in sorted(indexed_by_key.items()):
            chunks.append(
                SourceChunk(
                    doc="\n".join(line for _, line in indexed),
                    metadata={
                        "source": "k8s",
                        "source_file": filename,
                        "namespace": namespace,
                        "service": service,
                        "kind": "k8s",
                    },
                    doc_id=f"model-data:k8s:{namespace}:{service}:{filename}",
                )
            )
        # 2. Fine-grained chunks for every WARN/ERROR row so single decisive
        #    events (ImagePullBackOff, OOMKilled, BackOff restarts, probe
        #    failures) stay sharply retrievable instead of being diluted
        #    inside the large grouped timelines above.
        for (namespace, service), indexed in sorted(indexed_by_key.items()):
            for idx, line in indexed:
                level_match = re.match(r"\[[^\]]+\]\s+(\w+)", line)
                if not level_match or level_match.group(1) not in {"WARN", "ERROR"}:
                    continue
                digest = hashlib.sha1(f"{filename}:{idx}:{line}".encode()).hexdigest()[:12]
                chunks.append(
                    SourceChunk(
                        doc=line,
                        metadata={
                            "source": "k8s",
                            "source_file": filename,
                            "namespace": namespace,
                            "service": service,
                            "kind": "k8s-event",
                            "level": level_match.group(1),
                        },
                        doc_id=f"model-data:k8s-event:{digest}",
                    )
                )
    return chunks


def _load_deployment_chunks() -> list[SourceChunk]:
    path = _model_data_dir() / "deployment_events.json"
    if not path.exists():
        return []
    rows = json.loads(path.read_text(encoding="utf-8"))
    grouped: dict[str, list[str]] = {}
    for row in rows:
        service = str(row.get("service") or "unknown")
        grouped.setdefault(service, []).append(
            f"{row.get('timestamp')} ver={row.get('deploy_version')} "
            f"event={row.get('event_type')} by={row.get('initiated_by')}"
        )
    chunks: list[SourceChunk] = []
    for service, lines in sorted(grouped.items()):
        chunks.append(
            SourceChunk(
                doc="\n".join(lines),
                metadata={
                    "source": "events",
                    "source_file": "deployment_events.json",
                    "service": service,
                    "kind": "deployment",
                },
                doc_id=f"model-data:deployments:{service}",
            )
        )
    return chunks


def collection_source(collection_name: str) -> list[SourceChunk]:
    """Return the model-data chunks that belong to ``collection_name``."""
    if collection_name == "logs":
        return _load_log_chunks()
    if collection_name == "k8s":
        return _load_k8s_chunks()
    if collection_name == "metrics":
        return _load_metrics_chunks()
    if collection_name == "events":
        return _load_deployment_chunks()
    return []


def runbook_md() -> str:
    """Load the curated multi-incident runbook knowledge file (knowledge_base)."""
    path = Path(__file__).resolve().parent.parent.parent / "knowledge_base" / "runbooks" / "runbook.md"
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""