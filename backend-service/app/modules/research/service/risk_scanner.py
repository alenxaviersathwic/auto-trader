import re
from typing import Any, Dict, List, Set, Tuple


class RiskWordScanner:
    """
    Scans document text for negative risk terms appearing in proximity to underlyings,
    their aliases, or their constituent heavyweights.
    """

    @staticmethod
    def scan_document(
        document_text: str,
        underlying_code: str,
        aliases: List[str],
        heavyweights: List[Dict[str, Any]],
        risk_terms: List[Dict[str, Any]],
        proximity_chars: int = 400,
    ) -> List[Dict[str, Any]]:
        """
        Scans for risk words near underlying mentions.
        Returns list of risk signal hits: [{term, category, defaultSeverity, snippet}]
        """
        if not document_text:
            return []

        doc_lower = document_text.lower()
        search_names: List[str] = [underlying_code.lower()] + [a.lower() for a in aliases]
        for hw in heavyweights:
            hw_name = hw.get("name", "")
            if hw_name:
                search_names.append(hw_name.lower())
            for hw_alias in hw.get("aliases", []):
                search_names.append(hw_alias.lower())

        search_names = list(set(name for name in search_names if len(name) >= 2))
        hits: List[Dict[str, Any]] = []

        # Find positions of all underlying mentions
        mention_spans: List[Tuple[int, int]] = []
        for name in search_names:
            for match in re.finditer(re.escape(name), doc_lower):
                mention_spans.append(match.span())

        if not mention_spans:
            return []

        # Check proximity of each enabled risk term
        for rt in risk_terms:
            if not rt.get("enabled", True):
                continue
            term = rt.get("term", "").lower()
            if not term:
                continue

            for t_match in re.finditer(r"\b" + re.escape(term) + r"\b", doc_lower):
                t_start, t_end = t_match.span()
                # Check if near any mention
                is_near = any(
                    abs(t_start - m_end) <= proximity_chars or abs(m_start - t_end) <= proximity_chars
                    for m_start, m_end in mention_spans
                )
                if is_near:
                    snippet_start = max(0, t_start - 100)
                    snippet_end = min(len(document_text), t_end + 100)
                    snippet = document_text[snippet_start:snippet_end].strip()
                    hits.append({
                        "term": rt.get("term"),
                        "category": rt.get("category", "OTHER"),
                        "defaultSeverity": rt.get("defaultSeverity", 3),
                        "snippet": snippet,
                    })
                    break  # count term once per document

        return hits
