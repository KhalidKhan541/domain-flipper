from src.collectors.base import BaseCollector
from src.collectors.godaddy import GoDaddyCollector
from src.collectors.dropcatch import DropCatchCollector
from src.collectors.expireddomains import ExpiredDomainsCollector
from src.collectors.namejet import NameJetCollector
from src.collectors.dynadot import DynadotCollector

__all__ = [
    "BaseCollector",
    "GoDaddyCollector",
    "DropCatchCollector",
    "ExpiredDomainsCollector",
    "NameJetCollector",
    "DynadotCollector",
]

COLLECTORS = [
    GoDaddyCollector,
    DropCatchCollector,
    ExpiredDomainsCollector,
    NameJetCollector,
    DynadotCollector,
]
