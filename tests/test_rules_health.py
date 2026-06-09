"""Tests for health rules - deterministic, no live cluster needed."""
from __future__ import annotations

from app.k8s.models import (
    ClusterSnapshot,
    DeploymentInfo,
    JobInfo,
    NodeInfo,
    PodInfo,
    ResourceQuotaInfo,
)
from app.rules.health import (
    check_crashloop,
    check_deployment_availability,
    check_failed_jobs,
    check_image_pull_errors,
    check_missing_probes,
    check_missing_resource_limits,
    check_missing_resource_requests,
    check_namespaces_without_quota,
    check_node_conditions,
    check_pending_pods,
    check_pods_not_ready,
    run_all_health_checks,
)


def _make_pod(name="test-pod", namespace="default", phase="Running", conditions=None, container_statuses=None, spec_containers=None):
    return PodInfo(
        name=name,
        namespace=namespace,
        phase=phase,
        conditions=conditions or [{"type": "Ready", "status": "True"}],
        container_statuses=container_statuses or [{"name": "app", "ready": True, "restart_count": 0, "state": {"running": True}, "image": "nginx:latest"}],
        spec_containers=spec_containers or [
            {
                "name": "app",
                "image": "nginx:latest",
                "resources": {"requests": {"cpu": "100m", "memory": "128Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}},
                "security_context": {"privileged": False, "run_as_non_root": True, "run_as_user": 1000},
                "probes": {"readiness_probe": True, "liveness_probe": True},
                "volume_mounts": [],
                "env_count": 0,
            }
        ],
    )


class TestPodsNotReady:
    def test_ready_pod_no_finding(self):
        snap = ClusterSnapshot()
        snap.pods = [_make_pod(conditions=[{"type": "Ready", "status": "True"}])]
        findings = check_pods_not_ready(snap)
        assert findings == []

    def test_not_ready_pod_has_finding(self):
        snap = ClusterSnapshot()
        snap.pods = [_make_pod(
            phase="Running",
            conditions=[{"type": "Ready", "status": "False"}]
        )]
        findings = check_pods_not_ready(snap)
        assert len(findings) == 1
        assert findings[0].id == "health-pod-not-ready"
        assert findings[0].severity == "medium"

    def test_succeeded_pod_no_finding(self):
        snap = ClusterSnapshot()
        snap.pods = [_make_pod(phase="Succeeded", conditions=[{"type": "Ready", "status": "False"}])]
        findings = check_pods_not_ready(snap)
        assert findings == []


class TestCrashLoop:
    def test_crashloop_detected(self):
        snap = ClusterSnapshot()
        snap.pods = [_make_pod(
            container_statuses=[{
                "name": "app",
                "ready": False,
                "restart_count": 5,
                "state": {"waiting": {"reason": "CrashLoopBackOff"}},
                "image": "myapp:v1",
            }]
        )]
        findings = check_crashloop(snap)
        assert len(findings) == 1
        assert findings[0].id == "health-crashloop"
        assert findings[0].severity == "high"

    def test_running_container_no_finding(self):
        snap = ClusterSnapshot()
        snap.pods = [_make_pod()]
        findings = check_crashloop(snap)
        assert findings == []


class TestImagePullErrors:
    def test_image_pull_backoff_detected(self):
        snap = ClusterSnapshot()
        snap.pods = [_make_pod(
            container_statuses=[{
                "name": "app",
                "ready": False,
                "restart_count": 0,
                "state": {"waiting": {"reason": "ImagePullBackOff"}},
                "image": "missing:image",
            }]
        )]
        findings = check_image_pull_errors(snap)
        assert len(findings) == 1
        assert findings[0].id == "health-image-pull-error"

    def test_err_image_pull_detected(self):
        snap = ClusterSnapshot()
        snap.pods = [_make_pod(
            container_statuses=[{
                "name": "app",
                "ready": False,
                "restart_count": 0,
                "state": {"waiting": {"reason": "ErrImagePull"}},
                "image": "missing:image",
            }]
        )]
        findings = check_image_pull_errors(snap)
        assert len(findings) == 1


class TestPendingPods:
    def test_pending_pod_detected(self):
        snap = ClusterSnapshot()
        snap.pods = [_make_pod(phase="Pending", conditions=[])]
        findings = check_pending_pods(snap)
        assert len(findings) == 1
        assert findings[0].severity == "medium"

    def test_running_pod_not_flagged(self):
        snap = ClusterSnapshot()
        snap.pods = [_make_pod(phase="Running")]
        findings = check_pending_pods(snap)
        assert findings == []


class TestFailedJobs:
    def test_job_with_failures_detected(self):
        snap = ClusterSnapshot()
        snap.jobs = [JobInfo(name="my-job", namespace="default", failed=2, succeeded=0)]
        findings = check_failed_jobs(snap)
        assert len(findings) == 1
        assert findings[0].id == "health-job-failed"

    def test_successful_job_not_flagged(self):
        snap = ClusterSnapshot()
        snap.jobs = [JobInfo(name="my-job", namespace="default", failed=0, succeeded=1)]
        findings = check_failed_jobs(snap)
        assert findings == []


class TestDeploymentAvailability:
    def test_unavailable_replicas_detected(self):
        snap = ClusterSnapshot()
        snap.deployments = [DeploymentInfo(
            name="my-dep", namespace="default",
            replicas=3, ready_replicas=1, available_replicas=1, unavailable_replicas=2
        )]
        findings = check_deployment_availability(snap)
        assert len(findings) == 1
        assert findings[0].severity == "high"

    def test_fully_available_no_finding(self):
        snap = ClusterSnapshot()
        snap.deployments = [DeploymentInfo(
            name="my-dep", namespace="default",
            replicas=3, ready_replicas=3, available_replicas=3, unavailable_replicas=0
        )]
        findings = check_deployment_availability(snap)
        assert findings == []


class TestNodeConditions:
    def test_not_ready_node_detected(self):
        snap = ClusterSnapshot()
        snap.nodes = [NodeInfo(
            name="node-1",
            conditions=[{"type": "Ready", "status": "False", "reason": "KubeletNotReady", "message": ""}]
        )]
        findings = check_node_conditions(snap)
        assert any(f.id == "health-node-not-ready" for f in findings)
        assert any(f.severity == "critical" for f in findings)

    def test_memory_pressure_detected(self):
        snap = ClusterSnapshot()
        snap.nodes = [NodeInfo(
            name="node-1",
            conditions=[
                {"type": "Ready", "status": "True", "reason": "", "message": ""},
                {"type": "MemoryPressure", "status": "True", "reason": "MemoryPressure", "message": ""},
            ]
        )]
        findings = check_node_conditions(snap)
        assert any(f.id == "health-node-memorypressure" for f in findings)

    def test_healthy_node_no_finding(self):
        snap = ClusterSnapshot()
        snap.nodes = [NodeInfo(
            name="node-1",
            conditions=[{"type": "Ready", "status": "True", "reason": "", "message": ""}]
        )]
        findings = check_node_conditions(snap)
        assert findings == []


class TestMissingResources:
    def test_missing_requests_detected(self):
        snap = ClusterSnapshot()
        snap.pods = [_make_pod(
            spec_containers=[{
                "name": "app",
                "image": "nginx",
                "resources": {"requests": {}, "limits": {}},
                "security_context": {},
                "probes": {"readiness_probe": True, "liveness_probe": True},
                "volume_mounts": [],
                "env_count": 0,
            }]
        )]
        findings = check_missing_resource_requests(snap)
        assert len(findings) >= 1
        assert any(f.id == "operational-missing-requests" for f in findings)

    def test_missing_limits_detected(self):
        snap = ClusterSnapshot()
        snap.pods = [_make_pod(
            spec_containers=[{
                "name": "app",
                "image": "nginx",
                "resources": {"requests": {"cpu": "100m", "memory": "128Mi"}, "limits": {}},
                "security_context": {},
                "probes": {"readiness_probe": True, "liveness_probe": True},
                "volume_mounts": [],
                "env_count": 0,
            }]
        )]
        findings = check_missing_resource_limits(snap)
        assert len(findings) >= 1
        assert any(f.id == "operational-missing-limits" for f in findings)


class TestMissingProbes:
    def test_missing_readiness_probe_detected(self):
        snap = ClusterSnapshot()
        snap.pods = [_make_pod(
            spec_containers=[{
                "name": "app",
                "image": "nginx",
                "resources": {"requests": {"cpu": "100m"}, "limits": {"cpu": "500m"}},
                "security_context": {},
                "probes": {"readiness_probe": False, "liveness_probe": True},
                "volume_mounts": [],
                "env_count": 0,
            }]
        )]
        findings = check_missing_probes(snap)
        assert any(f.id == "operational-missing-readiness-probe" for f in findings)


class TestNamespacesWithoutQuota:
    def test_ns_without_quota_detected(self):
        snap = ClusterSnapshot()
        snap.namespaces = ["default", "production"]
        snap.resource_quotas = []
        findings = check_namespaces_without_quota(snap)
        assert len(findings) == 2

    def test_kube_namespaces_excluded(self):
        snap = ClusterSnapshot()
        snap.namespaces = ["kube-system", "kube-public"]
        snap.resource_quotas = []
        findings = check_namespaces_without_quota(snap)
        assert findings == []

    def test_ns_with_quota_no_finding(self):
        snap = ClusterSnapshot()
        snap.namespaces = ["default"]
        snap.resource_quotas = [ResourceQuotaInfo(name="default-quota", namespace="default")]
        findings = check_namespaces_without_quota(snap)
        assert findings == []


class TestRunAllHealthChecks:
    def test_empty_cluster_returns_list(self):
        snap = ClusterSnapshot()
        results = run_all_health_checks(snap)
        assert isinstance(results, list)

    def test_multiple_issues_detected(self):
        snap = ClusterSnapshot()
        snap.pods = [
            _make_pod("crasher", conditions=[{"type": "Ready", "status": "False"}],
                      container_statuses=[{"name": "app", "ready": False, "restart_count": 10,
                                           "state": {"waiting": {"reason": "CrashLoopBackOff"}}, "image": "x"}]),
        ]
        snap.nodes = [NodeInfo(name="n1", conditions=[{"type": "Ready", "status": "False", "reason": "", "message": ""}])]
        results = run_all_health_checks(snap)
        assert len(results) >= 2
