from __future__ import annotations

from app.k8s.models import ClusterSnapshot
from app.rules.findings import Finding, make_finding

_BROAD_ROLES = {"cluster-admin", "admin", "edit"}
_ANONYMOUS_SUBJECTS = {"system:anonymous", "system:unauthenticated"}
_BROAD_GROUPS = {"system:masters"}


def check_privileged_containers(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for pod in snapshot.pods:
        for c in pod.spec_containers:
            sc = c.get("security_context", {})
            if sc.get("privileged"):
                findings.append(
                    make_finding(
                        id="security-privileged-container",
                        title=f"Privileged container: {pod.name}/{c.get('name', '')}",
                        severity="critical",
                        category="security",
                        resource_ref=f"Pod/{pod.name}",
                        namespace=pod.namespace,
                        evidence=f"container={c.get('name', '')} privileged=true",
                        recommendation="Remove privileged flag. Use specific capabilities instead.",
                    )
                )
    return findings


def check_root_containers(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for pod in snapshot.pods:
        for c in pod.spec_containers:
            sc = c.get("security_context", {})
            run_as_non_root = sc.get("run_as_non_root")
            run_as_user = sc.get("run_as_user")
            if run_as_non_root is False or (run_as_non_root is None and run_as_user in (0, None)):
                findings.append(
                    make_finding(
                        id="security-root-container",
                        title=f"Container may run as root: {pod.name}/{c.get('name', '')}",
                        severity="high",
                        category="security",
                        resource_ref=f"Pod/{pod.name}",
                        namespace=pod.namespace,
                        evidence=f"runAsNonRoot={run_as_non_root} runAsUser={run_as_user}",
                        recommendation="Set runAsNonRoot: true or specify a non-root runAsUser.",
                    )
                )
    return findings


def check_hostpath_mounts(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for pod in snapshot.pods:
        for vol in pod.volumes:
            if "host_path" in vol:
                findings.append(
                    make_finding(
                        id="security-hostpath-mount",
                        title=f"HostPath volume mount: {pod.name}",
                        severity="high",
                        category="security",
                        resource_ref=f"Pod/{pod.name}",
                        namespace=pod.namespace,
                        evidence=f"volume={vol.get('name', '')} path={vol.get('host_path', '')}",
                        recommendation="Avoid HostPath mounts. Use PersistentVolumeClaims instead.",
                    )
                )
    return findings


def check_host_network(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for pod in snapshot.pods:
        if pod.host_network:
            findings.append(
                make_finding(
                    id="security-host-network",
                    title=f"Pod uses hostNetwork: {pod.name}",
                    severity="high",
                    category="security",
                    resource_ref=f"Pod/{pod.name}",
                    namespace=pod.namespace,
                    evidence="hostNetwork=true",
                    recommendation="Disable hostNetwork unless absolutely required.",
                )
            )
    return findings


def check_host_pid(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for pod in snapshot.pods:
        if pod.host_pid:
            findings.append(
                make_finding(
                    id="security-host-pid",
                    title=f"Pod uses hostPID: {pod.name}",
                    severity="high",
                    category="security",
                    resource_ref=f"Pod/{pod.name}",
                    namespace=pod.namespace,
                    evidence="hostPID=true",
                    recommendation="Disable hostPID unless absolutely required.",
                )
            )
    return findings


def check_host_ipc(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for pod in snapshot.pods:
        if pod.host_ipc:
            findings.append(
                make_finding(
                    id="security-host-ipc",
                    title=f"Pod uses hostIPC: {pod.name}",
                    severity="high",
                    category="security",
                    resource_ref=f"Pod/{pod.name}",
                    namespace=pod.namespace,
                    evidence="hostIPC=true",
                    recommendation="Disable hostIPC unless absolutely required.",
                )
            )
    return findings


def check_loadbalancer_services(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for svc in snapshot.services:
        if svc.service_type == "LoadBalancer":
            findings.append(
                make_finding(
                    id="networking-loadbalancer-service",
                    title=f"LoadBalancer service exposes workload externally: {svc.name}",
                    severity="medium",
                    category="networking",
                    resource_ref=f"Service/{svc.name}",
                    namespace=svc.namespace,
                    evidence="type=LoadBalancer",
                    recommendation="Verify this service should be publicly exposed. Consider using an Ingress.",
                )
            )
    return findings


def check_ingresses(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for ing in snapshot.ingresses:
        if ing.hosts:
            findings.append(
                make_finding(
                    id="networking-ingress-exposed",
                    title=f"Ingress exposes hosts: {ing.name}",
                    severity="info",
                    category="networking",
                    resource_ref=f"Ingress/{ing.name}",
                    namespace=ing.namespace,
                    evidence=f"hosts={ing.hosts}",
                    recommendation="Verify TLS is configured and hosts are intentionally exposed.",
                )
            )
    return findings


def check_namespaces_without_network_policy(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    namespaces_with_np = {np.namespace for np in snapshot.network_policies}
    for ns in snapshot.namespaces:
        if ns not in namespaces_with_np and not ns.startswith("kube-"):
            findings.append(
                make_finding(
                    id="networking-no-network-policy",
                    title=f"Namespace without NetworkPolicy: {ns}",
                    severity="medium",
                    category="networking",
                    resource_ref=f"Namespace/{ns}",
                    namespace=ns,
                    evidence="No NetworkPolicy found",
                    recommendation="Add NetworkPolicies to restrict pod-to-pod communication.",
                )
            )
    return findings


def check_broad_rbac_bindings(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []

    for crb in snapshot.cluster_role_bindings:
        role_name = crb.role_ref.get("name", "")
        if role_name in _BROAD_ROLES:
            for subject in crb.subjects:
                subj_name = subject.get("name", "")
                findings.append(
                    make_finding(
                        id="rbac-broad-clusterrolebinding",
                        title=f"ClusterRoleBinding to broad role: {crb.name}",
                        severity="high",
                        category="rbac",
                        resource_ref=f"ClusterRoleBinding/{crb.name}",
                        namespace="",
                        evidence=f"role={role_name} subject={subj_name}",
                        recommendation=f"Review whether {subj_name} requires cluster-wide {role_name} access.",
                    )
                )

    for rb in snapshot.role_bindings:
        role_name = rb.role_ref.get("name", "")
        if role_name in _BROAD_ROLES:
            for subject in rb.subjects:
                subj_name = subject.get("name", "")
                findings.append(
                    make_finding(
                        id="rbac-broad-rolebinding",
                        title=f"RoleBinding to broad role: {rb.name}",
                        severity="medium",
                        category="rbac",
                        resource_ref=f"RoleBinding/{rb.name}",
                        namespace=rb.namespace,
                        evidence=f"role={role_name} subject={subj_name}",
                        recommendation=f"Review whether {subj_name} requires {role_name} access in this namespace.",
                    )
                )
    return findings


def check_anonymous_bindings(snapshot: ClusterSnapshot) -> list[Finding]:
    findings: list[Finding] = []

    all_bindings: list[tuple[str, str, list[dict[str, str]]]] = []
    for crb in snapshot.cluster_role_bindings:
        all_bindings.append((f"ClusterRoleBinding/{crb.name}", "", crb.subjects))
    for rb in snapshot.role_bindings:
        all_bindings.append((f"RoleBinding/{rb.name}", rb.namespace, rb.subjects))

    for ref, ns, subjects in all_bindings:
        for subject in subjects:
            subj_name = subject.get("name", "")
            if subj_name in _ANONYMOUS_SUBJECTS or subject.get("kind") == "Group" and subj_name in _BROAD_GROUPS:
                findings.append(
                    make_finding(
                        id="rbac-anonymous-binding",
                        title=f"Binding to anonymous or overly broad subject: {ref}",
                        severity="critical",
                        category="rbac",
                        resource_ref=ref,
                        namespace=ns,
                        evidence=f"subject={subj_name} kind={subject.get('kind', '')}",
                        recommendation="Remove bindings for system:anonymous and system:unauthenticated immediately.",
                    )
                )
    return findings


def run_all_security_checks(snapshot: ClusterSnapshot) -> list[Finding]:
    """Run all security checks."""
    checks = [
        check_privileged_containers,
        check_root_containers,
        check_hostpath_mounts,
        check_host_network,
        check_host_pid,
        check_host_ipc,
        check_loadbalancer_services,
        check_ingresses,
        check_namespaces_without_network_policy,
        check_broad_rbac_bindings,
        check_anonymous_bindings,
    ]
    results: list[Finding] = []
    for check in checks:
        results.extend(check(snapshot))
    return results
