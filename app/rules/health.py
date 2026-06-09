from __future__ import annotations

from app.k8s.models import ClusterSnapshot
from app.rules.findings import Finding, make_finding


def check_pods_not_ready(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for pod in snapshot.pods:
        ready = False
        for c in pod.conditions:
            if c.get("type") == "Ready" and c.get("status") == "True":
                ready = True
                break
        if not ready and pod.phase not in ("Succeeded", ""):
            findings.append(
                make_finding(
                    id="health-pod-not-ready",
                    title=f"Pod not Ready: {pod.name}",
                    severity="medium",
                    category="health",
                    resource_ref=f"Pod/{pod.name}",
                    namespace=pod.namespace,
                    evidence=f"phase={pod.phase}",
                    recommendation="Check pod events and logs for details.",
                )
            )
    return findings


def check_crashloop(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for pod in snapshot.pods:
        for cs in pod.container_statuses:
            waiting = cs.get("state", {}).get("waiting", {})
            reason = waiting.get("reason", "")
            if reason == "CrashLoopBackOff":
                findings.append(
                    make_finding(
                        id="health-crashloop",
                        title=f"CrashLoopBackOff: {pod.name}/{cs.get('name', '')}",
                        severity="high",
                        category="health",
                        resource_ref=f"Pod/{pod.name}",
                        namespace=pod.namespace,
                        evidence=f"container={cs.get('name', '')} restarts={cs.get('restart_count', 0)}",
                        recommendation="Check container logs: kubectl logs -n {ns} {name} -c {container}",
                    )
                )
    return findings


def check_image_pull_errors(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    error_reasons = {"ImagePullBackOff", "ErrImagePull"}
    for pod in snapshot.pods:
        for cs in pod.container_statuses:
            waiting = cs.get("state", {}).get("waiting", {})
            reason = waiting.get("reason", "")
            if reason in error_reasons:
                findings.append(
                    make_finding(
                        id="health-image-pull-error",
                        title=f"Image pull error: {pod.name}/{cs.get('name', '')}",
                        severity="high",
                        category="health",
                        resource_ref=f"Pod/{pod.name}",
                        namespace=pod.namespace,
                        evidence=f"reason={reason} image={cs.get('image', '')}",
                        recommendation="Verify the image name, tag, and registry credentials.",
                    )
                )
    return findings


def check_pending_pods(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for pod in snapshot.pods:
        if pod.phase == "Pending":
            findings.append(
                make_finding(
                    id="health-pod-pending",
                    title=f"Pod Pending: {pod.name}",
                    severity="medium",
                    category="health",
                    resource_ref=f"Pod/{pod.name}",
                    namespace=pod.namespace,
                    evidence="phase=Pending",
                    recommendation="Check node resources, scheduling constraints, and pod events.",
                )
            )
    return findings


def check_failed_jobs(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for job in snapshot.jobs:
        if job.failed > 0:
            findings.append(
                make_finding(
                    id="health-job-failed",
                    title=f"Job has failures: {job.name}",
                    severity="medium",
                    category="health",
                    resource_ref=f"Job/{job.name}",
                    namespace=job.namespace,
                    evidence=f"failed={job.failed} succeeded={job.succeeded}",
                    recommendation="Inspect job pod logs and events for root cause.",
                )
            )
    return findings


def check_deployment_availability(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for dep in snapshot.deployments:
        if dep.unavailable_replicas > 0:
            findings.append(
                make_finding(
                    id="health-deployment-unavailable",
                    title=f"Deployment has unavailable replicas: {dep.name}",
                    severity="high",
                    category="health",
                    resource_ref=f"Deployment/{dep.name}",
                    namespace=dep.namespace,
                    evidence=f"unavailable={dep.unavailable_replicas} desired={dep.replicas}",
                    recommendation="Check rollout status and pod events.",
                )
            )
    return findings


def check_statefulset_availability(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for sts in snapshot.statefulsets:
        if sts.replicas > 0 and sts.ready_replicas < sts.replicas:
            findings.append(
                make_finding(
                    id="health-statefulset-unavailable",
                    title=f"StatefulSet has unavailable replicas: {sts.name}",
                    severity="high",
                    category="health",
                    resource_ref=f"StatefulSet/{sts.name}",
                    namespace=sts.namespace,
                    evidence=f"ready={sts.ready_replicas} desired={sts.replicas}",
                    recommendation="Check StatefulSet pod events and PVC status.",
                )
            )
    return findings


def check_daemonset_availability(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for ds in snapshot.daemonsets:
        if ds.unavailable > 0:
            findings.append(
                make_finding(
                    id="health-daemonset-unavailable",
                    title=f"DaemonSet has unavailable pods: {ds.name}",
                    severity="medium",
                    category="health",
                    resource_ref=f"DaemonSet/{ds.name}",
                    namespace=ds.namespace,
                    evidence=f"unavailable={ds.unavailable} desired={ds.desired}",
                    recommendation="Check node conditions and DaemonSet pod logs.",
                )
            )
    return findings


def check_node_conditions(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    problem_conditions = {"MemoryPressure", "DiskPressure", "PIDPressure", "NetworkUnavailable"}
    for node in snapshot.nodes:
        for cond in node.conditions:
            ctype = cond.get("type", "")
            cstatus = cond.get("status", "")
            if ctype == "Ready" and cstatus != "True":
                findings.append(
                    make_finding(
                        id="health-node-not-ready",
                        title=f"Node not Ready: {node.name}",
                        severity="critical",
                        category="health",
                        resource_ref=f"Node/{node.name}",
                        namespace="",
                        evidence=f"status={cstatus} reason={cond.get('reason', '')}",
                        recommendation="Investigate node health and connectivity.",
                    )
                )
            elif ctype in problem_conditions and cstatus == "True":
                findings.append(
                    make_finding(
                        id=f"health-node-{ctype.lower()}",
                        title=f"Node {ctype}: {node.name}",
                        severity="high",
                        category="health",
                        resource_ref=f"Node/{node.name}",
                        namespace="",
                        evidence=f"condition={ctype} status={cstatus}",
                        recommendation=f"Investigate node {ctype} condition.",
                    )
                )
    return findings


def check_warning_events(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for ev in snapshot.events:
        if ev.event_type == "Warning" and ev.count > 5:
            findings.append(
                make_finding(
                    id="health-warning-event",
                    title=f"Repeated Warning event: {ev.reason} on {ev.regarding_kind}/{ev.regarding_name}",
                    severity="low",
                    category="health",
                    resource_ref=f"{ev.regarding_kind}/{ev.regarding_name}",
                    namespace=ev.namespace,
                    evidence=f"count={ev.count} reason={ev.reason} message={ev.message[:100]}",
                    recommendation="Investigate the cause of repeated warning events.",
                )
            )
    return findings


def check_missing_resource_requests(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for pod in snapshot.pods:
        for c in pod.spec_containers:
            requests = c.get("resources", {}).get("requests", {})
            if not requests.get("cpu") or not requests.get("memory"):
                findings.append(
                    make_finding(
                        id="operational-missing-requests",
                        title=f"Container missing resource requests: {pod.name}/{c.get('name', '')}",
                        severity="low",
                        category="operational",
                        resource_ref=f"Pod/{pod.name}",
                        namespace=pod.namespace,
                        evidence=f"container={c.get('name', '')} requests={requests}",
                        recommendation="Add resource requests to enable proper scheduling.",
                    )
                )
    return findings


def check_missing_resource_limits(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for pod in snapshot.pods:
        for c in pod.spec_containers:
            limits = c.get("resources", {}).get("limits", {})
            if not limits.get("cpu") or not limits.get("memory"):
                findings.append(
                    make_finding(
                        id="operational-missing-limits",
                        title=f"Container missing resource limits: {pod.name}/{c.get('name', '')}",
                        severity="low",
                        category="operational",
                        resource_ref=f"Pod/{pod.name}",
                        namespace=pod.namespace,
                        evidence=f"container={c.get('name', '')} limits={limits}",
                        recommendation="Add resource limits to prevent resource contention.",
                    )
                )
    return findings


def check_missing_probes(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for pod in snapshot.pods:
        for c in pod.spec_containers:
            probes = c.get("probes", {})
            if not probes.get("readiness_probe"):
                findings.append(
                    make_finding(
                        id="operational-missing-readiness-probe",
                        title=f"Container missing readiness probe: {pod.name}/{c.get('name', '')}",
                        severity="low",
                        category="operational",
                        resource_ref=f"Pod/{pod.name}",
                        namespace=pod.namespace,
                        evidence=f"container={c.get('name', '')}",
                        recommendation="Add a readiness probe for reliable traffic routing.",
                    )
                )
            if not probes.get("liveness_probe"):
                findings.append(
                    make_finding(
                        id="operational-missing-liveness-probe",
                        title=f"Container missing liveness probe: {pod.name}/{c.get('name', '')}",
                        severity="info",
                        category="operational",
                        resource_ref=f"Pod/{pod.name}",
                        namespace=pod.namespace,
                        evidence=f"container={c.get('name', '')}",
                        recommendation="Add a liveness probe to enable automatic recovery.",
                    )
                )
    return findings


def check_namespaces_without_quota(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    namespaces_with_quota = {rq.namespace for rq in snapshot.resource_quotas}
    for ns in snapshot.namespaces:
        if ns not in namespaces_with_quota and not ns.startswith("kube-"):
            findings.append(
                make_finding(
                    id="operational-no-resource-quota",
                    title=f"Namespace without ResourceQuota: {ns}",
                    severity="low",
                    category="operational",
                    resource_ref=f"Namespace/{ns}",
                    namespace=ns,
                    evidence="No ResourceQuota found",
                    recommendation="Add a ResourceQuota to enforce resource constraints.",
                )
            )
    return findings


def check_namespaces_without_limitrange(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    namespaces_with_lr = {lr.namespace for lr in snapshot.limit_ranges}
    for ns in snapshot.namespaces:
        if ns not in namespaces_with_lr and not ns.startswith("kube-"):
            findings.append(
                make_finding(
                    id="operational-no-limit-range",
                    title=f"Namespace without LimitRange: {ns}",
                    severity="info",
                    category="operational",
                    resource_ref=f"Namespace/{ns}",
                    namespace=ns,
                    evidence="No LimitRange found",
                    recommendation="Add a LimitRange to set default resource constraints.",
                )
            )
    return findings


def run_all_health_checks(snapshot: ClusterSnapshot) -> list[Finding]:
    """Run all health and operational checks."""
    checks = [
        check_pods_not_ready,
        check_crashloop,
        check_image_pull_errors,
        check_pending_pods,
        check_failed_jobs,
        check_deployment_availability,
        check_statefulset_availability,
        check_daemonset_availability,
        check_node_conditions,
        check_warning_events,
        check_missing_resource_requests,
        check_missing_resource_limits,
        check_missing_probes,
        check_namespaces_without_quota,
        check_namespaces_without_limitrange,
    ]
    results: list[Finding] = []
    for check in checks:
        results.extend(check(snapshot))
    return results
