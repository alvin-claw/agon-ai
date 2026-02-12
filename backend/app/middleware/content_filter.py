"""Keyword-based content filter for debate turn text."""

import re


class ContentFilter:
    """Checks text against blocked patterns (hate speech, violence, illegal activity)."""

    BLOCKED_PATTERNS: list[tuple[str, str]] = [
        # English hate speech
        (r"\b(?:kill\s+all|exterminate|genocide)\b", "Incitement to violence/genocide"),
        (r"\b(?:racial\s+supremacy|white\s+power|ethnic\s+cleansing)\b", "Hate speech (supremacism)"),
        (r"\b(?:gas\s+the|lynch|enslave)\s+\w+", "Hate speech (violence against groups)"),
        # English violence
        (r"\b(?:how\s+to\s+(?:make\s+a\s+bomb|build\s+(?:a\s+)?weapon|synthesize\s+poison))\b", "Illegal activity instructions"),
        (r"\b(?:terrorist\s+attack\s+plan|mass\s+(?:shooting|murder)\s+guide)\b", "Terrorism-related content"),
        # English illegal activity
        (r"\b(?:how\s+to\s+(?:hack|steal\s+identity|launder\s+money|traffic\s+(?:drugs|humans)))\b", "Illegal activity instructions"),
        (r"\b(?:child\s+(?:porn|exploitation|abuse))\b", "Child exploitation content"),
        # Korean hate speech
        (r"(?:인종\s*청소|민족\s*말살|학살\s*해야)", "혐오 발언 (인종/민족)"),
        (r"(?:여성\s*혐오|남성\s*혐오|장애인\s*혐오).*(?:죽|없애|제거)", "혐오 발언 (차별적 폭력)"),
        # Korean violence
        (r"(?:폭탄\s*(?:만들|제조)|무기\s*제작|독극물\s*합성)", "불법 활동 지침"),
        (r"(?:테러\s*계획|총기\s*난사\s*방법)", "테러 관련 콘텐츠"),
        # Korean illegal activity
        (r"(?:마약\s*(?:제조|거래)|인신\s*매매|자금\s*세탁\s*방법)", "불법 활동 지침"),
        (r"(?:아동\s*(?:포르노|착취|학대))", "아동 착취 콘텐츠"),
    ]

    def __init__(self):
        self._compiled = [
            (re.compile(pattern, re.IGNORECASE), reason)
            for pattern, reason in self.BLOCKED_PATTERNS
        ]

    def check_content(self, text: str) -> tuple[bool, str | None]:
        """Check text against blocked patterns.

        Returns:
            (True, None) if safe, (False, reason) if violation found.
        """
        for regex, reason in self._compiled:
            if regex.search(text):
                return False, reason
        return True, None


# Module-level singleton
content_filter = ContentFilter()
