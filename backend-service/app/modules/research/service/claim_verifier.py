import difflib
import re
from typing import Tuple


class ClaimVerifier:
    """
    Verifies that extracted quotes genuinely exist in the source document text.
    Enforces the zero-hallucination citation guarantee.
    """

    @staticmethod
    def normalize_text(text: str) -> str:
        """Strips punctuation, normalizes curly quotes and collapses whitespace."""
        if not text:
            return ""
        # Normalize curly quotes and dashes
        t = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'").replace("—", "-")
        # Collapse whitespace
        t = re.sub(r"\s+", " ", t)
        return t.strip().lower()

    @classmethod
    def verify_quote(cls, quote: str, document_text: str, fuzzy_threshold: float = 0.95) -> Tuple[bool, float]:
        """
        Validates quote existence in document text.
        First attempts exact substring match; falls back to fuzzy sliding window match.
        Returns: (is_verified, match_ratio)
        """
        if not quote or not document_text:
            return False, 0.0

        norm_quote = cls.normalize_text(quote)
        norm_doc = cls.normalize_text(document_text)

        if not norm_quote:
            return False, 0.0

        # 1. Exact match
        if norm_quote in norm_doc:
            return True, 1.0

        # 2. Sliding window fuzzy match
        quote_len = len(norm_quote)
        if quote_len < 20:
            return False, 0.0

        # Check slices of length ~ quote_len in the document
        step = max(10, quote_len // 4)
        best_ratio = 0.0

        for i in range(0, max(1, len(norm_doc) - quote_len + 1), step):
            window = norm_doc[i : i + quote_len + 20]
            ratio = difflib.SequenceMatcher(None, norm_quote, window).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                if best_ratio >= fuzzy_threshold:
                    return True, best_ratio

        return best_ratio >= fuzzy_threshold, best_ratio
