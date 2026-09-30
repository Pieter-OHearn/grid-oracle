# ruff: noqa: E402
"""Mathematical and lifecycle evidence for WP08's offline ranker."""

import json
import math
import subprocess
import sys
from dataclasses import asdict

import pandas as pd
import pytest

torch = pytest.importorskip("torch", reason="install isolated docs/research/wp08 requirements")

from pipeline.custom_model.backend import device, hardware, memory
from pipeline.custom_model.data import Encoder, scores
from pipeline.custom_model.model import RaceRanker, ranking_loss, winner_probabilities
from pipeline.custom_model.training import load, save, seed_all, train


def fixture(n=3):
    frame = pd.DataFrame(
        {
            "race_key": ["tiny"] * n,
            "driver_identity_key": [f"d{i}" for i in range(n)],
            "constructor_identity_key": [f"t{i // 2}" for i in range(n)],
            "horizon": ["pre_weekend"] * n,
            "missing__qualifying": [True] * n,
            "driver_finish_mean_last_3": list(range(1, n + 1)),
        }
    )
    races = {"tiny": {"circuit": "track"}}
    targets = {"tiny": [{"driver": f"d{i}", "rank": i + 1} for i in range(n)]}
    return frame, races, targets


def config(epochs=30):
    return {
        "seed": 8082026,
        "hidden": 0,
        "interactions": False,
        "features": "all",
        "epochs": epochs,
        "learning_rate": 0.05,
        "regularization": 0.0,
    }


def test_hand_loss_and_censored_winner():
    s = torch.tensor([[math.log(3), math.log(2), 0.0]], dtype=torch.float64)
    mask = torch.ones_like(s, dtype=torch.bool)
    assert ranking_loss(s, torch.tensor([[1, 2, 3]]), mask).item() == pytest.approx(
        -math.log(3 / 6) - math.log(2 / 3), abs=1e-12
    )
    assert ranking_loss(s, torch.tensor([[1, 2, 0]]), mask).item() == pytest.approx(math.log(2), abs=1e-12)
    assert ranking_loss(torch.zeros((1, 2)), torch.tensor([[1, 2]]), mask[:, :2]).item() == pytest.approx(math.log(2))


def test_gradient_correctness_and_extreme_logits():
    s = torch.tensor([[0.2, -0.7, 0.1, 3.0]], dtype=torch.float64, requires_grad=True)
    r, m = torch.tensor([[1, 2, 0, 0]]), torch.tensor([[True, True, True, False]])
    assert torch.autograd.gradcheck(lambda x: ranking_loss(x, r, m), (s,), eps=1e-6, atol=1e-5)
    ranking_loss(s, r, m).backward()
    assert s.grad[0, 3] == 0
    assert s.grad[0, 2] > 0  # Censored entrant still in winner denominator.
    extreme = torch.tensor([[10000.0, -10000.0, 0.0]], requires_grad=True)
    ranking_loss(extreme, torch.tensor([[1, 2, 0]]), torch.ones((1, 3), dtype=torch.bool)).backward()
    assert torch.isfinite(extreme.grad).all()


def test_tiny_data_overfit():
    f, r, t = fixture()
    model, encoder, curve = train(f, r, t, config(350))
    batch, _, _ = encoder.batch(f, r, t)
    assert curve[-1] < 0.05 and curve[-1] < curve[0] / 20
    assert scores(model, batch).argsort(descending=True).tolist() == [[0, 1, 2]]


@pytest.mark.parametrize("hidden,interactions", [(0, False), (8, True)])
def test_entry_order_equivariance(hidden, interactions):
    seed_all(80)
    f, r, t = fixture(22)
    enc = Encoder.fit(f, r)
    model = RaceRanker(10, len(enc.drivers), len(enc.teams), len(enc.circuits), hidden, interactions)
    b, _, ids = enc.batch(f, r, t)
    shuffled = f.sample(frac=1, random_state=10)
    other, _, other_ids = enc.batch(shuffled, r, t)
    p = winner_probabilities(scores(model, b), b["mask"])[0]
    q = winner_probabilities(scores(model, other), other["mask"])[0]
    a = dict(zip(ids[0], p.tolist(), strict=True))
    for d, value in zip(other_ids[0], q.tolist(), strict=True):
        assert value == pytest.approx(a[d], abs=1e-7)
    assert ranking_loss(scores(model, b), b["ranks"], b["mask"]).item() == pytest.approx(
        ranking_loss(scores(model, other), other["ranks"], other["mask"]).item(), abs=1e-5
    )


def test_twenty_twenty_two_masks():
    s = torch.zeros((2, 22), requires_grad=True)
    m = torch.ones_like(s, dtype=torch.bool)
    m[0, 20:] = False
    ranks = torch.arange(1, 23).repeat(2, 1)
    ranks[0, 20:] = 0
    p = winner_probabilities(s, m)
    assert p[0, :20].tolist() == pytest.approx([1 / 20] * 20)
    assert p[1].tolist() == pytest.approx([1 / 22] * 22)
    assert p[0, 20:].sum() == 0
    loss = ranking_loss(s, ranks, m)
    assert loss.item() == pytest.approx((math.lgamma(21) + math.lgamma(23)) / 2, abs=1e-5)
    loss.backward()
    assert s.grad[0, 20:].abs().sum() == 0
    assert torch.isfinite(s.grad).all()


def test_cold_starts_and_horizon():
    f, r, t = fixture()
    model, encoder, _ = train(f, r, t, config())
    unknown = f.copy()
    unknown["driver_identity_key"] = ["rookie", "reserve", "unknown"]
    unknown["constructor_identity_key"] = "new_team"
    b, _, _ = encoder.batch(unknown, {"tiny": {"circuit": "new_track"}})
    assert (b["driver"] == 0).all() and (b["team"] == 0).all() and (b["circuit"] == 0).all()
    assert model.driver.weight[0].abs().sum() == 0
    assert model.team.weight[0].abs().sum() == 0
    assert torch.isfinite(scores(model, b)).all()
    base = scores(model, b)
    with torch.no_grad():
        model.linear[1, 0] = 2
    b["horizon"][:] = 1
    assert not torch.equal(base, scores(model, b))
    # Unknown interactions always map to the protected zero row.
    interacting = RaceRanker(10, 3, 2, 1, interactions=True)
    with torch.no_grad():
        interacting.interaction.weight[1:] = 100
    assert scores(interacting, b).abs().sum() == 0


def test_clean_process_save_load(tmp_path):
    f, r, t = fixture()
    model, encoder, _ = train(f, r, t, config(), checkpoint_dir=tmp_path)
    batch, _, _ = encoder.batch(f, r, t)
    original = scores(model, batch).detach().tolist()
    data = tmp_path / "batch.pt"
    save(data, batch)
    script = (
        "from pipeline.custom_model.training import load; "
        "from pipeline.custom_model.data import scores; import torch,json,sys; "
        "m,e,s=load(sys.argv[1]); b=torch.load(sys.argv[2],weights_only=True); "
        "print(json.dumps(scores(m,b).detach().tolist()))"
    )
    result = subprocess.check_output(
        [sys.executable, "-c", script, str(tmp_path / "epoch-0030.pt"), str(data)], text=True
    )
    assert json.loads(result) == original
    restored, _, _ = load(tmp_path / "epoch-0030.pt")
    assert asdict(encoder) == asdict(load(tmp_path / "epoch-0030.pt")[1])
    assert torch.equal(scores(restored, batch), scores(model, batch))


def test_resume_after_process_interruption(tmp_path):
    f, r, t = fixture()
    uninterrupted, _, curve = train(f, r, t, config())
    script = (
        "from pipeline.tests.test_custom_model import fixture,config; "
        "from pipeline.custom_model.training import train; import os,sys; "
        "f,r,t=fixture(); train(f,r,t,config(),checkpoint_dir=sys.argv[1],stop_after=11); os._exit(75)"
    )
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path)], check=False)
    assert result.returncode == 75
    resumed, _, resumed_curve = train(f, r, t, config(), resume=tmp_path / "epoch-0011.pt")
    assert resumed_curve == curve
    for k, v in uninterrupted.state_dict().items():
        assert torch.equal(v, resumed.state_dict()[k])
    bad = f.copy()
    bad.loc[0, "driver_finish_mean_last_3"] = 8
    with pytest.raises(ValueError, match="mismatch"):
        train(bad, r, t, config(), resume=tmp_path / "epoch-0011.pt")
    with pytest.raises(FileExistsError):
        train(f, r, t, config(), checkpoint_dir=tmp_path, stop_after=11)


@pytest.mark.parametrize("backend", ["cpu", "mps", "cuda"])
def test_backend_parity(backend):
    if not hardware()["backends"][backend]["usable"]:
        pytest.skip(f"{backend} unavailable; recorded hardware evidence required")
    seed_all(8)
    f, r, t = fixture(22)
    encoder = Encoder.fit(f, r)
    cpu = RaceRanker(10, 22, 11, 1, hidden=8, interactions=True)
    for p in cpu.parameters():
        with torch.no_grad():
            p.uniform_(-0.1, 0.1)
    cpu.driver.weight.data[0] = 0
    cpu.team.weight.data[0] = 0
    cpu.interaction.weight.data[0] = 0
    other = RaceRanker(10, 22, 11, 1, hidden=8, interactions=True).to(device(backend))
    other.load_state_dict(cpu.state_dict())
    a, _, _ = encoder.batch(f, r, t)
    b, _, _ = encoder.batch(f, r, t, backend)
    sa, sb = scores(cpu, a), scores(other, b)
    assert torch.allclose(sa, sb.cpu(), atol=2e-5, rtol=2e-5)
    la = ranking_loss(sa, a["ranks"], a["mask"])
    lb = ranking_loss(sb, b["ranks"], b["mask"])
    assert la.item() == pytest.approx(lb.item(), abs=2e-4, rel=2e-5)
    la.backward()
    lb.backward()
    for pa, pb in zip(cpu.parameters(), other.parameters(), strict=True):
        assert torch.allclose(pa.grad, pb.grad.cpu(), atol=2e-4, rtol=2e-4)
    torch.optim.SGD(cpu.parameters(), lr=0.01).step()
    torch.optim.SGD(other.parameters(), lr=0.01).step()
    assert torch.allclose(scores(cpu, a), scores(other, b).cpu(), atol=2e-4, rtol=2e-4)
    assert memory(device(backend))["peak_rss_mib"] > 0


@pytest.mark.parametrize(
    "ranks,mask", [([[1, 1]], [[True, True]]), ([[0, 2]], [[True, True]]), ([[1, 2]], [[False, False]])]
)
def test_invalid_targets(ranks, mask):
    with pytest.raises(ValueError):
        ranking_loss(torch.zeros((1, 2)), torch.tensor(ranks), torch.tensor(mask))


def test_unavailable_device():
    with pytest.raises(ValueError, match="unavailable"):
        device("imaginary")


def test_failure_registered_before_backend_selection(tmp_path):
    from pipeline.custom_model.experiment import run

    with pytest.raises(ValueError, match="unavailable"):
        run(tmp_path, backend_name="imaginary")
    events = next(tmp_path.glob("wp08-*"))
    assert json.loads((events / "started.json").read_text())["status"] == "started"
    assert "unavailable backend" in json.loads((events / "failed.json").read_text())["error"]
    assert not (events / "finished.json").exists()


def test_frozen_fit_boundaries_and_values(tmp_path):
    from pipeline.benchmark.artifacts import BENCHMARK, read_json
    from pipeline.benchmark.data import load_dataset
    from pipeline.custom_model.experiment import CONFIG, fit_candidate

    frames, targets, dataset = load_dataset(tmp_path / "data")
    splits = read_json(BENCHMARK / "splits.json")
    settings = read_json(CONFIG)
    fold = splits["folds"][0]
    candidate = settings["reference_candidates"][0]
    # A forged fold cannot include locked evaluation/calibration rows in fitting.
    forged = {**fold, "train": fold["calibration"]}
    with pytest.raises(ValueError, match="outside"):
        fit_candidate(
            frames["pre_weekend"],
            targets,
            {r["race"]: r for r in dataset["races"]},
            dataset,
            splits,
            settings,
            forged,
            "pre_weekend",
            candidate,
            "cpu",
            tmp_path / "checkpoints",
        )
    corrupt = frames["pre_weekend"].copy()
    corrupt.loc[corrupt.race_key.isin(fold["train"]), "driver_finish_mean_last_3"] = 999
    with pytest.raises(ValueError, match="feature values differ"):
        fit_candidate(
            corrupt,
            targets,
            {r["race"]: r for r in dataset["races"]},
            dataset,
            splits,
            settings,
            fold,
            "pre_weekend",
            candidate,
            "cpu",
            tmp_path / "checkpoints",
        )
