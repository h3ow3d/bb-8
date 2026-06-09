from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NodeInfo:
    name: str
    conditions: list[dict[str, str]] = field(default_factory=list)
    allocatable: dict[str, str] = field(default_factory=dict)
    capacity: dict[str, str] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class PodInfo:
    name: str
    namespace: str
    phase: str = ""
    conditions: list[dict[str, str]] = field(default_factory=list)
    container_statuses: list[dict[str, Any]] = field(default_factory=list)
    init_container_statuses: list[dict[str, Any]] = field(default_factory=list)
    spec_containers: list[dict[str, Any]] = field(default_factory=list)
    spec_init_containers: list[dict[str, Any]] = field(default_factory=list)
    host_network: bool = False
    host_pid: bool = False
    host_ipc: bool = False
    volumes: list[dict[str, Any]] = field(default_factory=list)
    node_name: str = ""
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)


@dataclass
class DeploymentInfo:
    name: str
    namespace: str
    replicas: int = 0
    ready_replicas: int = 0
    available_replicas: int = 0
    unavailable_replicas: int = 0
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class StatefulSetInfo:
    name: str
    namespace: str
    replicas: int = 0
    ready_replicas: int = 0
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class DaemonSetInfo:
    name: str
    namespace: str
    desired: int = 0
    ready: int = 0
    unavailable: int = 0
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class JobInfo:
    name: str
    namespace: str
    succeeded: int = 0
    failed: int = 0
    active: int = 0
    completions: int | None = None
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class CronJobInfo:
    name: str
    namespace: str
    schedule: str = ""
    suspended: bool = False
    last_schedule_time: str | None = None
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class ServiceInfo:
    name: str
    namespace: str
    service_type: str = ""
    cluster_ip: str = ""
    external_ips: list[str] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class IngressInfo:
    name: str
    namespace: str
    hosts: list[str] = field(default_factory=list)
    tls_hosts: list[str] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class EventInfo:
    name: str
    namespace: str
    reason: str = ""
    message: str = ""
    event_type: str = ""
    regarding_name: str = ""
    regarding_kind: str = ""
    count: int = 1
    first_time: str | None = None
    last_time: str | None = None


@dataclass
class ServiceAccountInfo:
    name: str
    namespace: str
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class RoleInfo:
    name: str
    namespace: str
    rules: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class RoleBindingInfo:
    name: str
    namespace: str
    role_ref: dict[str, str] = field(default_factory=dict)
    subjects: list[dict[str, str]] = field(default_factory=list)


@dataclass
class ClusterRoleInfo:
    name: str
    rules: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ClusterRoleBindingInfo:
    name: str
    role_ref: dict[str, str] = field(default_factory=dict)
    subjects: list[dict[str, str]] = field(default_factory=list)


@dataclass
class NetworkPolicyInfo:
    name: str
    namespace: str
    pod_selector: dict[str, Any] = field(default_factory=dict)
    policy_types: list[str] = field(default_factory=list)


@dataclass
class ResourceQuotaInfo:
    name: str
    namespace: str
    hard: dict[str, str] = field(default_factory=dict)
    used: dict[str, str] = field(default_factory=dict)


@dataclass
class LimitRangeInfo:
    name: str
    namespace: str
    limits: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PodDisruptionBudgetInfo:
    name: str
    namespace: str
    min_available: str | None = None
    max_unavailable: str | None = None
    current_healthy: int = 0
    desired_healthy: int = 0


@dataclass
class ClusterSnapshot:
    context: str = ""
    namespaces: list[str] = field(default_factory=list)
    nodes: list[NodeInfo] = field(default_factory=list)
    pods: list[PodInfo] = field(default_factory=list)
    deployments: list[DeploymentInfo] = field(default_factory=list)
    statefulsets: list[StatefulSetInfo] = field(default_factory=list)
    daemonsets: list[DaemonSetInfo] = field(default_factory=list)
    jobs: list[JobInfo] = field(default_factory=list)
    cronjobs: list[CronJobInfo] = field(default_factory=list)
    services: list[ServiceInfo] = field(default_factory=list)
    ingresses: list[IngressInfo] = field(default_factory=list)
    events: list[EventInfo] = field(default_factory=list)
    service_accounts: list[ServiceAccountInfo] = field(default_factory=list)
    roles: list[RoleInfo] = field(default_factory=list)
    role_bindings: list[RoleBindingInfo] = field(default_factory=list)
    cluster_roles: list[ClusterRoleInfo] = field(default_factory=list)
    cluster_role_bindings: list[ClusterRoleBindingInfo] = field(default_factory=list)
    network_policies: list[NetworkPolicyInfo] = field(default_factory=list)
    resource_quotas: list[ResourceQuotaInfo] = field(default_factory=list)
    limit_ranges: list[LimitRangeInfo] = field(default_factory=list)
    pod_disruption_budgets: list[PodDisruptionBudgetInfo] = field(default_factory=list)
