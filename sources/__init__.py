from .base import BaseSource, SourceResult
from .registry import registry, autodiscover
from .sec_edgar import SecEdgarSource
from .cyber_sources import CisaKevSource, NvdSource
from .cyber_rss import KrebsOnSecuritySource, BleepingComputerSource
from .markets import RssMarketSource, FedEcxBisSource
from .markets_rss import SeekingAlphaSource
from .markets_signals import DarkPoolSource, FinraShortInterestSource, CryptoOnchainSource
from .tech_ai import RssTechSource
from .tech_extra import TechExtraSource
from .crypto import CryptoNewsSource
from .geopower import GeopowerSource
from .geopower_extra import GeoExtraSource
from .finance_expanded import FinanceRssSource
from .security_expanded import SecurityRssSource
from .tech_expanded import TechRssSource
from .geopower_rss import GeopowerRssSource
from .engine import PipelineEngine
from .signals import enrich_item, extract_tickers, classify_event, compute_market_impact

_builtin_modules = [
    "sources.cyber_sources",
    "sources.cyber_rss",
    "sources.markets",
    "sources.markets_rss",
    "sources.markets_signals",
    "sources.tech_ai",
    "sources.tech_extra",
    "sources.crypto",
    "sources.geopower",
    "sources.geopower_extra",
    "sources.finance_expanded",
    "sources.security_expanded",
    "sources.tech_expanded",
    "sources.geopower_rss",
]
autodiscover(_builtin_modules)

__all__ = [
    "BaseSource", "SourceResult", "registry", "autodiscover",
    "SecEdgarSource", "CisaKevSource", "NvdSource",
    "KrebsOnSecuritySource", "BleepingComputerSource",
    "RssMarketSource", "FedEcxBisSource",
    "SeekingAlphaSource",
    "DarkPoolSource", "FinraShortInterestSource", "CryptoOnchainSource",
    "RssTechSource", "TechExtraSource",
    "CryptoNewsSource",
    "GeopowerSource", "GeoExtraSource",
    "PipelineEngine", "enrich_item", "extract_tickers",
]
