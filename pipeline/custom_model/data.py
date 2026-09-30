"""Train-only vocabularies; fixed scaling/imputation, no evaluation statistics."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
import torch

from pipeline.benchmark.data import KEY
from pipeline.benchmark.temporal import validate_features

TEAM = "constructor_identity_key"
FEATURES = [
    "driver_finish_mean_last_3",
    "constructor_finish_mean_last_3",
    "driver_championship_position_race_only",
    "constructor_championship_position_race_only",
    "qualifying_position",
]


@dataclass
class Encoder:
    drivers: dict
    teams: dict
    circuits: dict
    group: str = "all"

    @classmethod
    def fit(cls, frame, races, group="all"):
        def vocab(values):
            return {value: i + 1 for i, value in enumerate(sorted(set(values)))}

        return cls(
            vocab(frame[KEY]), vocab(frame[TEAM]), vocab(races[k]["circuit"] for k in frame.race_key.unique()), group
        )

    def batch(self, frame, races, targets=None, backend="cpu"):
        keys = list(dict.fromkeys(frame.race_key))
        width = max((frame.race_key == k).sum() for k in keys)
        size = (len(keys), width)
        tensors = {k: torch.zeros(size, dtype=torch.long) for k in ("driver", "team", "circuit", "ranks")}
        tensors["x"] = torch.zeros((*size, 10))
        tensors["mask"] = torch.zeros(size, dtype=torch.bool)
        tensors["horizon"] = torch.zeros(len(keys), dtype=torch.long)
        identities = []
        for i, key in enumerate(keys):
            rows = frame[frame.race_key == key]
            horizon = rows.horizon.iloc[0]
            validate_features(rows, horizon)
            ids = rows[KEY].tolist()
            identities.append(ids)
            n = len(ids)
            tensors["mask"][i, :n] = True
            tensors["horizon"][i] = int(horizon == "post_qualifying")
            for name, column, mapping in (("driver", KEY, self.drivers), ("team", TEAM, self.teams)):
                tensors[name][i, :n] = torch.tensor([mapping.get(v, 0) for v in rows[column]])
            tensors["circuit"][i, :n] = self.circuits.get(races[key]["circuit"], 0)
            # Fixed domain scale and midpoint, also for absent pre-weekend qualifying.
            values = np.array(
                [pd.to_numeric(rows[f]).to_numpy(dtype=float) if f in rows else np.full(n, np.nan) for f in FEATURES]
            ).T
            missing = ~np.isfinite(values)
            values = np.where(missing, 11.5, values) / 22
            if self.group == "standings":
                values[:, [0, 1, 4]] = 0
                missing[:, [0, 1, 4]] = False
            tensors["x"][i, :n] = torch.tensor(np.concatenate((values, missing), 1), dtype=torch.float32)
            if targets is not None:
                classified = sorted((r for r in targets[key] if r["rank"] is not None), key=lambda r: r["rank"])
                rank = {r["driver"]: j + 1 for j, r in enumerate(classified)}
                tensors["ranks"][i, :n] = torch.tensor([rank.get(d, 0) for d in ids])
        return {k: v.to(backend) for k, v in tensors.items()}, keys, identities


def scores(model, batch):
    return model(*(batch[k] for k in ("x", "driver", "team", "circuit", "horizon")))
