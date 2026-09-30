"""Record backend numerical parity and bounded synthetic-training resource evidence."""

import argparse
import time
from pathlib import Path

import pandas as pd
import torch

from pipeline.benchmark.artifacts import write_once
from pipeline.custom_model.backend import device, hardware, memory, synchronize
from pipeline.custom_model.data import Encoder, scores
from pipeline.custom_model.model import RaceRanker, ranking_loss, winner_probabilities
from pipeline.custom_model.training import seed_all, train


def verify(output):
    report = {
        "hardware": hardware(),
        "parity": {},
        "scope": "synthetic correctness/resource probe; no benchmark labels",
        "tolerances": {"score_atol_rtol": 2e-5, "loss_atol": 2e-4, "loss_rtol": 2e-5, "gradient_atol_rtol": 2e-4},
    }
    report["owner_reported_pc"] = {
        "cpu": "AMD Ryzen 7 5700X",
        "gpu": "GeForce RTX 5060",
        "ram_gb": 32,
        "os": "Windows 11 Pro",
        "vram": "unverified",
        "driver": "unverified",
        "remote_access": "not established",
    }
    n = 22
    frame = pd.DataFrame(
        {
            "race_key": ["synthetic"] * n,
            "driver_identity_key": [f"d{i}" for i in range(n)],
            "constructor_identity_key": [f"t{i // 2}" for i in range(n)],
            "horizon": ["pre_weekend"] * n,
            "missing__qualifying": [True] * n,
            "driver_finish_mean_last_3": list(range(1, n + 1)),
        }
    )
    races = {"synthetic": {"circuit": "track"}}
    targets = {"synthetic": [{"driver": f"d{i}", "rank": i + 1} for i in range(n)]}
    encoder = Encoder.fit(frame, races)
    batch, _, _ = encoder.batch(frame, races, targets)
    seed_all(6062026)
    reference = RaceRanker(10, n, n // 2, 1, hidden=8, interactions=True)
    for p in reference.parameters():
        with torch.no_grad():
            p.uniform_(-0.1, 0.1)
    for layer in (reference.driver, reference.team, reference.interaction):
        layer.weight.data[0] = 0
    sa = scores(reference, batch)
    la = ranking_loss(sa, batch["ranks"], batch["mask"])
    la.backward()
    pa = winner_probabilities(sa, batch["mask"])
    for name, proof in report["hardware"]["backends"].items():
        if not proof["usable"]:
            report["parity"][name] = {"status": "not run", "reason": proof["reason"]}
            continue
        backend = device(name)
        other = RaceRanker(10, n, n // 2, 1, hidden=8, interactions=True).to(backend)
        other.load_state_dict(reference.state_dict())
        b, _, _ = encoder.batch(frame, races, targets, name)
        sb = scores(other, b)
        lb = ranking_loss(sb, b["ranks"], b["mask"])
        lb.backward()
        gradient_error = max(
            (a.grad - b.grad.cpu()).abs().max().item()
            for a, b in zip(reference.parameters(), other.parameters(), strict=True)
        )
        score_error = (sa.detach() - sb.detach().cpu()).abs().max().item()
        loss_error = abs(la.item() - lb.item())
        probability_error = (pa.detach() - winner_probabilities(sb, b["mask"]).detach().cpu()).abs().max().item()
        assert torch.allclose(sa, sb.cpu(), atol=2e-5, rtol=2e-5)
        assert loss_error <= 2e-4 + 2e-5 * abs(la.item())
        assert all(
            torch.allclose(a.grad, b.grad.cpu(), atol=2e-4, rtol=2e-4)
            for a, b in zip(reference.parameters(), other.parameters(), strict=True)
        )
        settings = {
            "seed": 6062026,
            "hidden": 0,
            "interactions": False,
            "features": "all",
            "epochs": 30,
            "learning_rate": 0.05,
            "regularization": 0.1,
        }
        synchronize(backend)
        start = time.perf_counter()
        model, _, curve = train(frame, races, targets, settings, name)
        synchronize(backend)
        elapsed = time.perf_counter() - start
        start = time.perf_counter()
        with torch.no_grad():
            for _ in range(30):
                scores(model, b)
        synchronize(backend)
        report["parity"][name] = {
            "status": "passed",
            "score_max_abs": score_error,
            "loss_abs": loss_error,
            "gradient_max_abs": gradient_error,
            "probability_max_abs": probability_error,
            "synthetic_training_seconds": elapsed,
            "synthetic_inference_seconds_per_race": (time.perf_counter() - start) / 30,
            "curve": curve,
            "memory": memory(backend),
        }
    write_once(Path(output), report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(verify(parser.parse_args().output))
