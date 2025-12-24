import flyte
import flyte.report
import flytekit

_MAIN_TAB_NAME = "main"
_DEFAULT_TAB_NAME = "default"


class _DeckV2:
    """
    auto_add_to_deck should always set to True to be visualize
    """

    def __init__(self, name: str, html: str = "", auto_add_to_deck: bool = True):
        if name == _DEFAULT_TAB_NAME:
            self._name = _MAIN_TAB_NAME
        else:
            self._name = name
        flyte.report.get_tab(self._name).log(html)

    def append(self, html: str):
        flyte.report.get_tab(self._name).log(html)

    @staticmethod
    def publish():
        flyte.report.flush()


flytekit.Deck = _DeckV2
