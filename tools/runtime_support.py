"""Development-only affinity and peak memory measurements."""

import os


def one_cpu(index=0):
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        process = kernel.GetCurrentProcess()
        process_mask, system_mask = ctypes.c_size_t(), ctypes.c_size_t()
        kernel.GetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p]
        kernel.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
        if not kernel.GetProcessAffinityMask(process, ctypes.byref(process_mask), ctypes.byref(system_mask)):
            raise ctypes.WinError(ctypes.get_last_error())
        available = [1 << bit for bit in range(process_mask.value.bit_length())
                     if process_mask.value & (1 << bit)]
        if not 0 <= index < len(available):
            raise ValueError("CPU index is outside this process's permitted CPUs")
        first = available[index]
        if not kernel.SetProcessAffinityMask(process, first):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"logical_cpus": 1, "affinity_mask": first}
    available = os.sched_getaffinity(0)
    chosen = sorted(available)[index]
    os.sched_setaffinity(0, {chosen})
    return {"logical_cpus": 1, "cpu": chosen}


def peak_memory_bytes(process=None):
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in
                ("peak_working_set", "working_set", "peak_paged", "paged", "peak_nonpaged",
                 "nonpaged", "pagefile", "peak_pagefile")]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        handle = process._handle if process is not None else kernel.GetCurrentProcess()
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        info = Counters()
        info.cb = ctypes.sizeof(info)
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(info), info.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return info.peak_working_set
    import resource
    kind = resource.RUSAGE_CHILDREN if process is not None else resource.RUSAGE_SELF
    return resource.getrusage(kind).ru_maxrss * 1024
