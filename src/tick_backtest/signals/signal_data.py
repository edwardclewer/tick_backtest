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

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class SignalData:
    should_open: bool = False
    direction: int = 0      # +1 long, -1 short, 0 = none
    tp: Optional[float] = None
    sl: Optional[float] = None
    reason: str = "mean_reversion_zscore"
    timeout_seconds: Optional[float] = None
    should_close: bool = False
    close_reason: Optional[str] = None
    entry_metadata: Optional[Dict[str, Any]] = None
