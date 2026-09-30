"""Small entry-equivariant Plackett-Luce reference and shared-entry challenger."""

from __future__ import annotations

import torch
from torch import nn


def ranking_loss(scores: torch.Tensor, ranks: torch.Tensor, mask: torch.Tensor):
    """Winner over ALL intended entrants, then classified relative-order PL.

    Rank zero means an unclassified/censored entrant, not a last-place target.
    Such entrants enter the winner denominator but not later classified stages.
    Fully classified data give the ordinary full PL likelihood. Equal race weight.
    """
    if scores.ndim != 2 or scores.shape != ranks.shape or mask.shape != scores.shape:
        raise ValueError("scores, ranks and mask must be race-by-entry")
    if not torch.isfinite(scores).all() or not mask.any(dim=1).all():
        raise ValueError("nonfinite scores or empty field")
    labeled = mask & (ranks > 0)
    if not ((ranks == 1) & mask).sum(dim=1).eq(1).all():
        raise ValueError("each race needs one observed winner")
    for row in range(len(scores)):
        positive = ranks[row][labeled[row]]
        if positive.unique().numel() != positive.numel():
            raise ValueError("duplicate classified rank")
    # A finite sentinel prevents all-masked suffixes producing NaN gradients.
    floor = torch.finfo(scores.dtype).min / 100
    order = torch.argsort(torch.where(labeled, ranks, ranks.new_full((), 10**6)), dim=1)
    ordered = scores.gather(1, order)
    valid = labeled.gather(1, order)
    # O(field^2) risk sets are tiny (20/22 entrants), and logsumexp has
    # native CPU/CUDA/MPS support unlike MPS logcumsumexp in torch 2.7.
    positions = torch.arange(scores.shape[1], device=scores.device)
    remaining = positions[None, :] >= positions[:, None]
    risk = remaining[None, :, :] & valid[:, None, :]
    suffix = ordered[:, None, :].expand(-1, scores.shape[1], -1).masked_fill(~risk, floor).logsumexp(-1)
    stages = torch.where(valid, suffix - ordered, 0)
    winner = scores.masked_fill(~mask, floor).logsumexp(1) - ordered[:, 0]
    return (winner + stages[:, 1:].sum(1)).mean()


def winner_probabilities(scores, mask):
    if not mask.any(dim=-1).all() or not torch.isfinite(scores).all():
        raise ValueError("invalid winner field")
    return scores.masked_fill(~mask, -torch.inf).softmax(-1)


class RaceRanker(nn.Module):
    def __init__(self, dimensions, drivers, teams, circuits, hidden=0, interactions=False):
        super().__init__()
        self.linear = nn.Parameter(torch.zeros(2, dimensions))
        self.driver = nn.Embedding(drivers + 1, 2, padding_idx=0)
        self.team = nn.Embedding(teams + 1, 2, padding_idx=0)
        self.interaction = nn.Embedding((teams + 1) * (circuits + 1), 2, padding_idx=0) if interactions else None
        self.circuits = circuits
        self.network = (
            nn.Sequential(nn.Linear(dimensions + 1, hidden), nn.Tanh(), nn.Linear(hidden, 1, bias=False))
            if hidden
            else None
        )
        for layer in (self.driver, self.team, self.interaction):
            if layer is not None:
                nn.init.zeros_(layer.weight)

    def forward(self, x, driver, team, circuit, horizon):
        h = horizon[:, None].expand_as(driver)
        result = (x * self.linear[h]).sum(-1)
        result = result + self.driver(driver).gather(-1, h[..., None]).squeeze(-1)
        result = result + self.team(team).gather(-1, h[..., None]).squeeze(-1)
        if self.interaction is not None:
            idx = team * (self.circuits + 1) + circuit
            idx = torch.where((team > 0) & (circuit > 0), idx, 0)
            result = result + self.interaction(idx).gather(-1, h[..., None]).squeeze(-1)
        if self.network is not None:
            result = result + self.network(torch.cat((x, h[..., None].to(x.dtype)), -1)).squeeze(-1)
        return result

    def penalty(self):
        # Shared driver/team strength is not separately identifiable; shrink both.
        return sum(p.square().mean() for p in self.parameters())
