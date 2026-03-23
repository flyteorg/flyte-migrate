"""Replace ``flytekit.Deck`` with a v2-compatible implementation backed by ``flyte.report``.

In FlyteKit v1, ``Deck`` is used to render HTML visualisations in the Flyte
console.  In v2, the equivalent functionality is provided by the ``flyte.report``
module which organises output into named tabs.

This module maps the v1 ``Deck`` interface onto ``flyte.report.get_tab()`` so
that existing ``Deck(name, html)`` and ``deck.append(html)`` calls continue
to work.  The v1 "default" tab name is mapped to the v2 "main" tab.
"""

import flyte
import flyte.report
import flytekit

_MAIN_TAB_NAME = "main"
_DEFAULT_TAB_NAME = "default"


class _DeckV2:
    """V2-compatible replacement for ``flytekit.Deck``.

    Routes HTML content to the v2 reporting system via named tabs.
    The *auto_add_to_deck* parameter is accepted for v1 API compatibility
    but has no effect -- content is always added to the report.
    """

    def __init__(self, name: str, html: str = "", auto_add_to_deck: bool = True) -> None:
        # V2 uses "main" as the primary tab; v1 used "default".
        self._name = _MAIN_TAB_NAME if name == _DEFAULT_TAB_NAME else name
        flyte.report.get_tab(self._name).log(html)

    def append(self, html: str) -> None:
        """Append additional HTML content to this deck's tab."""
        flyte.report.get_tab(self._name).log(html)

    @staticmethod
    def publish() -> None:
        """Flush all accumulated report content to the Flyte console."""
        flyte.report.flush()


flytekit.Deck = _DeckV2
