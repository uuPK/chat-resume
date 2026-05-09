"""Warning filters for noisy third-party startup output."""

from __future__ import annotations

import warnings


def suppress_noisy_dependency_warnings() -> None:
    warnings.filterwarnings(
        "ignore",
        message=(
            r"The default value of `allowed_objects` will change in a future version\."
        ),
        category=Warning,
    )
