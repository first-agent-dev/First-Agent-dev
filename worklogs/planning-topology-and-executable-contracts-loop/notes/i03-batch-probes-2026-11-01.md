# I03: исходники диагностических batch probes

Дата 2026-11-01; проверялись на `796d0bf`. Это не regression tests и не
production-код; оба workspace и handlers искусственные. Каждая секция —
самостоятельный файл Python. Сохранить его во временный файл и выполнить из
корня repo: `PYTHONPATH=src .venv/bin/python <путь-к-файлу>` при настроенной
среде `knowledge/arena-env-build.md`. Нужны доступные исходники FA и зависимости.
F2 использует sleep только как диагностический probe: в будущем regression test
нужны контролируемые barrier/event и надёжный teardown. Предупреждение про tmux
в этой среде не относится к вызовам probe.

## F1: повторный dispatch после ошибки bookkeeping

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from collections import Counter
from unittest.mock import patch
from concurrent.futures import wait as real_wait
from fa.inner_loop import EventLog, SessionState, ToolCall, run_session
from fa.inner_loop.registry import ToolRegistry, ToolSpec, ToolResult
from fa.inner_loop.hooks import HookRegistry
from fa.inner_loop.runtime_limits import RuntimeLimits
from threading import Lock

with TemporaryDirectory() as d:
    ws = Path(d)
    state = SessionState(workspace_root=ws, run_id='fault-probe', log=EventLog(ws/'events.jsonl', run_id='fault-probe'))
    counts = Counter()
    lock = Lock()
    def handler(params):
        with lock: counts[params['key']] += 1
        return ToolResult.ok('ok', result=params['key'])
    registry = ToolRegistry()
    registry.register(ToolSpec(name='probe_read',description='Probe.',input_schema={'type':'object','properties':{'key':{'type':'string'}},'required':['key']},permission='read',handler=handler))
    calls = [ToolCall(name='probe_read',params={'key':k},call_id=k) for k in ['a','b']]
    def fail_wait(fs, timeout=None):
        real_wait(fs)
        raise RuntimeError('injected pool bookkeeping failure after handlers finished')
    with patch('fa.inner_loop.loop.wait', fail_wait):
        result = run_session(calls,registry=registry,hooks=HookRegistry(),state=state,limits=RuntimeLimits(max_iterations=10))
    print('handler executions:',dict(counts))
    print('returned result errors:',[r.error for r in result])
    assert counts == {'a':2,'b':2}
    assert all(r.error is None for r in result)
```

## F2: timeout с работающими потоками

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic, sleep
from unittest.mock import patch
from concurrent.futures import wait as wait_real
from fa.inner_loop import EventLog, SessionState, ToolCall, run_session
from fa.inner_loop.registry import ToolRegistry, ToolSpec, ToolResult
from fa.inner_loop.hooks import HookRegistry
from fa.inner_loop.runtime_limits import RuntimeLimits
with TemporaryDirectory() as d:
    ws=Path(d); state=SessionState(workspace_root=ws,run_id='timeout-probe',log=EventLog(ws/'events.jsonl',run_id='timeout-probe'))
    r=ToolRegistry(); started=Event(); effect=[]
    def h(params):
        started.set(); sleep(.35); effect.append(params['id']); return ToolResult.ok('done')
    r.register(ToolSpec(name='probe_read',description='probe',input_schema={'type':'object','properties':{'id':{'type':'string'}},'required':['id']},permission='read',handler=h))
    def shortened_wait(futures, timeout):
        assert started.wait(2)
        return wait_real(futures,timeout=.02)
    calls=[ToolCall(name='probe_read',params={'id':i},call_id=i) for i in ['a','b']]
    with patch('fa.inner_loop.loop.wait',shortened_wait):
        start=monotonic(); result=run_session(calls,registry=r,hooks=HookRegistry(),state=state,limits=RuntimeLimits(max_iterations=10)); elapsed=monotonic()-start
    print(f'elapsed={elapsed:.3f}s for injected 0.02s wait; completed effects={sorted(effect)}')
    print('reported errors:',[r.error.code if r.error else None for r in result])
    assert elapsed>=.30 and sorted(effect)==['a','b'] and all(r.error and r.error.code=='exec_timeout' for r in result)
```

## F3: scheduler после изменения hook

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from fa.inner_loop import EventLog, SessionState, ToolCall, run_session
from fa.inner_loop.registry import ToolRegistry, ToolSpec, ToolResult
from fa.inner_loop.hooks import HookRegistry, GuardMiddleware, LifecyclePoint, Decision
from fa.inner_loop.runtime_limits import RuntimeLimits

with TemporaryDirectory() as d:
    ws=Path(d); state=SessionState(workspace_root=ws,run_id='mutation-probe',log=EventLog(ws/'events.jsonl',run_id='mutation-probe'))
    rendezvous=Barrier(2); executions=[]
    def execute(label):
        def handler(params):
            executions.append(label)
            rendezvous.wait(timeout=3)
            return ToolResult.ok('ran '+label)
        return handler
    r=ToolRegistry()
    schema={'type':'object','properties':{},'required':[]}
    r.register(ToolSpec(name='probe_read',description='probe',input_schema=schema,permission='read',handler=execute('read')))
    r.register(ToolSpec(name='fs_run_bash',description='probe',input_schema=schema,permission='workspace',handler=execute('bash-shaped workspace tool')))
    class Rewriter(GuardMiddleware):
        attaches_to=(LifecyclePoint.BEFORE_TOOL_EXEC,)
        def handle(self, point, payload):
            call=payload.tool_call
            if call.call_id=='b':
                return Decision.modify(payload.with_tool_call(ToolCall(name='fs_run_bash',params={},call_id=call.call_id)))
            return Decision.allow()
    hooks=HookRegistry(); hooks.register(Rewriter())
    calls=[ToolCall(name='probe_read',params={},call_id='a'),ToolCall(name='probe_read',params={},call_id='b')]
    result=run_session(calls,registry=r,hooks=hooks,state=state,limits=RuntimeLimits(max_iterations=10))
    print('concurrent barrier reached:',executions)
    print('results:',[(v.summary, v.error) for v in result])
    assert executions==['read','bash-shaped workspace tool'] or executions==['bash-shaped workspace tool','read']
    assert all(v.error is None for v in result)
```

## F4: duplicate ID и результаты

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from fa.inner_loop import EventLog, SessionState, ToolCall, run_session
from fa.inner_loop.registry import ToolRegistry, ToolSpec, ToolResult
from fa.inner_loop.hooks import HookRegistry
from fa.inner_loop.runtime_limits import RuntimeLimits
from fa.inner_loop.coder_loop import _assert_tool_pairing_invariant
from threading import Barrier
with TemporaryDirectory() as d:
    ws=Path(d); state=SessionState(workspace_root=ws,run_id='id-probe',log=EventLog(ws/'events.jsonl',run_id='id-probe'))
    r=ToolRegistry(); barrier=Barrier(2)
    def h(params):
        barrier.wait(timeout=3)
        return ToolResult.ok(str(params['value']),result=params['value'])
    r.register(ToolSpec(name='probe_read',description='probe',input_schema={'type':'object','properties':{'value':{'type':'string'}},'required':['value']},permission='read',handler=h))
    calls=[ToolCall(name='probe_read',params={'value':'A'},call_id='same'),ToolCall(name='probe_read',params={'value':'B'},call_id='same')]
    out=run_session(calls,registry=r,hooks=HookRegistry(),state=state,limits=RuntimeLimits(max_iterations=10))
    print('actual results:',[(v.summary,v.result) for v in out])
    assert out[0].result == out[1].result
    messages=[{'role':'assistant','tool_calls':[{'id':'same'},{'id':'same'}]},{'role':'tool','tool_call_id':'same'},{'role':'tool','tool_call_id':'same'}]
    _assert_tool_pairing_invariant(messages)
    print('set-based pairing assertion accepted duplicate call/result IDs')
```
