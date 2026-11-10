"""Set-up shared by the Group 6 privacy tests.

The lab keeps a register of its interview participants (it needs one anyway for consent forms
and withdrawal requests). The identifier filter added for B1, B2/B4 and B3 reads that register
from DATA_DIR/privacy/participants.txt to know which names to replace. This fixture writes the
register for the synthetic participant used in the tests, as the lab's administrator would.
E-mail addresses and phone numbers need no register: they are found by pattern.

On the unmodified code the file is simply ignored, so the tests still fail there.
"""

import pytest

from .pia_support import INTERVIEWEE_NAME


@pytest.fixture(scope="session", autouse=True)
def participant_register(instance):
    register = instance.data_dir / "privacy" / "participants.txt"
    register.parent.mkdir(parents=True, exist_ok=True)
    register.write_text(f"# Interview participants (synthetic test data)\n{INTERVIEWEE_NAME}\n", encoding="utf-8")
    yield register
