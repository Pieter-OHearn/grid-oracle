"""Full-batch deterministic training with atomic, immutable epoch checkpoints."""

import io
import random
from dataclasses import asdict
from pathlib import Path

import numpy as np
import torch

from pipeline.benchmark.artifacts import digest, file_hash, write_bytes_once
from pipeline.custom_model.backend import observe_memory
from pipeline.custom_model.data import Encoder, scores
from pipeline.custom_model.model import RaceRanker, ranking_loss


def seed_all(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)


def save(path, value):
    buffer = io.BytesIO()
    torch.save(value, buffer)
    write_bytes_once(Path(path), buffer.getvalue())


def load(path, backend="cpu"):
    state = torch.load(path, map_location="cpu", weights_only=True)
    encoder = Encoder(**state["encoder"])
    model = RaceRanker(
        10,
        len(encoder.drivers),
        len(encoder.teams),
        len(encoder.circuits),
        state["config"]["hidden"],
        state["config"]["interactions"],
    ).to(backend)
    model.load_state_dict(state["model"])
    return model, encoder, state


def train(frame, races, targets, config, backend="cpu", checkpoint_dir=None, resume=None, stop_after=None):
    seed_all(config["seed"])
    encoder = Encoder.fit(frame, races, config["features"])
    batch, keys, identities = encoder.batch(frame, races, targets, backend)
    # Hash the actual ordered tensors, including labels and masks, before resume.
    fingerprint = digest(
        {"race_keys": keys, "identities": identities, "tensors": {k: v.cpu().tolist() for k, v in batch.items()}}
    )
    source = {p.name: file_hash(p) for p in sorted(Path(__file__).parent.glob("*.py"))}
    start, curve = 0, []
    if resume:
        model, encoder, state = load(resume, backend)
        if (
            state["source"] != source
            or state["backend"] != str(backend)
            or state["torch"] != torch.__version__
            or state["config"] != config
            or state["batch_sha256"] != fingerprint
            or state["encoder"] != asdict(Encoder.fit(frame, races, config["features"]))
        ):
            raise ValueError("resume config/data/vocabulary mismatch")
        start, curve = state["epoch"], state["curve"]
    else:
        model = RaceRanker(
            10,
            len(encoder.drivers),
            len(encoder.teams),
            len(encoder.circuits),
            config["hidden"],
            config["interactions"],
        ).to(backend)
    optimizer = torch.optim.Adam(model.parameters(), lr=config["learning_rate"])
    if resume:
        optimizer.load_state_dict(state["optimizer"])
        torch.set_rng_state(state["rng"])
    end = min(config["epochs"], stop_after) if stop_after is not None else config["epochs"]
    for epoch in range(start, end):
        optimizer.zero_grad()
        loss = (
            ranking_loss(scores(model, batch), batch["ranks"], batch["mask"])
            + config["regularization"] * model.penalty()
        )
        if not torch.isfinite(loss):
            raise ValueError("nonfinite training loss")
        observe_memory(backend)
        loss.backward()
        optimizer.step()
        observe_memory(backend)
        curve.append(float(loss.detach().cpu()))
        if checkpoint_dir is not None and (
            (epoch + 1) % config.get("checkpoint_interval", 25) == 0 or epoch + 1 == end
        ):
            save(
                Path(checkpoint_dir) / f"epoch-{epoch + 1:04d}.pt",
                {
                    "model": {k: v.cpu() for k, v in model.state_dict().items()},
                    "optimizer": optimizer.state_dict(),
                    "encoder": asdict(encoder),
                    "config": config,
                    "batch_sha256": fingerprint,
                    "epoch": epoch + 1,
                    "curve": curve,
                    "rng": torch.get_rng_state(),
                    "source": source,
                    "backend": str(backend),
                    "torch": str(torch.__version__),
                },
            )
    return model, encoder, curve
