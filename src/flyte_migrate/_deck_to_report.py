import flytekit
import flyte
import flyte.report


_MAIN_TAB_NAME = "main"

class _DeckV2:
    def __init__(self, name: str, html: str = "", auto_add_to_deck: bool = True):
        if name == "default": 
            self._name = _MAIN_TAB_NAME
        else: 
            self._name = name
        flyte.report.get_tab(self._name).log(html)

    def append(self, html: str):
        flyte.report.get_tab(self._name).log(html)
    
flytekit.Deck = _DeckV2
flytekit.Deck.publish = flyte.report.flush