"""Prompt injection detection."""

import re


class InjectionDetector:
    """Detect potential prompt injection attempts."""

    # Common injection patterns
    INJECTION_PATTERNS = [
        r"ignore\s+(previous|above|prior)\s+instructions?",
        r"disregard\s+(previous|above|prior)\s+instructions?",
        r"forget\s+(previous|above|prior)\s+instructions?",
        r"new\s+instructions?:",
        r"system\s*:",
        r"override\s+",
        r"you\s+are\s+now",
        r"act\s+as\s+",
        r"pretend\s+to\s+be",
        r"roleplay\s+as",
        r"simulate\s+",
        r"<\s*system\s*>",
        r"<\s*prompt\s*>",
        r"show\s+me\s+(your|the)\s+(prompt|instructions?|system)",
        r"what\s+(are|is)\s+your\s+(prompt|instructions?|system)",
        r"reveal\s+your\s+(prompt|instructions?|system)",
        r"score\s+this\s+(10|9|8)",  # Explicit score manipulation
        r"must\s+score\s+",
        r"should\s+score\s+",
    ]

    def __init__(self):
        """Initialize detector with compiled patterns."""
        self.patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.INJECTION_PATTERNS]

    def detect(self, text: str) -> tuple[bool, list[str]]:
        """
        Detect injection attempts in text.

        Returns:
            Tuple of (is_injection, matched_patterns)
        """
        matched = []

        for pattern in self.patterns:
            if pattern.search(text):
                matched.append(pattern.pattern)

        return len(matched) > 0, matched

    def sanitize(self, text: str) -> str:
        """
        Sanitize input text.

        Remove or escape potentially dangerous characters.
        """
        # Remove excessive whitespace
        text = " ".join(text.split())

        # Remove control characters except newlines
        text = "".join(char for char in text if char.isprintable() or char == "\n")

        return text


# Global detector instance
detector = InjectionDetector()
