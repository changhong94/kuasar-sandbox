"""Targeted native-snapshot cache conditioning. Never writes drop_caches."""
import ctypes
import os
from pathlib import Path
import time

libc = ctypes.CDLL(None, use_errno=True)
libc.mmap.restype = ctypes.c_void_p
libc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int,
                      ctypes.c_int, ctypes.c_int, ctypes.c_long]
libc.mincore.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p]
libc.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
PAGE = os.sysconf('SC_PAGE_SIZE')


def residency(path):
    size = path.stat().st_size
    pages = (size+PAGE-1)//PAGE
    if not pages:
        return {'path': str(path), 'bytes': 0, 'pages': 0, 'resident_pages': 0}
    fd = os.open(path, os.O_RDONLY)
    try:
        address = libc.mmap(None, size, 0, 1, fd, 0)  # PROT_NONE, MAP_SHARED
        if address == ctypes.c_void_p(-1).value:
            raise OSError(ctypes.get_errno(), 'mmap')
        try:
            vector = (ctypes.c_ubyte*pages)()
            if libc.mincore(address, size, vector):
                raise OSError(ctypes.get_errno(), 'mincore')
            return {'path': str(path), 'bytes': size, 'pages': pages,
                    'resident_pages': bytes(vector).translate(bytes(i & 1 for i in range(256))).count(1)}
        finally:
            libc.munmap(address, size)
    finally:
        os.close(fd)


def condition(paths, mode):
    assert mode in ('local_warm', 'local_cold')
    started = time.monotonic_ns()
    before = [residency(p) for p in paths]
    for path in paths:
        fd = os.open(path, os.O_RDONLY)
        try:
            if mode == 'local_cold':
                # The artifacts are immutable, but finish previous publication
                # writeback before asking the kernel to discard their cache.
                os.fsync(fd)
                os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
            else:
                while os.read(fd, 4*1024*1024):
                    pass
        finally:
            os.close(fd)
    after = [residency(p) for p in paths]
    pages = sum(x['pages'] for x in after)
    resident = sum(x['resident_pages'] for x in after)
    valid = resident == (0 if mode == 'local_cold' else pages)
    proof = {'mode': mode, 'preparation_ms': (time.monotonic_ns()-started)/1e6,
             'before': before, 'after': after, 'pages': pages,
             'resident_pages': resident, 'verified': valid}
    if not valid:
        raise RuntimeError(('Target cache state not established', proof))
    return proof


def verified_warm(paths):
    started=time.monotonic_ns()
    before=[residency(p) for p in paths]
    for p,row in zip(paths,before):
        if row['resident_pages'] != row['pages']:
            with open(p,'rb',buffering=0) as f:
                while f.read(4*1024*1024):pass
    after=[residency(p) for p in paths]
    pages=sum(r['pages'] for r in after);resident=sum(r['resident_pages'] for r in after)
    assert pages==resident
    return dict(mode='local_warm',method='verify full residency; read files only if not fully resident',before=before,after=after,pages=pages,resident_pages=resident,verified=True,preparation_ms=(time.monotonic_ns()-started)/1e6)
