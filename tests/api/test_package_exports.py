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

import tick_backtest
from tick_backtest import api


def test_top_level_package_reexports_public_api() -> None:
    assert tick_backtest.run is api.run
    assert tick_backtest.report is api.report
    assert tick_backtest.analyze is api.analyze
    assert tick_backtest.example_config is api.example_config
    assert callable(tick_backtest.run_backtest_batch)
