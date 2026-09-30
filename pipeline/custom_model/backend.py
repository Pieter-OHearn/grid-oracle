"""Probe usable accelerators, never silently fall back from a requested backend."""

import platform
import resource
import subprocess

import torch

_MPS_PEAK = {"allocated": 0, "driver": 0}


def observe_memory(backend):
    if str(backend).startswith("mps"):
        _MPS_PEAK["allocated"] = max(_MPS_PEAK["allocated"], torch.mps.current_allocated_memory())
        _MPS_PEAK["driver"] = max(_MPS_PEAK["driver"], torch.mps.driver_allocated_memory())


def hardware():
    available = {"cpu": True, "cuda": torch.cuda.is_available(), "mps": torch.backends.mps.is_available()}
    probes = {}
    for name, enabled in available.items():
        if not enabled:
            probes[name] = {"usable": False, "reason": "runtime reports unavailable"}
            continue
        try:
            x = torch.ones(3, device=name, requires_grad=True)
            x.square().sum().backward()
            probes[name] = {"usable": True, "gradient": x.grad.cpu().tolist()}
        except RuntimeError as error:
            probes[name] = {"usable": False, "reason": str(error)}

    def command(args):
        try:
            return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "cpu": command(["sysctl", "-n", "machdep.cpu.brand_string"]),
        "memory_bytes": command(["sysctl", "-n", "hw.memsize"]),
        "cuda_build": torch.version.cuda,
        "backends": probes,
        "cuda_devices": [
            {"name": torch.cuda.get_device_name(i), "vram_bytes": torch.cuda.get_device_properties(i).total_memory}
            for i in range(torch.cuda.device_count())
        ],
        "nvidia_inventory": command(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"]
        ),
        "pc_inventory": "not accessible; no remote hardware claim",
    }


def device(name):
    evidence = hardware()
    if name == "auto":
        name = next(n for n in ("cuda", "mps", "cpu") if evidence["backends"][n]["usable"])
    if name not in evidence["backends"] or not evidence["backends"][name]["usable"]:
        raise ValueError(f"unavailable backend: {name}")
    return torch.device(name)


def synchronize(backend):
    if backend.type == "cuda":
        torch.cuda.synchronize()
    elif backend.type == "mps":
        torch.mps.synchronize()


def memory(backend):
    observe_memory(backend)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "sampled_peak_mps_allocated_mib": _MPS_PEAK["allocated"] / 1024**2 if backend.type == "mps" else None,
        "sampled_peak_mps_driver_mib": _MPS_PEAK["driver"] / 1024**2 if backend.type == "mps" else None,
        "peak_rss_mib": rss / (1024**2 if platform.system() == "Darwin" else 1024),
        "peak_cuda_allocated_mib": torch.cuda.max_memory_allocated() / 1024**2 if backend.type == "cuda" else None,
        "mps_current_allocated_mib": torch.mps.current_allocated_memory() / 1024**2 if backend.type == "mps" else None,
        "mps_driver_allocated_mib": torch.mps.driver_allocated_memory() / 1024**2 if backend.type == "mps" else None,
    }
