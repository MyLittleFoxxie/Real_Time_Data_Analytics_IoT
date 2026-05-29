"""
Compatibility shims for running aiocoap tests on Windows with pytest-asyncio 0.21.x.
"""
import asyncio
import sys
from _pytest.fixtures import FixtureDef

# 1. pytest-asyncio 0.21.x accesses FixtureDef.unittest removed in pytest 8.1+
if not hasattr(FixtureDef, "unittest"):
    FixtureDef.unittest = False

# 2. aiocoap requires SelectorEventLoop on Windows — ProactorEventLoop breaks UDP
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
