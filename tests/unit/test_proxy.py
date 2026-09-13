from app.proxy.manager import ProxyManager


def test_proxy_cools_down_after_three_failures() -> None:
    manager = ProxyManager(["http://proxy-a:8080"])
    for _ in range(3):
        manager.report("http://proxy-a:8080", False)
    assert manager.next() is None


def test_proxy_success_resets_failures() -> None:
    manager = ProxyManager(["http://proxy-a:8080"])
    manager.report("http://proxy-a:8080", False)
    manager.report("http://proxy-a:8080", True)
    assert manager.next() == "http://proxy-a:8080"
