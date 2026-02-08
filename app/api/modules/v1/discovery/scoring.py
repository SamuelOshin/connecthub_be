"""
Scoring algorithm for matching engine.
Based on matching_engine_spec.md - Multi-Signal Scoring Formula

FinalScore = 0.25 × Preference_Overlap
           + 0.25 × Behavioral_Compatibility  
           + 0.20 × Effort_Score
           + 0.15 × Activity_Freshness
           + 0.10 × Feedback_History
           + 0.05 × Discovery_Exploration
"""

import math
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.api.core.config import settings


# ===========================================
# CONFIGURATION
# ===========================================

SCORING_WEIGHTS = {
    "preference_overlap": 0.25,
    "behavioral_compatibility": 0.25,
    "effort_score": 0.20,
    "activity_freshness": 0.15,
    "feedback_history": 0.10,
    "exploration": 0.05,
}

# Activity freshness half-life in hours (72 hours = 3 days)
FRESHNESS_HALF_LIFE_HOURS = 72


# ===========================================
# DATA CLASSES
# ===========================================


@dataclass
class UserProfile:
    """User profile data for scoring."""

    id: str
    age: int
    gender: Optional[str]
    location_lat: float
    location_lng: float
    bio: Optional[str]
    prompts: list[dict]
    is_verified: bool = False


@dataclass
class UserPreferences:
    """User matching preferences."""

    min_age: int = 18
    max_age: int = 99
    max_distance_km: int = 50
    gender_preferences: list[str] = None

    def __post_init__(self):
        if self.gender_preferences is None:
            self.gender_preferences = []


@dataclass
class UserScores:
    """User behavioral scores."""

    response_rate: float = 0.5
    avg_response_time_hours: Optional[float] = None
    message_quality_score: float = 0.5
    comment_quality_avg: float = 0.5
    profile_completion: float = 0.0
    photo_quality_avg: float = 0.5
    dates_from_matches_ratio: float = 0.0
    positive_feedback_ratio: float = 0.5
    last_active: Optional[datetime] = None
    ghost_count: int = 0


@dataclass
class MatchScore:
    """Result of match scoring calculation."""

    final_score: float
    breakdown: dict[str, float]
    reasons: list[str]


# ===========================================
# SCORING FUNCTIONS
# ===========================================


def calculate_match_score(
    viewer_profile: UserProfile,
    viewer_prefs: UserPreferences,
    viewer_scores: UserScores,
    candidate_profile: UserProfile,
    candidate_prefs: UserPreferences,
    candidate_scores: UserScores,
    distance_km: float,
) -> MatchScore:
    """
    Calculate compatibility score between two users.
    Returns a score from 0.0 to 1.0 with breakdown.
    """

    scores = {}

    # 1. Preference Overlap (0.0 - 1.0)
    scores["preference_overlap"] = calculate_preference_overlap(
        viewer_prefs=viewer_prefs,
        viewer_profile=viewer_profile,
        candidate_prefs=candidate_prefs,
        candidate_profile=candidate_profile,
        distance_km=distance_km,
    )

    # 2. Behavioral Compatibility (0.0 - 1.0)
    scores["behavioral_compatibility"] = calculate_behavioral_compatibility(
        viewer_scores=viewer_scores,
        candidate_scores=candidate_scores,
    )

    # 3. Effort Score (0.0 - 1.0)
    scores["effort_score"] = calculate_effort_score(candidate_scores)

    # 4. Activity Freshness (0.0 - 1.0)
    scores["activity_freshness"] = calculate_freshness(candidate_scores.last_active)

    # 5. Feedback History (0.0 - 1.0)
    scores["feedback_history"] = candidate_scores.positive_feedback_ratio

    # 6. Exploration Factor (0.0 - 1.0)
    scores["exploration"] = random.uniform(0.3, 1.0)

    # Calculate weighted final score
    final_score = sum(scores[key] * SCORING_WEIGHTS[key] for key in SCORING_WEIGHTS)

    # Generate human-readable match reasons
    reasons = generate_match_reasons(
        viewer_profile=viewer_profile,
        candidate_profile=candidate_profile,
        candidate_scores=candidate_scores,
        distance_km=distance_km,
        scores=scores,
    )

    return MatchScore(
        final_score=min(1.0, max(0.0, final_score)),
        breakdown=scores,
        reasons=reasons,
    )


def calculate_preference_overlap(
    viewer_prefs: UserPreferences,
    viewer_profile: UserProfile,
    candidate_prefs: UserPreferences,
    candidate_profile: UserProfile,
    distance_km: float,
) -> float:
    """
    Bidirectional preference matching.
    Both users should match each other's preferences.
    """

    # Viewer's preferences vs Candidate's attributes
    viewer_to_candidate = 0.0

    # Age match
    if viewer_prefs.min_age <= candidate_profile.age <= viewer_prefs.max_age:
        viewer_to_candidate += 1.0

    # Distance match
    if distance_km <= viewer_prefs.max_distance_km:
        viewer_to_candidate += 1.0

    # Gender match
    if not viewer_prefs.gender_preferences or candidate_profile.gender in viewer_prefs.gender_preferences:
        viewer_to_candidate += 1.0

    viewer_to_candidate /= 3  # Normalize

    # Candidate's preferences vs Viewer's attributes
    candidate_to_viewer = 0.0

    # Age match
    if candidate_prefs.min_age <= viewer_profile.age <= candidate_prefs.max_age:
        candidate_to_viewer += 1.0

    # Distance match (symmetric)
    if distance_km <= candidate_prefs.max_distance_km:
        candidate_to_viewer += 1.0

    # Gender match
    if not candidate_prefs.gender_preferences or viewer_profile.gender in candidate_prefs.gender_preferences:
        candidate_to_viewer += 1.0

    candidate_to_viewer /= 3

    # Both directions must be satisfied (geometric mean)
    if viewer_to_candidate == 0 or candidate_to_viewer == 0:
        return 0.0

    return math.sqrt(viewer_to_candidate * candidate_to_viewer)


def calculate_behavioral_compatibility(
    viewer_scores: UserScores,
    candidate_scores: UserScores,
) -> float:
    """
    Match users with similar communication patterns.
    Avoid matching high-effort users with ghosts.
    """

    # Response rate similarity
    response_diff = abs(viewer_scores.response_rate - candidate_scores.response_rate)
    response_similarity = 1.0 - response_diff

    # Response time compatibility
    viewer_time = viewer_scores.avg_response_time_hours or 12
    candidate_time = candidate_scores.avg_response_time_hours or 12
    time_diff = abs(viewer_time - candidate_time)
    time_similarity = max(0, 1.0 - (time_diff / 24))  # 24 hour diff = 0 similarity

    # Message quality similarity
    quality_diff = abs(
        viewer_scores.message_quality_score - candidate_scores.message_quality_score
    )
    quality_similarity = 1.0 - quality_diff

    # Weighted average
    return 0.4 * response_similarity + 0.3 * time_similarity + 0.3 * quality_similarity


def calculate_effort_score(user_scores: UserScores) -> float:
    """
    Reward users who put effort into the platform.
    """

    return (
        0.30 * user_scores.profile_completion
        + 0.25 * user_scores.photo_quality_avg
        + 0.25 * user_scores.comment_quality_avg
        + 0.20 * user_scores.response_rate
    )


def calculate_freshness(last_active: Optional[datetime]) -> float:
    """
    Boost recently active users, penalize dormant ones.
    Uses exponential decay with 72-hour half-life.
    """

    if last_active is None:
        return 0.5  # Default for unknown activity

    now = datetime.now(timezone.utc)
    
    # Handle naive datetime
    if last_active.tzinfo is None:
        last_active = last_active.replace(tzinfo=timezone.utc)

    hours_since_active = (now - last_active).total_seconds() / 3600

    # Exponential decay with 72-hour half-life
    freshness = math.exp(-0.693 * hours_since_active / FRESHNESS_HALF_LIFE_HOURS)

    return max(0.1, freshness)  # Floor at 0.1


def generate_match_reasons(
    viewer_profile: UserProfile,
    candidate_profile: UserProfile,
    candidate_scores: UserScores,
    distance_km: float,
    scores: dict[str, float],
) -> list[str]:
    """
    Generate human-readable reasons for the match.
    Shown to users for transparency.
    """

    reasons = []

    # Distance
    if distance_km < 5:
        reasons.append(f"Lives nearby ({distance_km:.1f} km away)")
    elif distance_km < 20:
        reasons.append(f"{distance_km:.0f} km away")

    # Age
    age_diff = abs(viewer_profile.age - candidate_profile.age)
    if age_diff <= 2:
        reasons.append("Similar age")

    # Shared interests (from prompts)
    shared = find_shared_interests(viewer_profile.prompts, candidate_profile.prompts)
    for interest in shared[:2]:
        reasons.append(f"Both love {interest}")

    # High effort user
    if scores.get("effort_score", 0) > 0.7:
        reasons.append("Detailed profile")

    # Good track record
    if scores.get("feedback_history", 0) > 0.7:
        reasons.append("Great past connections")

    # High response rate
    if candidate_scores.response_rate > 0.8:
        reasons.append("Usually responds")

    # Verified
    if candidate_profile.is_verified:
        reasons.append("Verified profile")

    return reasons[:4]  # Max 4 reasons


def find_shared_interests(
    viewer_prompts: list[dict],
    candidate_prompts: list[dict],
) -> list[str]:
    """
    Find shared interests from prompts.
    Simple keyword matching for now.
    """

    # Common interest keywords to look for
    interest_keywords = [
        "hiking", "travel", "music", "movies", "cooking", "fitness",
        "reading", "art", "photography", "gaming", "sports", "yoga",
        "dancing", "wine", "coffee", "dogs", "cats", "nature",
        "beach", "mountains", "running", "cycling", "swimming",
    ]

    viewer_text = " ".join(
        str(p.get("answer", "")).lower() for p in viewer_prompts
    )
    candidate_text = " ".join(
        str(p.get("answer", "")).lower() for p in candidate_prompts
    )

    shared = []
    for keyword in interest_keywords:
        if keyword in viewer_text and keyword in candidate_text:
            shared.append(keyword)

    return shared


def get_response_badge(response_rate: float) -> Optional[str]:
    """
    Get response rate badge for display.
    """

    if response_rate >= 0.9:
        return "VERY_RESPONSIVE"
    elif response_rate >= 0.7:
        return "RESPONSIVE"
    elif response_rate >= 0.4:
        return "SOMETIMES_RESPONDS"
    return None
