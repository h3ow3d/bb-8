"""Tests for security rules - deterministic, no live cluster needed."""
from __future__ import annotations

from app.k8s.models import (
    ClusterRoleBindingInfo,
    ClusterSnapshot,
    IngressInfo,
    NetworkPolicyInfo,
    PodInfo,
    RoleBindingInfo,
    ServiceInfo,
)
from app.rules.security import (
    check_anonymous_bindings,
    check_broad_rbac_bindings,
    check_host_ipc,
    check_host_network,
    check_host_pid,
    check_hostpath_mounts,
    check_ingresses,
    check_loadbalancer_services,
    check_namespaces_without_network_policy,
    check_privileged_containers,
    check_root_containers,
    run_all_security_checks,
)


def _make_pod(name="test-pod", namespace="default", spec_containers=None, **kwargs):
    defaults = {
        "phase": "Running",
        "conditions": [{"type": "Ready", "status": "True"}],
        "container_statuses": [],
        "spec_containers": spec_containers or [{
            "name": "app",
            "image": "nginx",
            "resources": {"requests": {}, "limits": {}},
            "security_context": {
                "privileged": False,
                "run_as_non_root": True,
                "run_as_user": 1000,
                "allow_privilege_escalation": None,
                "read_only_root_filesystem": None,
            },
            "probes": {"readiness_probe": True, "liveness_probe": True},
            "volume_mounts": [],
            "env_count": 0,
        }],
    }
    defaults.update(kwargs)
    return PodInfo(name=name, namespace=namespace, **defaults)


class TestPrivilegedContainers:
    def test_privileged_container_detected(self):
        snap = ClusterSnapshot()
        snap.pods = [_make_pod(spec_containers=[{
            "name": "app", "image": "nginx",
            "resources": {"requests": {}, "limits": {}},
            "security_context": {"privileged": True, "run_as_non_root": None, "run_as_user": None},
            "probes": {"readiness_probe": True, "liveness_probe": True},
            "volume_mounts": [], "env_count": 0,
        }])]
        findings = check_privileged_containers(snap)
        assert len(findings) == 1
        assert findings[0].id == "security-privileged-container"
        assert findings[0].severity == "critical"

    def test_non_privileged_no_finding(self):
        snap = ClusterSnapshot()
        snap.pods = [_make_pod()]
        findings = check_privileged_containers(snap)
        assert findings == []


class TestRootContainers:
    def test_no_run_as_non_root_flagged(self):
        snap = ClusterSnapshot()
        snap.pods = [_make_pod(spec_containers=[{
            "name": "app", "image": "nginx",
            "resources": {"requests": {}, "limits": {}},
            "security_context": {"privileged": False, "run_as_non_root": None, "run_as_user": None},
            "probes": {"readiness_probe": True, "liveness_probe": True},
            "volume_mounts": [], "env_count": 0,
        }])]
        findings = check_root_containers(snap)
        assert len(findings) == 1
        assert findings[0].id == "security-root-container"
        assert findings[0].severity == "high"

    def test_run_as_root_false_no_finding(self):
        snap = ClusterSnapshot()
        snap.pods = [_make_pod(spec_containers=[{
            "name": "app", "image": "nginx",
            "resources": {"requests": {}, "limits": {}},
            "security_context": {"privileged": False, "run_as_non_root": True, "run_as_user": 1000},
            "probes": {"readiness_probe": True, "liveness_probe": True},
            "volume_mounts": [], "env_count": 0,
        }])]
        findings = check_root_containers(snap)
        assert findings == []


class TestHostPathMounts:
    def test_hostpath_volume_detected(self):
        snap = ClusterSnapshot()
        snap.pods = [PodInfo(
            name="my-pod", namespace="default",
            volumes=[{"name": "host-vol", "host_path": "/var/log"}]
        )]
        findings = check_hostpath_mounts(snap)
        assert len(findings) == 1
        assert findings[0].id == "security-hostpath-mount"

    def test_no_hostpath_no_finding(self):
        snap = ClusterSnapshot()
        snap.pods = [PodInfo(name="my-pod", namespace="default", volumes=[{"name": "configmap"}])]
        findings = check_hostpath_mounts(snap)
        assert findings == []


class TestHostNamespace:
    def test_host_network_detected(self):
        snap = ClusterSnapshot()
        snap.pods = [PodInfo(name="pod", namespace="default", host_network=True)]
        findings = check_host_network(snap)
        assert len(findings) == 1
        assert findings[0].id == "security-host-network"

    def test_host_pid_detected(self):
        snap = ClusterSnapshot()
        snap.pods = [PodInfo(name="pod", namespace="default", host_pid=True)]
        findings = check_host_pid(snap)
        assert len(findings) == 1
        assert findings[0].id == "security-host-pid"

    def test_host_ipc_detected(self):
        snap = ClusterSnapshot()
        snap.pods = [PodInfo(name="pod", namespace="default", host_ipc=True)]
        findings = check_host_ipc(snap)
        assert len(findings) == 1
        assert findings[0].id == "security-host-ipc"


class TestLoadBalancerServices:
    def test_lb_service_detected(self):
        snap = ClusterSnapshot()
        snap.services = [ServiceInfo(name="my-svc", namespace="default", service_type="LoadBalancer")]
        findings = check_loadbalancer_services(snap)
        assert len(findings) == 1
        assert findings[0].id == "networking-loadbalancer-service"

    def test_clusterip_not_flagged(self):
        snap = ClusterSnapshot()
        snap.services = [ServiceInfo(name="my-svc", namespace="default", service_type="ClusterIP")]
        findings = check_loadbalancer_services(snap)
        assert findings == []


class TestIngresses:
    def test_ingress_with_host_flagged(self):
        snap = ClusterSnapshot()
        snap.ingresses = [IngressInfo(name="my-ing", namespace="default", hosts=["app.example.com"])]
        findings = check_ingresses(snap)
        assert len(findings) == 1
        assert findings[0].id == "networking-ingress-exposed"

    def test_ingress_without_host_not_flagged(self):
        snap = ClusterSnapshot()
        snap.ingresses = [IngressInfo(name="my-ing", namespace="default", hosts=[])]
        findings = check_ingresses(snap)
        assert findings == []


class TestNetworkPolicies:
    def test_namespace_without_np_detected(self):
        snap = ClusterSnapshot()
        snap.namespaces = ["default", "production"]
        snap.network_policies = []
        findings = check_namespaces_without_network_policy(snap)
        assert len(findings) == 2

    def test_namespace_with_np_not_flagged(self):
        snap = ClusterSnapshot()
        snap.namespaces = ["default"]
        snap.network_policies = [NetworkPolicyInfo(name="default-deny", namespace="default")]
        findings = check_namespaces_without_network_policy(snap)
        assert findings == []

    def test_kube_namespaces_excluded(self):
        snap = ClusterSnapshot()
        snap.namespaces = ["kube-system"]
        snap.network_policies = []
        findings = check_namespaces_without_network_policy(snap)
        assert findings == []


class TestBroadRBACBindings:
    def test_cluster_admin_binding_detected(self):
        snap = ClusterSnapshot()
        snap.cluster_role_bindings = [ClusterRoleBindingInfo(
            name="my-binding",
            role_ref={"kind": "ClusterRole", "name": "cluster-admin"},
            subjects=[{"kind": "User", "name": "alice"}]
        )]
        findings = check_broad_rbac_bindings(snap)
        assert len(findings) == 1
        assert findings[0].id == "rbac-broad-clusterrolebinding"
        assert findings[0].severity == "high"

    def test_limited_role_not_flagged(self):
        snap = ClusterSnapshot()
        snap.cluster_role_bindings = [ClusterRoleBindingInfo(
            name="safe-binding",
            role_ref={"kind": "ClusterRole", "name": "view"},
            subjects=[{"kind": "User", "name": "bob"}]
        )]
        findings = check_broad_rbac_bindings(snap)
        assert findings == []


class TestAnonymousBindings:
    def test_anonymous_subject_detected(self):
        snap = ClusterSnapshot()
        snap.cluster_role_bindings = [ClusterRoleBindingInfo(
            name="anon-binding",
            role_ref={"kind": "ClusterRole", "name": "view"},
            subjects=[{"kind": "User", "name": "system:anonymous"}]
        )]
        findings = check_anonymous_bindings(snap)
        assert len(findings) >= 1
        assert findings[0].severity == "critical"

    def test_unauthenticated_subject_detected(self):
        snap = ClusterSnapshot()
        snap.role_bindings = [RoleBindingInfo(
            name="bad-binding", namespace="default",
            role_ref={"kind": "Role", "name": "reader"},
            subjects=[{"kind": "Group", "name": "system:unauthenticated"}]
        )]
        findings = check_anonymous_bindings(snap)
        assert len(findings) >= 1


class TestRunAllSecurityChecks:
    def test_empty_cluster_returns_list(self):
        snap = ClusterSnapshot()
        results = run_all_security_checks(snap)
        assert isinstance(results, list)

    def test_multiple_issues_detected(self):
        snap = ClusterSnapshot()
        snap.pods = [PodInfo(name="bad-pod", namespace="default", host_network=True, host_pid=True)]
        snap.namespaces = ["default"]
        snap.network_policies = []
        results = run_all_security_checks(snap)
        assert len(results) >= 3
