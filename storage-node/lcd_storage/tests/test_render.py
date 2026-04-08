"""Tests for the pure render module (no hardware)."""

from render import render_frame, render_error, COLS


class TestRenderFrame:
    def test_off_when_zero_replicas(self):
        frame = render_frame(
            node_label="node-1",
            spec_replicas=0,
            disk_used=None,
            disk_total=None,
            deployment_name="agent1",
        )
        assert frame == ["agent1 is OFF", ""]

    def test_off_when_none_replicas(self):
        frame = render_frame(
            node_label="node-1",
            spec_replicas=None,
            disk_used=None,
            disk_total=None,
            deployment_name="agent1",
        )
        assert frame[0] == "agent1 is OFF"

    def test_disk_na_when_replicas_up_but_no_disk(self):
        frame = render_frame(
            node_label="node-2",
            spec_replicas=1,
            disk_used=None,
            disk_total=None,
            deployment_name="agent2",
        )
        assert frame == ["node-2", "disk: n/a"]

    def test_disk_usage_rendered(self):
        frame = render_frame(
            node_label="node-3",
            spec_replicas=1,
            disk_used=1024 * 1024 * 1024,  # 1.0G
            disk_total=500 * 1024 * 1024 * 1024,  # 500.0G
            deployment_name="agent3",
        )
        assert frame[0] == "node-3"
        assert "/" in frame[1]

    def test_long_deployment_name_is_trimmed(self):
        frame = render_frame(
            node_label="node-1",
            spec_replicas=0,
            disk_used=None,
            disk_total=None,
            deployment_name="a-very-long-deployment-name-that-exceeds-the-width",
        )
        assert len(frame[0]) <= COLS
        assert len(frame[1]) <= COLS

    def test_all_lines_within_width(self):
        frame = render_frame(
            node_label="node-99",
            spec_replicas=1,
            disk_used=999 * 1024**3,
            disk_total=1000 * 1024**3,
            deployment_name="agent99",
        )
        for line in frame:
            assert len(line) <= COLS


class TestRenderError:
    def test_single_label(self):
        frame = render_error("K8S ERROR")
        assert frame == ["K8S ERROR", ""]

    def test_label_and_detail(self):
        frame = render_error("ERROR", "RuntimeError")
        assert frame == ["ERROR", "RuntimeError"]

    def test_long_label_trimmed(self):
        frame = render_error("this is a very long error label", "detail")
        assert len(frame[0]) <= COLS
        assert len(frame[1]) <= COLS
