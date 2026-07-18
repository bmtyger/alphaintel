import logging
from typing import Dict, Any, List
from .registry import registry
from .signals import enrich_item

logger = logging.getLogger(__name__)


class PipelineEngine:
    def __init__(self, categories: List[str] | None = None) -> None:
        self.categories = categories or ["finance", "security", "trends", "geopower"]

    def run(self) -> Dict[str, Any]:
        all_items: List[Dict[str, Any]] = []
        errors: List[str] = []
        sources = [s for s in registry.all() if s.category in self.categories]
        for source in sources:
            try:
                result = source._safe_fetch()
                if result.success and result.items:
                    for item in result.items:
                        try:
                            enriched = enrich_item(item)
                            all_items.append(enriched)
                        except Exception as exc:
                            logger.warning("Enrichment failed for %s: %s", source.name, exc)
                            all_items.append(item)
                elif not result.success:
                    errors.append(f"{source.name}: {result.error}")
                logger.info("[engine] %s produced %d items", source.name, len(result.items))
            except Exception as exc:
                errors.append(f"{source.name}: {exc}")
                logger.exception("Source %s crashed", source.name)
        # Deduplicate by headline
        seen = set()
        deduped = []
        for item in all_items:
            key = item["headline"].strip().lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        # Sort by confidence desc then timestamp desc
        deduped.sort(key=lambda x: (x.get("confidence", 0), x.get("timestamp", "")), reverse=True)
        return {"intel_stream": deduped, "errors": errors}

    @staticmethod
    def validate_schema(stream: List[Dict[str, Any]]) -> List[str]:
        problems = []
        required = {"category", "timestamp", "headline", "bullet_points", "source", "confidence"}
        valid_cats = {"finance", "security", "trends", "geopower"}
        for idx, item in enumerate(stream):
            if not isinstance(item, dict):
                problems.append(f"Item {idx} not an object")
                continue
            miss = required - item.keys()
            if miss:
                problems.append(f"Item {idx} missing: {', '.join(sorted(miss))}")
            if item.get("category") not in valid_cats:
                problems.append(f"Item {idx} invalid category: {item.get('category')}")
            if not isinstance(item.get("confidence"), (int, float)) or not (0 <= item["confidence"] <= 100):
                problems.append(f"Item {idx} confidence invalid: {item.get('confidence')}")
            if not isinstance(item.get("bullet_points"), list):
                problems.append(f"Item {idx} bullet_points not list")
            if not item.get("headline"):
                problems.append(f"Item {idx} headline empty")
        return problems

    @staticmethod
    def deduplicate_by_ticker(stream: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """For finance items, keep highest-confidence item per ticker."""
        best: Dict[str, Dict[str, Any]] = {}
        for item in stream:
            if item.get("category") != "finance":
                continue
            for t in item.get("tickers", []) or []:
                prev = best.get(t)
                if not prev or (item.get("confidence", 0) > prev.get("confidence", 0)):
                    best[t] = item
        # merge deduped finance + non-finance
        seen_titles = set()
        out = []
        for item in stream:
            if item.get("category") != "finance":
                seen_titles.add(item["headline"].strip().lower())
                out.append(item)
                continue
            if any(t in best and best[t] is item for t in item.get("tickers", [])):
                seen_titles.add(item["headline"].strip().lower())
                if item not in out:
                    out.append(item)
        return out
