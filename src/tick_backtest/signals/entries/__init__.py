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

"""Entry engine exports and registry."""

from .base import BaseEntryEngine, EntryEngineFactory, EntryResult
from .ewma_crossover import EWMACrossoverEntryEngine
from .null import NullEntryEngine
from .threshold_reversion import ThresholdReversionEntryEngine

ENTRY_ENGINE_REGISTRY: dict[str, EntryEngineFactory] = {
    "threshold_reversion": ThresholdReversionEntryEngine,
    "ewma_crossover": EWMACrossoverEntryEngine,
    "stub": NullEntryEngine,
}

__all__ = [
    "BaseEntryEngine",
    "EntryResult",
    "EWMACrossoverEntryEngine",
    "NullEntryEngine",
    "ThresholdReversionEntryEngine",
    "ENTRY_ENGINE_REGISTRY",
]
