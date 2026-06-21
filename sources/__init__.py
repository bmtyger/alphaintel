from .base import BaseSource, SourceResult
from .registry import registry, autodiscover
from .sec_edgar import SecEdgarSource
from .cyber_sources import CisaKevSource, NvdSource
from .cyber_rss import KrebsOnSecuritySource, BleepingComputerSource
from .markets import RssMarketSource, FedEcxBisSource
from .markets_signals import DarkPoolSource, FinraShortInterestSource, CryptoOnchainSource
from .tech_ai import RssTechSource
from .crypto import CryptoNewsSource
from .geopower import GeopowerSource
from .engine import PipelineEngine
from .signals import enrich_item, extract_tickers, classify_event, compute_market_impact

_builtin_modules = [
    "sources.cyber_sources",
    "sources.cyber_rss",
    "sources.markets",
    "sources.markets_signals",
    "sources.tech_ai",
    "sources.crypto",
    "sources.geopower",
]
autodiscover(_builtin_modules)

__all__ = [
    "BaseSource", "SourceResult", "registry", "autodiscover",
    "SecEdgarSource", "CisaKevSource", "NvdSource",
    "KrebsOnSecuritySource", "BleepingComputerSource",
    "RssMarketSource", "FedEcxBisSource",
    "DarkPoolSource", "FinraShortInterestSource", "CryptoOnchainSource",
    "RssTechSource", "CryptoNewsSource", "GeopowerSource",
    "PipelineEngine", "enrich_item", "extract_tickers",
]
