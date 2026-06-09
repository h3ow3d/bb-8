from __future__ import annotations

import logging
from typing import Any

from kubernetes import client  # type: ignore[import-untyped]
from kubernetes.client import ApiClient  # type: ignore[import-untyped]

from app.k8s.client import safe_get
from app.k8s.models import (
    ClusterRoleBindingInfo,
    ClusterRoleInfo,
    ClusterSnapshot,
    CronJobInfo,
    DaemonSetInfo,
    DeploymentInfo,
    EventInfo,
    IngressInfo,
    JobInfo,
    LimitRangeInfo,
    NetworkPolicyInfo,
    NodeInfo,
    PodDisruptionBudgetInfo,
    PodInfo,
    ResourceQuotaInfo,
    RoleBindingInfo,
    RoleInfo,
    ServiceAccountInfo,
    ServiceInfo,
    StatefulSetInfo,
)

logger = logging.getLogger(__name__)


def _safe_list(fn: Any, *args: Any, **kwargs: Any) -> list[Any]:
    """Call a list function and return items, or empty list on failure."""
    try:
        result = fn(*args, **kwargs)
        return result.items or []
    except Exception as exc:
        logger.warning("Collection error in %s: %s", getattr(fn, "__name__", fn), exc)
        return []


def collect_snapshot(api_client: ApiClient) -> ClusterSnapshot:
    """Collect a bounded snapshot of cluster state. Never reads Secrets."""
    core = client.CoreV1Api(api_client)
    apps = client.AppsV1Api(api_client)
    batch = client.BatchV1Api(api_client)
    networking = client.NetworkingV1Api(api_client)
    rbac = client.RbacAuthorizationV1Api(api_client)
    policy = client.PolicyV1Api(api_client)

    snapshot = ClusterSnapshot()

    # Namespaces
    ns_list = _safe_list(core.list_namespace)
    snapshot.namespaces = [safe_get(ns, "metadata", "name", default="") for ns in ns_list]

    # Nodes
    for node in _safe_list(core.list_node):
        conds = []
        for c in safe_get(node, "status", "conditions") or []:
            conds.append(
                {
                    "type": safe_get(c, "type", default=""),
                    "status": safe_get(c, "status", default=""),
                    "reason": safe_get(c, "reason", default=""),
                    "message": safe_get(c, "message", default=""),
                }
            )
        snapshot.nodes.append(
            NodeInfo(
                name=safe_get(node, "metadata", "name", default=""),
                conditions=conds,
                allocatable=dict(safe_get(node, "status", "allocatable") or {}),
                capacity=dict(safe_get(node, "status", "capacity") or {}),
                labels=dict(safe_get(node, "metadata", "labels") or {}),
            )
        )

    # Pods
    for pod in _safe_list(core.list_pod_for_all_namespaces):
        container_statuses = []
        for cs in safe_get(pod, "status", "container_statuses") or []:
            state = safe_get(cs, "state")
            state_info: dict[str, Any] = {}
            if state:
                if safe_get(state, "running"):
                    state_info = {"running": True}
                elif safe_get(state, "waiting"):
                    state_info = {
                        "waiting": {
                            "reason": safe_get(state, "waiting", "reason", default=""),
                            "message": safe_get(state, "waiting", "message", default=""),
                        }
                    }
                elif safe_get(state, "terminated"):
                    state_info = {
                        "terminated": {
                            "reason": safe_get(state, "terminated", "reason", default=""),
                            "exit_code": safe_get(state, "terminated", "exit_code", default=0),
                        }
                    }
            container_statuses.append(
                {
                    "name": safe_get(cs, "name", default=""),
                    "ready": safe_get(cs, "ready", default=False),
                    "restart_count": safe_get(cs, "restart_count", default=0),
                    "state": state_info,
                    "image": safe_get(cs, "image", default=""),
                }
            )

        spec_containers = []
        for c in safe_get(pod, "spec", "containers") or []:
            resources = safe_get(c, "resources")
            requests = dict(safe_get(resources, "requests") or {}) if resources else {}
            limits = dict(safe_get(resources, "limits") or {}) if resources else {}
            security_ctx = safe_get(c, "security_context")
            probes: dict[str, Any] = {
                "readiness_probe": safe_get(c, "readiness_probe") is not None,
                "liveness_probe": safe_get(c, "liveness_probe") is not None,
            }
            volumes_mounts = [
                {"name": safe_get(vm, "name", default=""), "mount_path": safe_get(vm, "mount_path", default="")}
                for vm in (safe_get(c, "volume_mounts") or [])
            ]
            env_count = len(safe_get(c, "env") or [])
            spec_containers.append(
                {
                    "name": safe_get(c, "name", default=""),
                    "image": safe_get(c, "image", default=""),
                    "resources": {"requests": requests, "limits": limits},
                    "security_context": {
                        "privileged": safe_get(security_ctx, "privileged", default=False) if security_ctx else False,
                        "run_as_non_root": safe_get(security_ctx, "run_as_non_root", default=None) if security_ctx else None,
                        "run_as_user": safe_get(security_ctx, "run_as_user", default=None) if security_ctx else None,
                        "allow_privilege_escalation": safe_get(security_ctx, "allow_privilege_escalation", default=None) if security_ctx else None,
                        "read_only_root_filesystem": safe_get(security_ctx, "read_only_root_filesystem", default=None) if security_ctx else None,
                    },
                    "probes": probes,
                    "volume_mounts": volumes_mounts,
                    "env_count": env_count,
                }
            )

        volumes = []
        for v in safe_get(pod, "spec", "volumes") or []:
            vol: dict[str, Any] = {"name": safe_get(v, "name", default="")}
            if safe_get(v, "host_path"):
                vol["host_path"] = safe_get(v, "host_path", "path", default="")
            volumes.append(vol)

        pod_conditions = []
        for pc in safe_get(pod, "status", "conditions") or []:
            pod_conditions.append(
                {
                    "type": safe_get(pc, "type", default=""),
                    "status": safe_get(pc, "status", default=""),
                }
            )

        snapshot.pods.append(
            PodInfo(
                name=safe_get(pod, "metadata", "name", default=""),
                namespace=safe_get(pod, "metadata", "namespace", default=""),
                phase=safe_get(pod, "status", "phase", default=""),
                conditions=pod_conditions,
                container_statuses=container_statuses,
                spec_containers=spec_containers,
                host_network=safe_get(pod, "spec", "host_network", default=False) or False,
                host_pid=safe_get(pod, "spec", "host_pid", default=False) or False,
                host_ipc=safe_get(pod, "spec", "host_ipc", default=False) or False,
                volumes=volumes,
                node_name=safe_get(pod, "spec", "node_name", default="") or "",
                labels=dict(safe_get(pod, "metadata", "labels") or {}),
                annotations=dict(safe_get(pod, "metadata", "annotations") or {}),
            )
        )

    # Deployments
    for dep in _safe_list(apps.list_deployment_for_all_namespaces):
        snapshot.deployments.append(
            DeploymentInfo(
                name=safe_get(dep, "metadata", "name", default=""),
                namespace=safe_get(dep, "metadata", "namespace", default=""),
                replicas=safe_get(dep, "spec", "replicas", default=0) or 0,
                ready_replicas=safe_get(dep, "status", "ready_replicas", default=0) or 0,
                available_replicas=safe_get(dep, "status", "available_replicas", default=0) or 0,
                unavailable_replicas=safe_get(dep, "status", "unavailable_replicas", default=0) or 0,
                labels=dict(safe_get(dep, "metadata", "labels") or {}),
            )
        )

    # StatefulSets
    for sts in _safe_list(apps.list_stateful_set_for_all_namespaces):
        snapshot.statefulsets.append(
            StatefulSetInfo(
                name=safe_get(sts, "metadata", "name", default=""),
                namespace=safe_get(sts, "metadata", "namespace", default=""),
                replicas=safe_get(sts, "spec", "replicas", default=0) or 0,
                ready_replicas=safe_get(sts, "status", "ready_replicas", default=0) or 0,
                labels=dict(safe_get(sts, "metadata", "labels") or {}),
            )
        )

    # DaemonSets
    for ds in _safe_list(apps.list_daemon_set_for_all_namespaces):
        snapshot.daemonsets.append(
            DaemonSetInfo(
                name=safe_get(ds, "metadata", "name", default=""),
                namespace=safe_get(ds, "metadata", "namespace", default=""),
                desired=safe_get(ds, "status", "desired_number_scheduled", default=0) or 0,
                ready=safe_get(ds, "status", "number_ready", default=0) or 0,
                unavailable=safe_get(ds, "status", "number_unavailable", default=0) or 0,
                labels=dict(safe_get(ds, "metadata", "labels") or {}),
            )
        )

    # Jobs
    for job in _safe_list(batch.list_job_for_all_namespaces):
        completions = safe_get(job, "spec", "completions")
        snapshot.jobs.append(
            JobInfo(
                name=safe_get(job, "metadata", "name", default=""),
                namespace=safe_get(job, "metadata", "namespace", default=""),
                succeeded=safe_get(job, "status", "succeeded", default=0) or 0,
                failed=safe_get(job, "status", "failed", default=0) or 0,
                active=safe_get(job, "status", "active", default=0) or 0,
                completions=int(completions) if completions is not None else None,
                labels=dict(safe_get(job, "metadata", "labels") or {}),
            )
        )

    # CronJobs
    for cj in _safe_list(batch.list_cron_job_for_all_namespaces):
        lst = safe_get(cj, "status", "last_schedule_time")
        snapshot.cronjobs.append(
            CronJobInfo(
                name=safe_get(cj, "metadata", "name", default=""),
                namespace=safe_get(cj, "metadata", "namespace", default=""),
                schedule=safe_get(cj, "spec", "schedule", default="") or "",
                suspended=safe_get(cj, "spec", "suspend", default=False) or False,
                last_schedule_time=str(lst) if lst else None,
                labels=dict(safe_get(cj, "metadata", "labels") or {}),
            )
        )

    # Services
    for svc in _safe_list(core.list_service_for_all_namespaces):
        ext_ips = list(safe_get(svc, "spec", "external_i_ps") or [])
        snapshot.services.append(
            ServiceInfo(
                name=safe_get(svc, "metadata", "name", default=""),
                namespace=safe_get(svc, "metadata", "namespace", default=""),
                service_type=safe_get(svc, "spec", "type", default="") or "",
                cluster_ip=safe_get(svc, "spec", "cluster_ip", default="") or "",
                external_ips=ext_ips,
                labels=dict(safe_get(svc, "metadata", "labels") or {}),
            )
        )

    # Ingresses
    for ing in _safe_list(networking.list_ingress_for_all_namespaces):
        hosts: list[str] = []
        tls_hosts: list[str] = []
        for rule in safe_get(ing, "spec", "rules") or []:
            h = safe_get(rule, "host", default="")
            if h:
                hosts.append(h)
        for tls in safe_get(ing, "spec", "tls") or []:
            tls_hosts.extend(safe_get(tls, "hosts") or [])
        snapshot.ingresses.append(
            IngressInfo(
                name=safe_get(ing, "metadata", "name", default=""),
                namespace=safe_get(ing, "metadata", "namespace", default=""),
                hosts=hosts,
                tls_hosts=tls_hosts,
                labels=dict(safe_get(ing, "metadata", "labels") or {}),
            )
        )

    # Events (warning only, limit 200)
    for ev in _safe_list(core.list_event_for_all_namespaces, field_selector="type=Warning", limit=200):
        snapshot.events.append(
            EventInfo(
                name=safe_get(ev, "metadata", "name", default=""),
                namespace=safe_get(ev, "metadata", "namespace", default=""),
                reason=safe_get(ev, "reason", default="") or "",
                message=safe_get(ev, "message", default="") or "",
                event_type=safe_get(ev, "type", default="") or "",
                regarding_name=safe_get(ev, "involved_object", "name", default="") or "",
                regarding_kind=safe_get(ev, "involved_object", "kind", default="") or "",
                count=safe_get(ev, "count", default=1) or 1,
                first_time=str(safe_get(ev, "first_timestamp")) if safe_get(ev, "first_timestamp") else None,
                last_time=str(safe_get(ev, "last_timestamp")) if safe_get(ev, "last_timestamp") else None,
            )
        )

    # ServiceAccounts
    for sa in _safe_list(core.list_service_account_for_all_namespaces):
        snapshot.service_accounts.append(
            ServiceAccountInfo(
                name=safe_get(sa, "metadata", "name", default=""),
                namespace=safe_get(sa, "metadata", "namespace", default=""),
                labels=dict(safe_get(sa, "metadata", "labels") or {}),
            )
        )

    # Roles
    for role in _safe_list(rbac.list_role_for_all_namespaces):
        rules_list = []
        for r in safe_get(role, "rules") or []:
            rules_list.append(
                {
                    "api_groups": list(safe_get(r, "api_groups") or []),
                    "resources": list(safe_get(r, "resources") or []),
                    "verbs": list(safe_get(r, "verbs") or []),
                }
            )
        snapshot.roles.append(
            RoleInfo(
                name=safe_get(role, "metadata", "name", default=""),
                namespace=safe_get(role, "metadata", "namespace", default=""),
                rules=rules_list,
            )
        )

    # RoleBindings
    for rb in _safe_list(rbac.list_role_binding_for_all_namespaces):
        subjects = [
            {
                "kind": safe_get(s, "kind", default=""),
                "name": safe_get(s, "name", default=""),
                "namespace": safe_get(s, "namespace", default=""),
            }
            for s in (safe_get(rb, "subjects") or [])
        ]
        snapshot.role_bindings.append(
            RoleBindingInfo(
                name=safe_get(rb, "metadata", "name", default=""),
                namespace=safe_get(rb, "metadata", "namespace", default=""),
                role_ref={
                    "kind": safe_get(rb, "role_ref", "kind", default=""),
                    "name": safe_get(rb, "role_ref", "name", default=""),
                },
                subjects=subjects,
            )
        )

    # ClusterRoles
    for cr in _safe_list(rbac.list_cluster_role):
        rules_list = []
        for r in safe_get(cr, "rules") or []:
            rules_list.append(
                {
                    "api_groups": list(safe_get(r, "api_groups") or []),
                    "resources": list(safe_get(r, "resources") or []),
                    "verbs": list(safe_get(r, "verbs") or []),
                }
            )
        snapshot.cluster_roles.append(
            ClusterRoleInfo(
                name=safe_get(cr, "metadata", "name", default=""),
                rules=rules_list,
            )
        )

    # ClusterRoleBindings
    for crb in _safe_list(rbac.list_cluster_role_binding):
        subjects = [
            {
                "kind": safe_get(s, "kind", default=""),
                "name": safe_get(s, "name", default=""),
                "namespace": safe_get(s, "namespace", default=""),
            }
            for s in (safe_get(crb, "subjects") or [])
        ]
        snapshot.cluster_role_bindings.append(
            ClusterRoleBindingInfo(
                name=safe_get(crb, "metadata", "name", default=""),
                role_ref={
                    "kind": safe_get(crb, "role_ref", "kind", default=""),
                    "name": safe_get(crb, "role_ref", "name", default=""),
                },
                subjects=subjects,
            )
        )

    # NetworkPolicies
    for np in _safe_list(networking.list_network_policy_for_all_namespaces):
        snapshot.network_policies.append(
            NetworkPolicyInfo(
                name=safe_get(np, "metadata", "name", default=""),
                namespace=safe_get(np, "metadata", "namespace", default=""),
                pod_selector=dict(safe_get(np, "spec", "pod_selector") or {}),
                policy_types=list(safe_get(np, "spec", "policy_types") or []),
            )
        )

    # ResourceQuotas
    for rq in _safe_list(core.list_resource_quota_for_all_namespaces):
        snapshot.resource_quotas.append(
            ResourceQuotaInfo(
                name=safe_get(rq, "metadata", "name", default=""),
                namespace=safe_get(rq, "metadata", "namespace", default=""),
                hard=dict(safe_get(rq, "spec", "hard") or {}),
                used=dict(safe_get(rq, "status", "used") or {}),
            )
        )

    # LimitRanges
    for lr in _safe_list(core.list_limit_range_for_all_namespaces):
        limits = []
        for li in safe_get(lr, "spec", "limits") or []:
            limits.append(
                {
                    "type": safe_get(li, "type", default=""),
                    "default": dict(safe_get(li, "default") or {}),
                    "default_request": dict(safe_get(li, "default_request") or {}),
                    "max": dict(safe_get(li, "max") or {}),
                    "min": dict(safe_get(li, "min") or {}),
                }
            )
        snapshot.limit_ranges.append(
            LimitRangeInfo(
                name=safe_get(lr, "metadata", "name", default=""),
                namespace=safe_get(lr, "metadata", "namespace", default=""),
                limits=limits,
            )
        )

    # PodDisruptionBudgets
    for pdb in _safe_list(policy.list_pod_disruption_budget_for_all_namespaces):
        min_av = safe_get(pdb, "spec", "min_available")
        max_un = safe_get(pdb, "spec", "max_unavailable")
        snapshot.pod_disruption_budgets.append(
            PodDisruptionBudgetInfo(
                name=safe_get(pdb, "metadata", "name", default=""),
                namespace=safe_get(pdb, "metadata", "namespace", default=""),
                min_available=str(min_av) if min_av is not None else None,
                max_unavailable=str(max_un) if max_un is not None else None,
                current_healthy=safe_get(pdb, "status", "current_healthy", default=0) or 0,
                desired_healthy=safe_get(pdb, "status", "desired_healthy", default=0) or 0,
            )
        )

    return snapshot
