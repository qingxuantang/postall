"""
Rule Library - Storage and Scoring of Content Rules

Manages the rule database for RLHF system.
Rules are scored based on user feedback and engagement metrics.
"""

import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from zoneinfo import ZoneInfo


@dataclass
class ContentRule:
    """A content generation rule."""
    id: str
    description: str
    category: str  # philosophy, psychology, communication, sociology
    score: float
    applications: int
    success_rate: float
    confidence: float  # 0-1, based on number of applications
    created_at: str
    updated_at: str
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContentRule':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class RuleLibrary:
    """
    Storage and management of content generation rules.

    Rules are stored in SQLite and scored based on feedback.
    """

    def __init__(self, db_path: Path, timezone: str = "UTC"):
        """
        Initialize rule library.

        Args:
            db_path: Path to SQLite database file
            timezone: Timezone for timestamps
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.timezone = ZoneInfo(timezone)
        self._init_database()

    def _init_database(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            # Create rules table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rules (
                    id TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    score REAL DEFAULT 0.0,
                    applications INTEGER DEFAULT 0,
                    success_rate REAL DEFAULT 0.0,
                    confidence REAL DEFAULT 0.0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1
                )
            """)

            # Create rule applications table (track each use)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rule_applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_id TEXT NOT NULL,
                    post_id TEXT,
                    feedback_signal REAL,
                    engagement_score REAL,
                    applied_at TEXT NOT NULL,
                    FOREIGN KEY (rule_id) REFERENCES rules(id)
                )
            """)

            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rules_score ON rules(score DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rules_category ON rules(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rule_apps_rule_id ON rule_applications(rule_id)")

            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def add_rule(self, rule: ContentRule) -> bool:
        """
        Add a new rule to the library.

        Args:
            rule: ContentRule object

        Returns:
            True if successful
        """
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO rules (id, description, category, score, applications,
                                      success_rate, confidence, created_at, updated_at, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    rule.id, rule.description, rule.category, rule.score,
                    rule.applications, rule.success_rate, rule.confidence,
                    rule.created_at, rule.updated_at, int(rule.is_active)
                ))
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Rule already exists
            return False
        except Exception as e:
            print(f"[RuleLibrary] Error adding rule: {e}")
            return False

    def get_rule(self, rule_id: str) -> Optional[ContentRule]:
        """Get a rule by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM rules WHERE id = ?", (rule_id,))
            row = cursor.fetchone()

            if row:
                return ContentRule(
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
                )
        return None

    def get_high_scoring_rules(self, limit: int = 10, category: Optional[str] = None) -> List[ContentRule]:
        """
        Get top-scoring rules for content generation.

        Args:
            limit: Maximum number of rules to return
            category: Filter by category (optional)

        Returns:
            List of ContentRule objects
        """
        with self._get_connection() as conn:
            if category:
                cursor = conn.execute("""
                    SELECT * FROM rules
                    WHERE is_active = 1 AND category = ? AND score > 0
                    ORDER BY score DESC, confidence DESC
                    LIMIT ?
                """, (category, limit))
            else:
                cursor = conn.execute("""
                    SELECT * FROM rules
                    WHERE is_active = 1 AND score > 0
                    ORDER BY score DESC, confidence DESC
                    LIMIT ?
                """, (limit,))

            rules = []
            for row in cursor.fetchall():
                rules.append(ContentRule(
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

            return rules

    def get_low_confidence_rules(self, limit: int = 5) -> List[ContentRule]:
        """
        Get low-confidence rules for exploration.

        These are rules with few applications that might be hidden gems.

        Returns:
            List of ContentRule objects
        """
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM rules
                WHERE is_active = 1 AND applications < 5 AND score >= -0.5
                ORDER BY RANDOM()
                LIMIT ?
            """, (limit,))

            rules = []
            for row in cursor.fetchall():
                rules.append(ContentRule(
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

            return rules

    def update_rule_score(self, rule_id: str, feedback_signal: float, post_id: Optional[str] = None):
        """
        Update rule score based on feedback.

        Args:
            rule_id: Rule ID
            feedback_signal: Feedback signal value (+1.0 to -1.0)
            post_id: Associated post ID (optional)
        """
        with self._get_connection() as conn:
            # Record application
            conn.execute("""
                INSERT INTO rule_applications (rule_id, post_id, feedback_signal, applied_at)
                VALUES (?, ?, ?, ?)
            """, (rule_id, post_id, feedback_signal, datetime.now(self.timezone).isoformat()))

            # Update rule score and stats
            conn.execute("""
                UPDATE rules
                SET score = score + ?,
                    applications = applications + 1,
                    success_rate = (
                        SELECT AVG(CASE WHEN feedback_signal > 0 THEN 1.0 ELSE 0.0 END)
                        FROM rule_applications
                        WHERE rule_id = ?
                    ),
                    confidence = MIN(1.0, applications * 0.1),
                    updated_at = ?
                WHERE id = ?
            """, (feedback_signal, rule_id, datetime.now(self.timezone).isoformat(), rule_id))

            conn.commit()

    def get_rule_stats(self) -> Dict[str, Any]:
        """Get overall rule library statistics."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total_rules,
                    SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_rules,
                    SUM(CASE WHEN score > 0 THEN 1 ELSE 0 END) as positive_rules,
                    SUM(CASE WHEN score < 0 THEN 1 ELSE 0 END) as negative_rules,
                    AVG(score) as avg_score,
                    SUM(applications) as total_applications
                FROM rules
            """)
            row = cursor.fetchone()

            return {
                'total_rules': row['total_rules'],
                'active_rules': row['active_rules'],
                'positive_rules': row['positive_rules'],
                'negative_rules': row['negative_rules'],
                'avg_score': row['avg_score'] or 0.0,
                'total_applications': row['total_applications'] or 0
            }

    def init_default_rules(self):
        """Initialize default rules from Four-Dimensional framework."""
        now = datetime.now(self.timezone).isoformat()

        default_rules = [
            # Philosophy rules
            ContentRule(
                id="phil_001",
                description="Use Heidegger's Being-toward-death to create existential urgency",
                category="philosophy",
                score=0.0,
                applications=0,
                success_rate=0.0,
                confidence=0.0,
                created_at=now,
                updated_at=now
            ),
            ContentRule(
                id="phil_002",
                description="Apply Nietzsche's value revaluation to subvert conventional beliefs",
                category="philosophy",
                score=0.0,
                applications=0,
                success_rate=0.0,
                confidence=0.0,
                created_at=now,
                updated_at=now
            ),
            ContentRule(
                id="phil_003",
                description="Use Foucault's power/knowledge framework to reveal hidden control",
                category="philosophy",
                score=0.0,
                applications=0,
                success_rate=0.0,
                confidence=0.0,
                created_at=now,
                updated_at=now
            ),

            # Psychology rules
            ContentRule(
                id="psych_001",
                description="Activate Jung's Hero archetype through transformation narrative",
                category="psychology",
                score=0.0,
                applications=0,
                success_rate=0.0,
                confidence=0.0,
                created_at=now,
                updated_at=now
            ),
            ContentRule(
                id="psych_002",
                description="Trigger fear emotion through unknown dangers",
                category="psychology",
                score=0.0,
                applications=0,
                success_rate=0.0,
                confidence=0.0,
                created_at=now,
                updated_at=now
            ),
            ContentRule(
                id="psych_003",
                description="Create curiosity gap with 'the truth about X' framing",
                category="psychology",
                score=0.0,
                applications=0,
                success_rate=0.0,
                confidence=0.0,
                created_at=now,
                updated_at=now
            ),

            # Communication rules
            ContentRule(
                id="comm_001",
                description="Apply AIDA model: Attention → Interest → Desire → Action",
                category="communication",
                score=0.0,
                applications=0,
                success_rate=0.0,
                confidence=0.0,
                created_at=now,
                updated_at=now
            ),
            ContentRule(
                id="comm_002",
                description="Provide social currency through exclusive insights",
                category="communication",
                score=0.0,
                applications=0,
                success_rate=0.0,
                confidence=0.0,
                created_at=now,
                updated_at=now
            ),

            # Sociology rules
            ContentRule(
                id="soc_001",
                description="Create 'We vs They' social identity division",
                category="sociology",
                score=0.0,
                applications=0,
                success_rate=0.0,
                confidence=0.0,
                created_at=now,
                updated_at=now
            ),
            ContentRule(
                id="soc_002",
                description="Use upward social comparison to motivate action",
                category="sociology",
                score=0.0,
                applications=0,
                success_rate=0.0,
                confidence=0.0,
                created_at=now,
                updated_at=now
            ),
        ]

        for rule in default_rules:
            self.add_rule(rule)

        print(f"[RuleLibrary] Initialized {len(default_rules)} default rules")
