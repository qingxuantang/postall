"""
VIRAL Scoring System

V (Validation/Violation) - Expectation validation/violation: 1-10
I (Identity) - Identity activation level: 1-10
R (Resonance) - Emotional resonance: 1-10
A (Attention) - Attention capture power: 1-10
L (Logic) - Logical credibility: 1-10

VIRAL Score = (V×1.5 + I×1.2 + R×1.3 + A×1.5 + L×0.5) / 6
Target: ≥ 7.5 for high viral potential
"""

from dataclasses import dataclass
from typing import Dict, Any
import re


@dataclass
class VIRALScore:
    """VIRAL scoring result."""
    validation_violation: float  # 1-10
    identity: float              # 1-10
    resonance: float             # 1-10
    attention: float             # 1-10
    logic: float                 # 1-10
    viral_score: float           # Weighted average

    def to_dict(self) -> Dict[str, float]:
        return {
            'validation_violation': self.validation_violation,
            'identity': self.identity,
            'resonance': self.resonance,
            'attention': self.attention,
            'logic': self.logic,
            'viral_score': self.viral_score
        }

    def is_high_potential(self) -> bool:
        """Check if content has high viral potential (≥7.5)."""
        return self.viral_score >= 7.5


class VIRALScorer:
    """
    VIRAL scoring system for content evaluation.

    Uses AI to evaluate content across 5 dimensions.
    """

    THRESHOLD_HIGH_POTENTIAL = 7.5

    @classmethod
    def score(cls, content: str, executor: Any = None) -> VIRALScore:
        """
        Calculate VIRAL score for content.

        Args:
            content: The content to score
            executor: AI executor for scoring (optional, uses heuristics if None)

        Returns:
            VIRALScore object
        """
        if executor:
            return cls._score_with_ai(content, executor)
        else:
            return cls._score_heuristic(content)

    @classmethod
    def _score_with_ai(cls, content: str, executor: Any) -> VIRALScore:
        """Score content using AI executor."""
        prompt = f"""
评估以下内容的VIRAL病毒传播潜力，给出1-10分：

内容：
{content}

请按以下5个维度评分：

1. **V (Validation/Violation)** - 期待验证/违背：内容是验证了读者预期还是打破了预期？
   - 1-3分：完全符合预期，无新意
   - 4-6分：部分打破预期
   - 7-10分：强烈颠覆认知

2. **I (Identity)** - 身份激活：内容是否让读者产生"这就是我"的认同感？
   - 1-3分：无法产生认同
   - 4-6分：部分认同
   - 7-10分：强烈认同，"说的就是我"

3. **R (Resonance)** - 情绪共鸣：内容是否触发强烈情绪反应？
   - 1-3分：平淡无波
   - 4-6分：有一定情绪触动
   - 7-10分：情绪强烈，无法忽视

4. **A (Attention)** - 注意力捕获：标题和开头是否能瞬间抓住注意力？
   - 1-3分：平庸，易被忽略
   - 4-6分：有吸引力
   - 7-10分：无法不点开

5. **L (Logic)** - 逻辑可信度：论证是否有理有据，令人信服？
   - 1-3分：逻辑混乱
   - 4-6分：基本合理
   - 7-10分：严密可信

输出JSON格式：
{{"V": 分数, "I": 分数, "R": 分数, "A": 分数, "L": 分数}}
"""

        response = executor.execute_prompt(prompt)

        # Parse JSON response
        import json
        try:
            scores = json.loads(response)
            v = float(scores.get('V', 5))
            i = float(scores.get('I', 5))
            r = float(scores.get('R', 5))
            a = float(scores.get('A', 5))
            l = float(scores.get('L', 5))
        except:
            # Fallback to heuristic
            return cls._score_heuristic(content)

        # Calculate weighted VIRAL score
        viral_score = (v * 1.5 + i * 1.2 + r * 1.3 + a * 1.5 + l * 0.5) / 6

        return VIRALScore(
            validation_violation=v,
            identity=i,
            resonance=r,
            attention=a,
            logic=l,
            viral_score=viral_score
        )

    @classmethod
    def _score_heuristic(cls, content: str) -> VIRALScore:
        """
        Heuristic scoring based on content analysis.
        Used as fallback when AI executor is not available.
        """
        # Simple heuristic scoring based on content patterns
        v = cls._score_validation(content)
        i = cls._score_identity(content)
        r = cls._score_resonance(content)
        a = cls._score_attention(content)
        l = cls._score_logic(content)

        viral_score = (v * 1.5 + i * 1.2 + r * 1.3 + a * 1.5 + l * 0.5) / 6

        return VIRALScore(
            validation_violation=v,
            identity=i,
            resonance=r,
            attention=a,
            logic=l,
            viral_score=viral_score
        )

    @staticmethod
    def _score_validation(content: str) -> float:
        """Score expectation validation/violation."""
        # Check for counter-intuitive phrases
        counter_patterns = [
            r'其实|实际上|真相是|并非|不是.*而是',
            r'actually|truth is|not.*but|contrary to'
        ]
        score = 5.0  # Default
        for pattern in counter_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                score += 1.5
        return min(score, 10.0)

    @staticmethod
    def _score_identity(content: str) -> float:
        """Score identity activation."""
        # Check for identity markers
        identity_patterns = [
            r'你|我们|如果你是',
            r'you|we|if you are'
        ]
        score = 5.0
        for pattern in identity_patterns:
            matches = len(re.findall(pattern, content, re.IGNORECASE))
            score += min(matches * 0.3, 2.0)
        return min(score, 10.0)

    @staticmethod
    def _score_resonance(content: str) -> float:
        """Score emotional resonance."""
        # Check for emotional words
        emotion_words_cn = ['焦虑', '恐惧', '希望', '愤怒', '兴奋', '失望', '惊讶']
        emotion_words_en = ['fear', 'hope', 'anger', 'excited', 'disappointed', 'shocked']

        score = 5.0
        for word in emotion_words_cn + emotion_words_en:
            if word in content.lower():
                score += 0.5
        return min(score, 10.0)

    @staticmethod
    def _score_attention(content: str) -> float:
        """Score attention capture."""
        # Check opening strength
        first_line = content.split('\n')[0] if '\n' in content else content[:100]

        score = 5.0
        # Question mark in first line
        if '?' in first_line or '？' in first_line:
            score += 1.0
        # Numbers
        if re.search(r'\d+', first_line):
            score += 1.0
        # Urgency words
        if re.search(r'现在|立即|马上|紧急|now|urgent|immediately', first_line, re.IGNORECASE):
            score += 1.5

        return min(score, 10.0)

    @staticmethod
    def _score_logic(content: str) -> float:
        """Score logical credibility."""
        score = 7.0  # Default assume decent logic

        # Check for data/statistics
        if re.search(r'\d+%|数据显示|研究表明|data shows|research shows', content, re.IGNORECASE):
            score += 1.0

        # Check for examples
        if re.search(r'例如|比如|for example|such as', content, re.IGNORECASE):
            score += 0.5

        # Check structure (if has clear paragraphs)
        paragraphs = content.split('\n\n')
        if len(paragraphs) >= 3:
            score += 0.5

        return min(score, 10.0)
