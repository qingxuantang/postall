"""
RLHF Manager - Core RLHF Logic

Orchestrates the RLHF (Reinforcement Learning from Human Feedback) system:
1. Loads high-scoring rules for content generation
2. Tracks which rules are applied to each post
3. Collects feedback and updates rule scores
4. Provides exploration mode for low-confidence rules
5. Generates evolution reports

Integrated from James Writing Workflow.
"""

from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from zoneinfo import ZoneInfo
import json

from .rule_library import RuleLibrary, ContentRule
from .feedback_collector import FeedbackCollector


class RLHFManager:
    """
    RLHF Manager - Core RLHF system orchestration.

    Usage:
        manager = RLHFManager(db_path)

        # Get rules for content generation
        rules = manager.get_rules_for_generation()

        # After content generated, record which rules were applied
        manager.record_rule_application(post_id, rule_ids)

        # After user feedback, update rule scores
        manager.process_feedback(post_id)
    """

    def __init__(self, db_path: Path, timezone: str = "UTC", exploration_probability: float = 0.15):
        """
        Initialize RLHF Manager.

        Args:
            db_path: Path to SQLite database
            timezone: Timezone for timestamps
            exploration_probability: Probability of including low-confidence rules (0-1)
        """
        self.db_path = Path(db_path)
        self.timezone = ZoneInfo(timezone)
        self.exploration_probability = exploration_probability

        # Initialize components
        self.rule_library = RuleLibrary(db_path, timezone)
        self.feedback_collector = FeedbackCollector(db_path)

        # Initialize default rules if database is empty
        stats = self.rule_library.get_rule_stats()
        if stats['total_rules'] == 0:
            print("[RLHFManager] Initializing default rules...")
            self.rule_library.init_default_rules()

    def get_rules_for_generation(
        self,
        count: int = 10,
        category: Optional[str] = None,
        include_exploration: bool = True
    ) -> List[ContentRule]:
        """
        Get rules to apply for content generation.

        Includes both high-scoring rules and exploration rules (low-confidence).

        Args:
            count: Total number of rules to return
            category: Filter by category (optional)
            include_exploration: Include low-confidence rules for exploration

        Returns:
            List of ContentRule objects
        """
        # Get high-scoring rules
        high_scoring_count = int(count * (1 - self.exploration_probability)) if include_exploration else count
        high_scoring = self.rule_library.get_high_scoring_rules(limit=high_scoring_count, category=category)

        # Add exploration rules if enabled
        if include_exploration and len(high_scoring) < count:
            exploration_count = count - len(high_scoring)
            exploration_rules = self.rule_library.get_low_confidence_rules(limit=exploration_count)
            return high_scoring + exploration_rules
        else:
            return high_scoring

    def record_rule_application(self, post_id: str, rule_ids: List[str]):
        """
        Record which rules were applied to a post.

        This creates a mapping for later feedback processing.

        Args:
            post_id: Database post ID
            rule_ids: List of rule IDs that were applied
        """
        # Store in a JSON mapping file
        mapping_file = self.db_path.parent / "rule_post_mappings.json"

        try:
            if mapping_file.exists():
                mappings = json.loads(mapping_file.read_text(encoding='utf-8'))
            else:
                mappings = {}

            mappings[post_id] = {
                'rule_ids': rule_ids,
                'recorded_at': datetime.now(self.timezone).isoformat()
            }

            mapping_file.write_text(json.dumps(mappings, indent=2, ensure_ascii=False), encoding='utf-8')

            print(f"[RLHFManager] Recorded {len(rule_ids)} rules for post {post_id}")

        except Exception as e:
            print(f"[RLHFManager] Error recording rule application: {e}")

    def process_feedback(self, post_id: str):
        """
        Process feedback for a post and update rule scores.

        Collects feedback from all sources, aggregates it, and updates
        scores for all rules that were applied to this post.

        Args:
            post_id: Database post ID
        """
        # Get aggregated feedback
        feedback = self.feedback_collector.aggregate_feedback(post_id)
        final_signal = feedback['final_signal']

        if final_signal == 0.0 and not feedback['sources']:
            print(f"[RLHFManager] No feedback available for post {post_id}")
            return

        # Get rules that were applied to this post
        mapping_file = self.db_path.parent / "rule_post_mappings.json"

        if not mapping_file.exists():
            print(f"[RLHFManager] No rule mapping found for post {post_id}")
            return

        try:
            mappings = json.loads(mapping_file.read_text(encoding='utf-8'))
            rule_ids = mappings.get(post_id, {}).get('rule_ids', [])

            if not rule_ids:
                print(f"[RLHFManager] No rules mapped to post {post_id}")
                return

            # Update score for each rule
            for rule_id in rule_ids:
                self.rule_library.update_rule_score(rule_id, final_signal, post_id)

            print(f"[RLHFManager] Updated {len(rule_ids)} rules with signal {final_signal:.2f}")

        except Exception as e:
            print(f"[RLHFManager] Error processing feedback: {e}")

    def get_evolution_report(self) -> Dict[str, Any]:
        """
        Generate RLHF evolution report.

        Returns:
            Dictionary with evolution statistics and recommendations
        """
        stats = self.rule_library.get_rule_stats()

        # Get top performers
        top_rules = self.rule_library.get_high_scoring_rules(limit=10)

        # Get low performers
        with self.rule_library._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM rules
                WHERE is_active = 1 AND score < 0
                ORDER BY score ASC
                LIMIT 10
            """)

            low_rules = []
            for row in cursor.fetchall():
                low_rules.append(ContentRule(
                    id=row['id'],
                    description=row['description'],
                    category=row['category'],
                    score=row['score'],
                    applications=row['applications'],
                    success_rate=row['success_rate'],
                    confidence=row['confidence'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    is_active=bool(row['is_active'])
                ))

        # Get exploration candidates
        exploration_rules = self.rule_library.get_low_confidence_rules(limit=5)

        return {
            'stats': stats,
            'top_rules': [
                {
                    'id': r.id,
                    'description': r.description,
                    'category': r.category,
                    'score': round(r.score, 2),
                    'applications': r.applications,
                    'success_rate': round(r.success_rate * 100, 1)
                }
                for r in top_rules
            ],
            'low_rules': [
                {
                    'id': r.id,
                    'description': r.description,
                    'category': r.category,
                    'score': round(r.score, 2),
                    'applications': r.applications
                }
                for r in low_rules
            ],
            'exploration_candidates': [
                {
                    'id': r.id,
                    'description': r.description,
                    'category': r.category,
                    'applications': r.applications,
                    'confidence': round(r.confidence, 2)
                }
                for r in exploration_rules
            ],
            'recommendations': self._generate_recommendations(stats, top_rules, low_rules)
        }

    def _generate_recommendations(
        self,
        stats: Dict[str, Any],
        top_rules: List[ContentRule],
        low_rules: List[ContentRule]
    ) -> List[str]:
        """Generate actionable recommendations based on RLHF data."""
        recommendations = []

        # Check if enough data
        if stats['total_applications'] < 10:
            recommendations.append(
                "⚠️ Not enough data yet. Generate more content to improve rule scores."
            )

        # Check for strong performers
        if top_rules and top_rules[0].score > 5.0:
            recommendations.append(
                f"✅ Strong performer: '{top_rules[0].description}' (Score: {top_rules[0].score:.1f})"
            )

        # Check for weak performers
        if low_rules and low_rules[0].score < -2.0:
            recommendations.append(
                f"⚠️ Consider deactivating: '{low_rules[0].description}' (Score: {low_rules[0].score:.1f})"
            )

        # Exploration mode recommendation
        if stats['total_applications'] > 20:
            recommendations.append(
                "💡 Enable exploration mode to discover hidden gem rules"
            )

        return recommendations

    def format_prompt_with_rules(self, base_prompt: str, rules: List[ContentRule], language: str = "zh") -> str:
        """
        Format AI prompt with high-scoring rules.

        Args:
            base_prompt: Base prompt text
            rules: List of rules to include
            language: "zh" or "en"

        Returns:
            Enhanced prompt with rules
        """
        if not rules:
            return base_prompt

        rules_text = []
        rules_text.append("=== 高分规则 (High-Scoring Rules from RLHF) ===" if language == "zh" else "=== High-Scoring Rules (RLHF) ===")

        # Group by category
        by_category = {}
        for rule in rules:
            if rule.category not in by_category:
                by_category[rule.category] = []
            by_category[rule.category].append(rule)

        # Format by category
        for category, cat_rules in by_category.items():
            rules_text.append(f"\n【{category.capitalize()}】")
            for rule in cat_rules:
                confidence_stars = "★" * int(rule.confidence * 5)
                rules_text.append(f"  • {rule.description} (Score: {rule.score:.1f}, {confidence_stars})")

        rules_section = "\n".join(rules_text)

        # Insert rules after base prompt
        return f"{base_prompt}\n\n{rules_section}\n\n"
