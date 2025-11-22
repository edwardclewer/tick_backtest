# Copyright 2025 Edward Clewer
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import numpy as np
from collections import deque
from dataclasses import dataclass


@dataclass
class _Event:
    start: float
    end: float
    bin_idx: int


class PyTimeWeightedHistogram:
    """Reference Python implementation retained for fallback and validation."""

    def __init__(self, edges: np.ndarray, horizon_seconds: float):
        assert edges.ndim == 1 and edges.size >= 2
        assert np.all(np.diff(edges) > 0)
        assert horizon_seconds > 0.0

        self.edges = edges.astype(float)
        self.horizon = float(horizon_seconds)
        self.n_bins = self.edges.size - 1

        self.weights = np.zeros(self.n_bins, dtype=float)
        self.total = 0.0
        self._events = deque()

    def _bin_index(self, x: float) -> int:
        if x <= self.edges[0]:
            return 0
        if x >= self.edges[-1]:
            return self.n_bins - 1
        idx = int(np.searchsorted(self.edges, x, side="right") - 1)
        return max(0, min(self.n_bins - 1, idx))

    def add(self, start: float, end: float, value: float) -> None:
        if end <= start:
            return
        b = self._bin_index(value)
        w = end - start
        self.weights[b] += w
        self.total += w
        self._events.append(_Event(start, end, b))

    def trim(self, now: float) -> None:
        cutoff = now - self.horizon
        while self._events:
            ev = self._events[0]
            if ev.end <= cutoff:
                w = ev.end - ev.start
                self.weights[ev.bin_idx] -= w
                self.total -= w
                self._events.popleft()
                continue
            if ev.start < cutoff < ev.end:
                drop_w = cutoff - ev.start
                self.weights[ev.bin_idx] -= drop_w
                self.total -= drop_w
                self._events[0] = _Event(cutoff, ev.end, ev.bin_idx)
                break
            break
        if self.total < 0 and abs(self.total) < 1e-9:
            self.total = 0.0

    def percentile_rank(self, x: float) -> float:
        if self.total <= 0.0:
            return np.nan
        b = self._bin_index(x)
        below = self.weights[:b].sum()
        left, right = self.edges[b], self.edges[b + 1]
        if right > left:
            frac = (x - left) / (right - left)
            frac = max(0.0, min(1.0, frac))
        else:
            frac = 0.0
        in_bin = self.weights[b] * frac
        return float((below + in_bin) / self.total)
