from app.classes.remote_stats import stats


def test_host_cpu_is_the_machine_percent(monkeypatch) -> None:
    """
    psutil.cpu_percent() is already a percent of the whole machine, so it
    must not be divided by the number of cores (40% on 8 cores showed 5).
    """
    monkeypatch.setattr(stats.psutil, "cpu_percent", lambda interval=None: 40.04)
    monkeypatch.setattr(stats.psutil, "cpu_count", lambda: 8)
    assert stats.Stats.try_get_cpu_usage() == 40.0


def test_host_cpu_failure_returns_minus_one(monkeypatch) -> None:
    def broken(interval=None):
        raise OSError("no /proc")

    monkeypatch.setattr(stats.psutil, "cpu_percent", broken)
    assert stats.Stats.try_get_cpu_usage() == -1
