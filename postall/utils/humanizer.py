"""
Chinese Content Humanizer - Remove AI Patterns

Removes typical AI-generated patterns from Chinese content to make it feel more authentic.
Based on /humanizer-zh from James Writing Workflow.
"""

import re
from typing import List, Tuple


class ChineseHumanizer:
    """
    Remove AI patterns from Chinese content.

    Tested to produce "no AI scent" content on real X accounts.
    """

    # AI patterns to remove or simplify
    AI_PATTERNS = {
        # Template openings (模板化开头)
        'template_openings': [
            r'^在当今社会.*?[，,]',
            r'^随着.*?的发展[，,]',
            r'^近年来[，,].*?越来越',
            r'^众所周知[，,]',
            r'^不可否认的是[，,]',
        ],

        # Excessive connectors (过度使用的连接词)
        'excessive_connectors': [
            r'首先.*?其次.*?最后',
            r'一方面.*?另一方面',
            r'不仅.*?而且.*?更',
        ],

        # Empty conclusions (空洞的总结)
        'empty_conclusions': [
            r'综上所述[，,]',
            r'总而言之[，,]',
            r'总的来说[，,]',
            r'由此可见[，,]',
        ],

        # Overly polite phrases (过度礼貌用语)
        'overly_polite': [
            r'让我们来看看',
            r'值得注意的是',
            r'需要指出的是',
            r'我们可以发现',
            r'不难发现',
        ],

        # Mechanical enumeration (机械化列举)
        'mechanical_enum': [
            r'第一点.*?第二点.*?第三点',
            r'一是.*?二是.*?三是',
        ]
    }

    # English AI patterns
    AI_PATTERNS_EN = {
        'template_openings': [
            r'^In today\'s world.*?,',
            r'^With the development of.*?,',
            r'^In recent years.*?,',
            r'^It is well known that',
        ],

        'overly_polite': [
            r'Let\'s take a look at',
            r'It is worth noting that',
            r'It should be pointed out that',
            r'We can see that',
        ],

        'empty_conclusions': [
            r'In conclusion,',
            r'To sum up,',
            r'In summary,',
        ]
    }

    def humanize(self, text: str, language: str = "auto") -> str:
        """
        Remove AI patterns from text.

        Args:
            text: Input text
            language: "zh" for Chinese, "en" for English, "auto" for auto-detect

        Returns:
            Humanized text
        """
        if language == "auto":
            language = self._detect_language(text)

        if language == "zh":
            return self._humanize_chinese(text)
        else:
            return self._humanize_english(text)

    def _humanize_chinese(self, text: str) -> str:
        """Remove AI patterns from Chinese text."""
        # Remove template openings
        for pattern in self.AI_PATTERNS['template_openings']:
            text = re.sub(pattern, '', text)

        # Simplify excessive connectors
        for pattern in self.AI_PATTERNS['excessive_connectors']:
            text = self._simplify_connectors(text, pattern)

        # Remove empty conclusions
        for pattern in self.AI_PATTERNS['empty_conclusions']:
            text = re.sub(pattern, '', text)

        # Remove overly polite phrases
        for pattern in self.AI_PATTERNS['overly_polite']:
            text = re.sub(pattern, '', text)

        # Simplify mechanical enumeration
        for pattern in self.AI_PATTERNS['mechanical_enum']:
            text = self._simplify_enumeration(text, pattern)

        # Clean up extra whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)

        return text.strip()

    def _humanize_english(self, text: str) -> str:
        """Remove AI patterns from English text."""
        # Remove template openings
        for pattern in self.AI_PATTERNS_EN['template_openings']:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)

        # Remove overly polite phrases
        for pattern in self.AI_PATTERNS_EN['overly_polite']:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)

        # Remove empty conclusions
        for pattern in self.AI_PATTERNS_EN['empty_conclusions']:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)

        # Clean up extra whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)

        return text.strip()

    def _simplify_connectors(self, text: str, pattern: str) -> str:
        """Simplify excessive connector usage."""
        # Replace "首先...其次...最后" with simpler structure
        text = re.sub(r'首先[，,]', '', text)
        text = re.sub(r'其次[，,]', '', text)
        text = re.sub(r'最后[，,]', '', text)
        return text

    def _simplify_enumeration(self, text: str, pattern: str) -> str:
        """Simplify mechanical enumeration."""
        # Replace "第一点...第二点...第三点" with natural flow
        text = re.sub(r'第[一二三四五]点[：:]', '', text)
        text = re.sub(r'[一二三四五]是[：:]', '', text)
        return text

    def detect_ai_patterns(self, text: str) -> List[Tuple[str, str]]:
        """
        Detect AI patterns in text.

        Returns:
            List of (pattern_type, matched_text) tuples
        """
        detected = []
        language = self._detect_language(text)

        patterns = self.AI_PATTERNS if language == "zh" else self.AI_PATTERNS_EN

        for pattern_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                matches = re.findall(pattern, text)
                for match in matches:
                    detected.append((pattern_type, match))

        return detected

    def calculate_ai_score(self, text: str) -> float:
        """
        Calculate AI pattern score (0-1, higher = more AI-like).

        Returns:
            Score from 0 (very human) to 1 (very AI)
        """
        patterns = self.detect_ai_patterns(text)
        pattern_count = len(patterns)

        # Each pattern adds 0.1 to score, cap at 1.0
        score = min(pattern_count * 0.1, 1.0)
        return score

    @staticmethod
    def _detect_language(text: str) -> str:
        """Detect if text is Chinese or English."""
        # Count Chinese characters
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        total_chars = len(text)

        if chinese_chars / max(total_chars, 1) > 0.3:
            return "zh"
        else:
            return "en"
