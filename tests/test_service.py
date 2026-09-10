import time

from bellhop.server.server import Service

def blocking_function():
    time.sleep(5)

def test_service():
    service = Service("MyService", ["uv", "run", "start", "MyService"])
    service.start()
    blocking_function()
    service.stop()
