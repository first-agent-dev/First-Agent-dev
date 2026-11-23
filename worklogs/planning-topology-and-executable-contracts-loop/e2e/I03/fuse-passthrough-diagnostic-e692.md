# E692 — local FUSE passthrough diagnostic (2026-11-23)

**Classification:** disposable local kernel experiment, not a test verdict, Docker evidence,
production code, a security boundary, or W4. The library example mirrors the entire host
root; run only on a disposable machine with an isolated mount and backing directory. Do not
expose this mount to an untrusted process. It intentionally has no path policy.

Host: Linux 6.1.158+ x86_64; uid 1001, gid 1001; `/sys/kernel/security/lsm` reports
`capability,landlock,selinux`, not AppArmor. No `apparmor_parser`, `aa-exec`, Docker or
Podman executable was found. `/dev/fuse` opened and an unprivileged FUSE mount succeeded.
These are observations about this Arena host only, not the deployment host.

Source: libfuse 3.14.0 upstream example `example/passthrough.c`, from
<https://codeload.github.com/libfuse/libfuse/tar.gz/refs/tags/fuse-3.14.0>.
Tarball SHA-256 `b14f7d97abc11a5a70a37955021a7a1d8eb1d3dd5b6abec66af093eae3168c62`;
example SHA-256 `ed3e85af1b37d0a356f42718de2e95cc4191a3739f3943c89859a4ca4f40f8af`.
Matched installed `libfuse3.so.3.14.0`; no development headers installed, so upstream
headers and an empty generated `libfuse_config.h` were used for this diagnostic build.
This is not a validated release build or dependency prescription. The example sets entry,
attribute and negative timeouts to zero; its file handlers retain backing descriptors.

## Procedure and observed outcomes

Both scripts below are runnable from repository root after the setup. `RootedViewIO` is the
actual project implementation, targeting the backing workspace outside the FUSE view.
All files are disposable, with a mode-0700 staging directory. The FUSE example translates
absolute paths under the mount to corresponding host paths: it does not scope a workspace.

```sh
mkdir -p /tmp/fa-e692
curl -fsSL https://codeload.github.com/libfuse/libfuse/tar.gz/refs/tags/fuse-3.14.0 -o /tmp/fa-e692/libfuse.tar.gz
tar -xzf /tmp/fa-e692/libfuse.tar.gz -C /tmp/fa-e692
touch /tmp/fa-e692/libfuse-fuse-3.14.0/include/libfuse_config.h
cc -Wall -I/tmp/fa-e692/libfuse-fuse-3.14.0/include /tmp/fa-e692/libfuse-fuse-3.14.0/example/passthrough.c -o /tmp/fa-e692/passthrough -Wl,-l:libfuse3.so.3
mkdir -p /tmp/fa-e692/mount /tmp/fa-e692/backing /tmp/fa-e692/staging
chmod 700 /tmp/fa-e692/staging
# Save the scripts below as /tmp/fa-e692/probe.py and /tmp/fa-e692/openfd.py.
/tmp/fa-e692/passthrough /tmp/fa-e692/mount
PYTHONPATH=src .venv/bin/python /tmp/fa-e692/probe.py
PYTHONPATH=src .venv/bin/python /tmp/fa-e692/openfd.py
fusermount3 -u /tmp/fa-e692/mount
```

`probe.py` (the original run mounted/unmounted separately for each script):

```python
import os, pathlib, tempfile, json
from fa.execution.view_io import RootedViewIO
root=pathlib.Path('/tmp/fa-e692/backing/workspace'); project=root/'worklogs/demo'; project.mkdir(parents=True,exist_ok=True)
(project/'notes').mkdir(exist_ok=True); (project/'ledger.md').write_text('initial\n'); (project/'other.md').write_text('other\n')
staging=pathlib.Path('/tmp/fa-e692/staging'); staging.mkdir(exist_ok=True)
mounted=pathlib.Path('/tmp/fa-e692/mount')/project.relative_to('/')
result={}
with (mounted/'ledger.md').open('a') as f: f.write('fuse append\n')
rfd=os.open(root,os.O_RDONLY|os.O_DIRECTORY); sfd=os.open(staging,os.O_RDONLY|os.O_DIRECTORY)
try:
 with RootedViewIO(rfd,sfd,uid=os.getuid(),gid=os.getgid(),writable=True,protected_paths=(),excluded_paths=()) as io:
  before=io.read_file('worklogs/demo/ledger.md',offset_bytes=0,max_bytes=4096)
  result['authority_before']=before['content']
  io.write_file('worklogs/demo/ledger.md','file tool replacement\n',expected_sha256=before['sha256'])
finally: os.close(rfd); os.close(sfd)
result['fuse_after_authority']= (mounted/'ledger.md').read_text()
with (mounted/'ledger.md').open('a') as f: f.write('second append\n')
(mounted/'notes/tmp').write_text('atomic replacement\n'); os.replace(mounted/'notes/tmp',mounted/'ledger.md')
with (mounted/'ledger.md').open('a') as f: f.write('third append\n')
result['backing_ledger']=(project/'ledger.md').read_text()
(mounted/'other.md').write_text('fuse uncontrolled\n'); result['backing_other']=(project/'other.md').read_text()
(project/'other.md').write_text('direct backing bypass\n'); result['fuse_after_direct']=(mounted/'other.md').read_text()
print(json.dumps(result,indent=2))
```

Observed: authority before replacement was `initial\nfuse append\n`; fresh FUSE read
after RootedViewIO atomic replacement was `file tool replacement\n`; after subsequent
append, notes-temp rename over ledger and another append, backing ledger was
`atomic replacement\nthird append\n`. Ordinary writes to `other.md` through this
passthrough succeeded. A direct backing write also succeeded and a fresh FUSE read saw it.
The latter demonstrates bypass when backing is accessible, not a bypass of a policy:
this example implements none.

`openfd.py`:

```python
import os, pathlib, json
from fa.execution.view_io import RootedViewIO
root=pathlib.Path('/tmp/fa-e692/backing/workspace'); p=root/'worklogs/demo/ledger.md'; p.write_text('old\n'); mount=pathlib.Path('/tmp/fa-e692/mount')/p.relative_to('/')
rfd=os.open(root,os.O_RDONLY|os.O_DIRECTORY); sfd=os.open('/tmp/fa-e692/staging',os.O_RDONLY|os.O_DIRECTORY)
fd=os.open(mount,os.O_RDWR|os.O_APPEND)
try:
 with RootedViewIO(rfd,sfd,uid=os.getuid(),gid=os.getgid(),writable=True,protected_paths=(),excluded_paths=()) as io:
  before=io.read_file('worklogs/demo/ledger.md',offset_bytes=0,max_bytes=4096)
  io.write_file('worklogs/demo/ledger.md','new\n',expected_sha256=before['sha256'])
 os.write(fd,b'stale append\n'); os.lseek(fd,0,os.SEEK_SET)
 print(json.dumps({'existing_fd':os.read(fd,128).decode(),'fresh_fuse':mount.read_text(),'backing':p.read_text()}))
finally: os.close(fd); os.close(rfd); os.close(sfd)
```

Observed successful `os.write` on the already-open FUSE descriptor following external
atomic replacement. Reading that descriptor returned `old\n`, while a fresh FUSE open and
the backing pathname both returned `new\n`. This establishes that the reported write
was not visible through the fresh authoritative path in this sequence. It does not establish
whether the old backing inode contains the bytes or explain the stale read/cache mechanics.
A non-FUSE control ran the identical script with `mount=p` (direct backing path) instead
of the FUSE path. The old descriptor returned `old\nstale append\n`; fresh and backing
path reads both returned `new\n`. Thus a successful stale-descriptor write being absent
from the new pathname is also reproducible without FUSE. The FUSE old-FD read differs in
this run; cache and inode contents were not independently characterized. To reproduce the
control, replace the `mount=...` assignment in the script with `mount=p` and run it once.
Long-lived descriptor semantics, detection, and agent-facing failure/recovery need explicit
design; merely checking fresh pathname continuity is insufficient.

## What this did not establish

No name-based denial policy, alien uid/container, protected mounts, alias/link/rename
matrix, crash/replay, cache invalidation proof, secure backing exclusion, worker lifecycle,
profile binding, concurrent views, authority publication or STOP_VIEW→SEAL→PUBLISH was tested.
The upstream example accesses host root and is unsuitable as a product boundary. No AppArmor
profile was compiled or loaded. E657, the immutable-payload fallback, C1 producer/EDGE,
E674 and W4 remain open. A future disposable-host FUSE policy experiment must separately
prove direct-backing exclusion and operation mediation, not infer them from these observations.
