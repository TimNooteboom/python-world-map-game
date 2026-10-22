"""One class per kind of mode; build_modes makes one object for every entry in config.MODES."""

from ..config import MODES
from .guess import GuessMode
from .learn import CountryLearnMode, FactLearnMode
from .naming import NamingMode
from .quiz import QuizGameMode


def mode_class(info):
    if info.subject in ("guess", "guess_capital"):
        return GuessMode
    if info.subject == "countries":
        return NamingMode if info.kind == "game" else CountryLearnMode
    return QuizGameMode if info.kind == "game" else FactLearnMode


def build_modes(app):
    """{mode key: mode object} for every mode in the menu."""
    return {key: mode_class(info)(app, key) for key, info in MODES.items()}
