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

"""Project-wide exception hierarchy."""

from __future__ import annotations


class TickBacktestError(Exception):
    """Base exception for the tick backtest stack."""


class ConfigError(TickBacktestError):
    """Raised when user-supplied configuration is invalid."""


class DataFeedError(TickBacktestError):
    """Raised when underlying market data cannot be accessed or parsed."""

