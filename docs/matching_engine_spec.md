# ConnectHub Matching Engine - Technical Specification

> **Version**: 1.0  
> **Last Updated**: February 2026  
> **Status**: Design Phase  
> **Author**: Architecture Team

---

## Executive Summary

This document specifies the technical design for ConnectHub's matching engine - the core differentiator of our dating platform. Based on extensive research into dating app algorithms, industry trends, and user behavior, this specification outlines an **outcome-optimized** matching system designed to maximize real-world relationship success, not engagement metrics.

### Key Differentiators

| Traditional Apps | ConnectHub |
|------------------|------------|
| Optimize for swipes/time-on-app | Optimize for dates & relationships |
| Elo-style popularity rankings | Balanced visibility algorithm |
| Passive likes allowed | Required comment with every like |
| No outcome feedback | "We Connected" feedback loop |
| Black-box algorithm | Transparent matching reasons |

---

## Table of Contents

1. [Research Foundation](#1-research-foundation)
2. [Architecture Overview](#2-architecture-overview)
3. [Database Schema](#3-database-schema)
4. [Scoring Algorithm](#4-scoring-algorithm)
5. [Discovery Service](#5-discovery-service)
6. [Swipe & Match Logic](#6-swipe--match-logic)
7. [Feedback Loop System](#7-feedback-loop-system)
8. [Anti-Ghost Mechanics](#8-anti-ghost-mechanics)
9. [API Specification](#9-api-specification)
10. [Background Workers](#10-background-workers)
11. [Frontend Components](#11-frontend-components)
12. [Performance & Scaling](#12-performance--scaling)
13. [Privacy & Transparency](#13-privacy--transparency)
14. [Implementation Roadmap](#14-implementation-roadmap)

---

## 1. Research Foundation

### 1.1 Industry Statistics (2025-2026)

| Metric | Value | Source |
|--------|-------|--------|
| App deletion within 1 month | 69% | AppsFlyer 2025 |
| Tinder subscriber decline | 9 consecutive quarters | TechCrunch Nov 2025 |
| Users who experienced harassment | 48% | Pew Research 2023 |
| Positive experience rate | Only 53% | Pew Research 2023 |
| Partnered adults who met on apps | Only 10% | Pew Research 2023 |
| Likes with comments → date conversion | 2x higher | Hinge 2025 |

### 1.2 What Makes Matches Work

Based on Gale-Shapley algorithm (Nobel Prize 2012) and Hinge's research:

1. **Stable Matching** - No two people would prefer each other over their current matches
2. **Effort Signals** - Comments with likes are 2x more likely to result in dates
3. **Outcome Feedback** - Hinge's "We Met" feature is the only real success optimizer
4. **Behavioral Compatibility** - When/how people communicate matters

### 1.3 What Doesn't Work

1. **Elo-style scoring** - Creates winner-take-all dynamics (80/20 problem)
2. **Collaborative filtering without diversity** - Amplifies early user biases
3. **Passive swiping** - Leads to low-quality matches and ghosting
4. **AI-generated messages** - Gen Z rejects this (Bloomberg 2025)

---

## 2. Architecture Overview

### 2.1 System Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (Next.js)                            │
├─────────────────────────────────────────────────────────────────────────┤
│  Discovery UI  │  Match Modal  │  Chat  │  Feedback Forms  │  Profile   │
└───────┬────────┴───────┬───────┴───┬────┴────────┬─────────┴─────┬──────┘
        │                │           │             │               │
        ▼                ▼           ▼             ▼               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         FASTAPI BACKEND                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐       │
│  │  DISCOVERY       │  │  MATCHING        │  │  FEEDBACK        │       │
│  │  SERVICE         │  │  SERVICE         │  │  SERVICE         │       │
│  │                  │  │                  │  │                  │       │
│  │  - PostGIS query │  │  - Swipe logic   │  │  - "We Connected"│       │
│  │  - Preference    │  │  - Mutual detect │  │  - Rating storage│       │
│  │    filtering     │  │  - Match create  │  │  - ML training   │       │
│  │  - Multi-signal  │  │  - Notification  │  │    data prep     │       │
│  │    scoring       │  │                  │  │                  │       │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘       │
│           │                     │                     │                  │
│           ▼                     ▼                     ▼                  │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    SCORING ENGINE                                 │   │
│  │                                                                   │   │
│  │   FinalScore = 0.25 × Preference_Overlap                         │   │
│  │              + 0.25 × Behavioral_Compatibility                    │   │
│  │              + 0.20 × Effort_Score                                │   │
│  │              + 0.15 × Activity_Freshness                          │   │
│  │              + 0.10 × Feedback_History                            │   │
│  │              + 0.05 × Discovery_Exploration                       │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         SUPABASE PLATFORM                                │
├─────────────────────────────────────────────────────────────────────────┤
│  PostgreSQL + PostGIS  │  Realtime  │  Auth  │  Storage  │  Edge Funcs  │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         ARQ WORKERS (Background)                         │
├─────────────────────────────────────────────────────────────────────────┤
│  Score Recalc  │  Match Detection  │  Notifications  │  ML Training     │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Geospatial | PostGIS + GIST Index | O(log n) distance queries |
| Caching | Redis | Score caching, rate limiting |
| Background Jobs | ARQ | Async score calculation |
| ML (Future) | Scikit-learn → TensorFlow | Compatibility prediction |
| Real-time | Supabase Realtime | Match notifications |

---

## 3. Database Schema

### 3.1 Core Tables

```sql
-- ============================================
-- DISCOVERY & MATCHING TABLES
-- ============================================

-- User preferences for matching
CREATE TABLE public.user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE UNIQUE,
    
    -- Hard Filters (Dealbreakers)
    min_age INT DEFAULT 18,
    max_age INT DEFAULT 99,
    max_distance_km INT DEFAULT 50,
    gender_preferences TEXT[] DEFAULT '{}',
    
    -- Soft Preferences (Influence Score)
    preferred_height_min_cm INT,
    preferred_height_max_cm INT,
    preferred_education TEXT[],
    preferred_religion TEXT[],
    preferred_smoking TEXT,
    preferred_drinking TEXT,
    preferred_children TEXT,
    
    -- Matching Behavior
    show_verified_only BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Swipes with required comments
CREATE TABLE public.swipes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    liker_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    liked_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    direction TEXT NOT NULL CHECK (direction IN ('PASS', 'LIKE', 'SUPER_LIKE')),
    
    -- REQUIRED for LIKE/SUPER_LIKE (our differentiator)
    comment TEXT,
    comment_target TEXT, -- 'photo_1', 'prompt_2', etc.
    
    -- Analytics
    time_spent_viewing_ms INT,
    profile_scroll_depth FLOAT, -- 0.0 to 1.0
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(liker_id, liked_id),
    
    -- Enforce comment requirement for likes
    CONSTRAINT require_comment_for_like 
        CHECK (direction = 'PASS' OR (comment IS NOT NULL AND LENGTH(comment) >= 10))
);

-- Matches (mutual likes)
CREATE TABLE public.matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user1_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    user2_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    
    -- Match metadata
    matched_at TIMESTAMPTZ DEFAULT NOW(),
    first_message_at TIMESTAMPTZ,
    
    -- Status tracking
    status TEXT DEFAULT 'ACTIVE' CHECK (status IN (
        'ACTIVE',      -- Normal state
        'EXPIRED',     -- No message in 72 hours
        'UNMATCHED',   -- One party unmatched
        'REPORTED'     -- Safety issue
    )),
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '72 hours'),
    
    -- "We Connected" feedback
    feedback_requested_at TIMESTAMPTZ,
    user1_feedback JSONB,  -- See Feedback schema below
    user2_feedback JSONB,
    
    UNIQUE(user1_id, user2_id)
);

-- User behavior scores (recalculated by workers)
CREATE TABLE public.user_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE UNIQUE,
    
    -- Response behavior
    response_rate FLOAT DEFAULT 0.5,         -- 0.0 to 1.0
    avg_response_time_hours FLOAT,
    message_quality_score FLOAT DEFAULT 0.5, -- Based on length, questions, etc.
    
    -- Engagement quality
    comment_quality_avg FLOAT DEFAULT 0.5,   -- AI-scored comment thoughtfulness
    profile_completion FLOAT DEFAULT 0.0,    -- 0.0 to 1.0
    photo_quality_avg FLOAT DEFAULT 0.5,     -- AI-scored photo quality
    
    -- Outcome history (most important!)
    dates_from_matches_ratio FLOAT DEFAULT 0.0,  -- Matches that led to dates
    positive_feedback_ratio FLOAT DEFAULT 0.5,   -- From "We Connected"
    
    -- Activity
    last_active TIMESTAMPTZ DEFAULT NOW(),
    days_since_signup INT DEFAULT 0,
    
    -- Anti-abuse
    report_count INT DEFAULT 0,
    ghost_count INT DEFAULT 0,  -- Matches expired without message
    
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Discovery queue (precomputed recommendations)
CREATE TABLE public.discovery_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    candidate_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    
    -- Scoring breakdown (for transparency)
    final_score FLOAT NOT NULL,
    preference_overlap_score FLOAT,
    behavioral_compatibility_score FLOAT,
    effort_score FLOAT,
    activity_freshness_score FLOAT,
    feedback_history_score FLOAT,
    exploration_score FLOAT,
    
    -- Why this match? (for UI transparency)
    match_reasons JSONB, -- ['Both love hiking', 'Similar age', 'High response rate']
    
    -- Queue management
    position INT,
    shown_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '24 hours'),
    
    UNIQUE(user_id, candidate_id)
);

-- "We Connected" feedback (the secret sauce)
CREATE TABLE public.connection_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id UUID REFERENCES matches(id) ON DELETE CASCADE,
    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    
    -- Core feedback
    did_you_meet BOOLEAN,
    meeting_type TEXT CHECK (meeting_type IN ('VIDEO_CALL', 'IN_PERSON', 'STILL_CHATTING', 'NO_CONTACT')),
    
    -- If met
    would_meet_again BOOLEAN,
    connection_quality INT CHECK (connection_quality BETWEEN 1 AND 5),
    
    -- What made it work/not work
    positive_factors TEXT[], -- ['Great conversation', 'Shared interests', 'Attractive']
    negative_factors TEXT[], -- ['No chemistry', 'Different than photos', 'Bad communicator']
    
    -- Free text (optional)
    notes TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(match_id, user_id)
);

-- ============================================
-- INDEXES FOR PERFORMANCE
-- ============================================

-- Geospatial index (already exists on profiles.location)
-- CREATE INDEX idx_profiles_location ON profiles USING GIST (location);

-- Discovery performance
CREATE INDEX idx_discovery_queue_user ON discovery_queue(user_id, position);
CREATE INDEX idx_discovery_queue_expires ON discovery_queue(expires_at);

-- Swipe lookup
CREATE INDEX idx_swipes_liker ON swipes(liker_id, created_at DESC);
CREATE INDEX idx_swipes_liked ON swipes(liked_id, direction);

-- Active matches
CREATE INDEX idx_matches_active ON matches(user1_id, user2_id) WHERE status = 'ACTIVE';
CREATE INDEX idx_matches_expires ON matches(expires_at) WHERE status = 'ACTIVE';

-- Score lookup
CREATE INDEX idx_user_scores_user ON user_scores(user_id);
```

### 3.2 RLS Policies

```sql
-- Users can only see their own preferences
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own preferences"
    ON user_preferences FOR ALL
    USING (auth.uid() = user_id);

-- Swipes are private to the liker (liked person can't see until match)
ALTER TABLE swipes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own swipes"
    ON swipes FOR ALL
    USING (auth.uid() = liker_id);

-- Matches visible to both parties
ALTER TABLE matches ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can see own matches"
    ON matches FOR SELECT
    USING (auth.uid() = user1_id OR auth.uid() = user2_id);

-- Discovery queue is private
ALTER TABLE discovery_queue ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can see own queue"
    ON discovery_queue FOR SELECT
    USING (auth.uid() = user_id);

-- Feedback is private
ALTER TABLE connection_feedback ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own feedback"
    ON connection_feedback FOR ALL
    USING (auth.uid() = user_id);
```

---

## 4. Scoring Algorithm

### 4.1 Multi-Signal Scoring Formula

```python
def calculate_match_score(viewer: User, candidate: User) -> MatchScore:
    """
    Calculate compatibility score between two users.
    
    Returns a score from 0.0 to 1.0 with breakdown.
    """
    
    # Weight configuration (tunable)
    WEIGHTS = {
        'preference_overlap': 0.25,      # Do they match each other's preferences?
        'behavioral_compatibility': 0.25, # Communication style match
        'effort_score': 0.20,             # Quality of their engagement
        'activity_freshness': 0.15,       # Are they active?
        'feedback_history': 0.10,         # Past success rate
        'exploration': 0.05,              # Serendipity factor
    }
    
    scores = {}
    
    # 1. Preference Overlap (0.0 - 1.0)
    # How well does candidate match viewer's preferences AND vice versa?
    scores['preference_overlap'] = calculate_preference_overlap(viewer, candidate)
    
    # 2. Behavioral Compatibility (0.0 - 1.0)
    # Do they communicate similarly?
    scores['behavioral_compatibility'] = calculate_behavioral_compatibility(
        viewer.user_scores,
        candidate.user_scores
    )
    
    # 3. Effort Score (0.0 - 1.0)
    # Does this person put effort into their profile and interactions?
    scores['effort_score'] = calculate_effort_score(candidate.user_scores)
    
    # 4. Activity Freshness (0.0 - 1.0)
    # Penalize dormant users, boost recently active
    scores['activity_freshness'] = calculate_freshness(candidate.last_active)
    
    # 5. Feedback History (0.0 - 1.0)
    # Based on "We Connected" feedback from their past matches
    scores['feedback_history'] = candidate.user_scores.positive_feedback_ratio
    
    # 6. Exploration Factor (0.0 - 1.0)
    # Random boost to ensure diversity (anti-echo-chamber)
    scores['exploration'] = random.uniform(0.3, 1.0)
    
    # Calculate weighted final score
    final_score = sum(
        scores[key] * WEIGHTS[key]
        for key in WEIGHTS
    )
    
    # Generate human-readable match reasons
    match_reasons = generate_match_reasons(viewer, candidate, scores)
    
    return MatchScore(
        final_score=final_score,
        breakdown=scores,
        reasons=match_reasons
    )
```

### 4.2 Preference Overlap Calculation

```python
def calculate_preference_overlap(viewer: User, candidate: User) -> float:
    """
    Bidirectional preference matching.
    Both users should match each other's preferences.
    """
    
    # Viewer's preferences vs Candidate's attributes
    viewer_to_candidate = 0.0
    viewer_to_candidate += match_age(viewer.prefs.min_age, viewer.prefs.max_age, candidate.age)
    viewer_to_candidate += match_distance(viewer.location, candidate.location, viewer.prefs.max_distance_km)
    viewer_to_candidate += match_gender(viewer.prefs.gender_preferences, candidate.gender)
    viewer_to_candidate += match_soft_prefs(viewer.prefs, candidate.attributes)
    viewer_to_candidate /= 4  # Normalize
    
    # Candidate's preferences vs Viewer's attributes
    candidate_to_viewer = 0.0
    candidate_to_viewer += match_age(candidate.prefs.min_age, candidate.prefs.max_age, viewer.age)
    candidate_to_viewer += match_distance(candidate.location, viewer.location, candidate.prefs.max_distance_km)
    candidate_to_viewer += match_gender(candidate.prefs.gender_preferences, viewer.gender)
    candidate_to_viewer += match_soft_prefs(candidate.prefs, viewer.attributes)
    candidate_to_viewer /= 4
    
    # Both directions must be satisfied (geometric mean)
    return math.sqrt(viewer_to_candidate * candidate_to_viewer)
```

### 4.3 Behavioral Compatibility

```python
def calculate_behavioral_compatibility(viewer_scores: UserScores, candidate_scores: UserScores) -> float:
    """
    Match users with similar communication patterns.
    Avoid matching high-effort users with ghosts.
    """
    
    # Response rate similarity
    response_diff = abs(viewer_scores.response_rate - candidate_scores.response_rate)
    response_similarity = 1.0 - response_diff
    
    # Response time compatibility
    # Fast responders might get frustrated with slow ones
    time_diff = abs(
        (viewer_scores.avg_response_time_hours or 12) - 
        (candidate_scores.avg_response_time_hours or 12)
    )
    time_similarity = max(0, 1.0 - (time_diff / 24))  # 24 hour diff = 0 similarity
    
    # Message quality similarity
    quality_diff = abs(viewer_scores.message_quality_score - candidate_scores.message_quality_score)
    quality_similarity = 1.0 - quality_diff
    
    # Weighted average
    return (
        0.4 * response_similarity +
        0.3 * time_similarity +
        0.3 * quality_similarity
    )
```

### 4.4 Effort Score

```python
def calculate_effort_score(user_scores: UserScores) -> float:
    """
    Reward users who put effort into the platform.
    """
    
    return (
        0.30 * user_scores.profile_completion +
        0.25 * user_scores.photo_quality_avg +
        0.25 * user_scores.comment_quality_avg +
        0.20 * user_scores.response_rate
    )
```

### 4.5 Activity Freshness

```python
def calculate_freshness(last_active: datetime) -> float:
    """
    Boost recently active users, penalize dormant ones.
    Uses exponential decay.
    """
    
    hours_since_active = (datetime.now(UTC) - last_active).total_seconds() / 3600
    
    # Exponential decay with 72-hour half-life
    half_life_hours = 72
    freshness = math.exp(-0.693 * hours_since_active / half_life_hours)
    
    return max(0.1, freshness)  # Floor at 0.1 to not completely hide inactive users
```

### 4.6 Match Reason Generation

```python
def generate_match_reasons(viewer: User, candidate: User, scores: Dict) -> List[str]:
    """
    Generate human-readable reasons for the match.
    Shown to users for transparency.
    """
    
    reasons = []
    
    # Distance
    distance_km = calculate_distance(viewer.location, candidate.location)
    if distance_km < 5:
        reasons.append(f"Lives nearby ({distance_km:.1f} km away)")
    elif distance_km < 20:
        reasons.append(f"{distance_km:.0f} km away")
    
    # Age
    age_diff = abs(viewer.age - candidate.age)
    if age_diff <= 2:
        reasons.append("Similar age")
    
    # Shared interests (from prompts/preferences)
    shared = find_shared_interests(viewer.prompts, candidate.prompts)
    for interest in shared[:2]:
        reasons.append(f"Both love {interest}")
    
    # High effort user
    if scores['effort_score'] > 0.7:
        reasons.append("Detailed profile")
    
    # Good track record
    if scores['feedback_history'] > 0.7:
        reasons.append("Great past connections")
    
    # High response rate
    if candidate.user_scores.response_rate > 0.8:
        reasons.append("Usually responds")
    
    return reasons[:4]  # Max 4 reasons
```

---

## 5. Discovery Service

### 5.1 API Endpoint

```python
# app/api/modules/v1/discovery/router.py

from fastapi import APIRouter, Depends, Query
from typing import List

router = APIRouter(prefix="/discovery", tags=["Discovery"])

@router.get("/profiles", response_model=DiscoveryResponse)
async def get_discovery_profiles(
    limit: int = Query(default=10, le=50),
    cursor: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get discovery profiles for the current user.
    
    Returns profiles sorted by match score with pagination.
    Each profile includes:
    - Basic info
    - Match score breakdown
    - Human-readable match reasons
    """
    
    # Check/refresh discovery queue
    queue = await discovery_service.get_or_refresh_queue(
        user_id=current_user.id,
        db=db
    )
    
    # Apply cursor pagination
    profiles = await discovery_service.get_paginated_profiles(
        queue=queue,
        cursor=cursor,
        limit=limit,
        db=db
    )
    
    # Mark as shown (for analytics)
    await discovery_service.mark_shown(
        user_id=current_user.id,
        profile_ids=[p.id for p in profiles],
        db=db
    )
    
    return DiscoveryResponse(
        profiles=profiles,
        next_cursor=profiles[-1].cursor if profiles else None,
        remaining_today=await get_remaining_likes(current_user.id)
    )
```

### 5.2 Discovery Service

```python
# app/api/modules/v1/discovery/service.py

class DiscoveryService:
    
    async def get_or_refresh_queue(
        self,
        user_id: UUID,
        db: AsyncSession,
    ) -> List[DiscoveryQueueItem]:
        """
        Get cached discovery queue or generate new one.
        Queue is refreshed when:
        - Less than 20 items remaining
        - Queue is older than 1 hour
        """
        
        # Check existing queue
        queue = await self.get_cached_queue(user_id, db)
        
        if len(queue) < 20 or self.is_stale(queue):
            # Generate new candidates
            new_candidates = await self.generate_candidates(user_id, db)
            queue = await self.merge_and_save_queue(user_id, queue, new_candidates, db)
        
        return queue
    
    async def generate_candidates(
        self,
        user_id: UUID,
        db: AsyncSession,
    ) -> List[DiscoveryQueueItem]:
        """
        Generate new candidate profiles using PostGIS.
        """
        
        user = await self.get_user_with_preferences(user_id, db)
        
        # Step 1: PostGIS filtering (hard filters)
        candidates = await db.execute(text("""
            SELECT 
                p.id,
                p.display_name,
                p.birthdate,
                p.gender,
                p.bio,
                p.prompts,
                p.location,
                ST_Distance(
                    p.location::geography,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                ) / 1000 as distance_km,
                us.response_rate,
                us.positive_feedback_ratio,
                us.profile_completion,
                us.last_active
            FROM profiles p
            LEFT JOIN user_scores us ON us.user_id = p.id
            LEFT JOIN user_preferences up ON up.user_id = p.id
            WHERE 
                -- Not self
                p.id != :user_id
                
                -- Not already swiped
                AND p.id NOT IN (
                    SELECT liked_id FROM swipes WHERE liker_id = :user_id
                )
                
                -- Not already matched
                AND p.id NOT IN (
                    SELECT user2_id FROM matches WHERE user1_id = :user_id
                    UNION
                    SELECT user1_id FROM matches WHERE user2_id = :user_id
                )
                
                -- Distance filter
                AND ST_DWithin(
                    p.location::geography,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                    :max_distance_m
                )
                
                -- Age filter
                AND EXTRACT(YEAR FROM AGE(p.birthdate)) BETWEEN :min_age AND :max_age
                
                -- Gender filter
                AND (:gender_filter = '{}' OR p.gender = ANY(:gender_filter))
                
                -- Profile completeness (minimum)
                AND COALESCE(us.profile_completion, 0) >= 0.3
                
                -- Not reported/banned
                AND COALESCE(us.report_count, 0) < 3
                
            ORDER BY us.last_active DESC NULLS LAST
            LIMIT 200
        """), {
            'user_id': user_id,
            'lng': user.location.x,
            'lat': user.location.y,
            'max_distance_m': user.preferences.max_distance_km * 1000,
            'min_age': user.preferences.min_age,
            'max_age': user.preferences.max_age,
            'gender_filter': user.preferences.gender_preferences or [],
        })
        
        candidate_rows = candidates.fetchall()
        
        # Step 2: Score each candidate
        scored_candidates = []
        for row in candidate_rows:
            candidate = CandidateProfile.from_row(row)
            score = calculate_match_score(user, candidate)
            
            scored_candidates.append(DiscoveryQueueItem(
                user_id=user_id,
                candidate_id=candidate.id,
                final_score=score.final_score,
                preference_overlap_score=score.breakdown['preference_overlap'],
                behavioral_compatibility_score=score.breakdown['behavioral_compatibility'],
                effort_score=score.breakdown['effort_score'],
                activity_freshness_score=score.breakdown['activity_freshness'],
                feedback_history_score=score.breakdown['feedback_history'],
                exploration_score=score.breakdown['exploration'],
                match_reasons=score.reasons,
            ))
        
        # Step 3: Sort by score with exploration factor
        # Top 70% by score, remaining 30% include exploration picks
        scored_candidates.sort(key=lambda x: x.final_score, reverse=True)
        
        top_candidates = scored_candidates[:70]
        exploration_pool = scored_candidates[70:150]
        random.shuffle(exploration_pool)
        exploration_picks = exploration_pool[:30]
        
        final_candidates = top_candidates + exploration_picks
        random.shuffle(final_candidates)  # Mix so exploration isn't obvious
        
        # Assign positions
        for i, c in enumerate(final_candidates):
            c.position = i
        
        return final_candidates
```

---

## 6. Swipe & Match Logic

### 6.1 Swipe Endpoint

```python
# app/api/modules/v1/discovery/router.py

@router.post("/swipe", response_model=SwipeResponse)
async def create_swipe(
    swipe: SwipeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Record a swipe action.
    
    For LIKE/SUPER_LIKE:
    - Comment is REQUIRED (min 10 characters)
    - Must specify which photo/prompt the comment is about
    
    Returns match info if mutual like detected.
    """
    
    # Validate comment requirement
    if swipe.direction in ['LIKE', 'SUPER_LIKE']:
        if not swipe.comment or len(swipe.comment) < 10:
            raise ValidationError(
                "Please include a thoughtful comment (at least 10 characters)",
                code="COMMENT_REQUIRED"
            )
    
    # Check daily like limit
    likes_today = await get_likes_today(current_user.id, db)
    if likes_today >= DAILY_LIKE_LIMIT and not current_user.is_premium:
        raise LimitExceededError("Daily like limit reached")
    
    # Create swipe record
    swipe_record = await discovery_service.create_swipe(
        liker_id=current_user.id,
        liked_id=swipe.profile_id,
        direction=swipe.direction,
        comment=swipe.comment,
        comment_target=swipe.comment_target,
        time_spent_viewing_ms=swipe.time_spent_viewing_ms,
        profile_scroll_depth=swipe.profile_scroll_depth,
        db=db,
    )
    
    # Check for mutual like
    match = None
    if swipe.direction in ['LIKE', 'SUPER_LIKE']:
        match = await discovery_service.check_and_create_match(
            user1_id=current_user.id,
            user2_id=swipe.profile_id,
            db=db,
        )
    
    return SwipeResponse(
        success=True,
        match=match,
        remaining_likes=DAILY_LIKE_LIMIT - likes_today - 1,
    )
```

### 6.2 Match Detection

```python
# app/api/modules/v1/discovery/service.py

async def check_and_create_match(
    self,
    user1_id: UUID,
    user2_id: UUID,
    db: AsyncSession,
) -> Match | None:
    """
    Check if there's a mutual like and create match.
    """
    
    # Check if other user has liked us
    reverse_swipe = await db.execute(
        select(Swipe)
        .where(Swipe.liker_id == user2_id)
        .where(Swipe.liked_id == user1_id)
        .where(Swipe.direction.in_(['LIKE', 'SUPER_LIKE']))
    )
    reverse_swipe = reverse_swipe.scalar_one_or_none()
    
    if not reverse_swipe:
        return None
    
    # Create match!
    match = Match(
        user1_id=min(user1_id, user2_id),  # Consistent ordering
        user2_id=max(user1_id, user2_id),
        matched_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=72),
        status='ACTIVE',
    )
    
    db.add(match)
    await db.commit()
    
    # Queue notifications
    await enqueue_match_notification(match.id)
    
    return match
```

---

## 7. Feedback Loop System

### 7.1 "We Connected" Request Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    FEEDBACK REQUEST TIMING                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Match Created ───► 3 days ───► First Prompt                    │
│        │                           │                             │
│        │                           ▼                             │
│        │              "How's it going with [Name]?"              │
│        │                           │                             │
│        │           ┌───────────────┼───────────────┐            │
│        │           ▼               ▼               ▼            │
│        │      "Great!"     "Still chatting"    "No reply"        │
│        │           │               │               │            │
│        │           ▼               ▼               ▼            │
│        │      Ask in 7 days   Ask in 3 days   Record ghost      │
│        │           │               │                             │
│        │           ▼               ▼                             │
│        │    ┌──────────────────────────────────────────┐        │
│        │    │  "Did you meet [Name] in person?"        │        │
│        │    │                                           │        │
│        │    │  [ ] Yes, in person                      │        │
│        │    │  [ ] Yes, video call                     │        │
│        │    │  [ ] No, but still chatting              │        │
│        │    │  [ ] No, lost interest                   │        │
│        │    └──────────────────────────────────────────┘        │
│        │                          │                              │
│        │               ┌──────────┴──────────┐                  │
│        │               ▼                     ▼                  │
│        │          If met:               If not met:             │
│        │    "Would you meet again?"   "What happened?"          │
│        │    "How was the connection?"                           │
│        │                                                         │
│        │                          │                              │
│        │                          ▼                              │
│        │           Store feedback, update user_scores            │
│        │                                                         │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Feedback Schema

```python
# app/api/modules/v1/feedback/schemas.py

class ConnectionFeedbackCreate(BaseModel):
    match_id: UUID
    
    # Core questions
    did_you_meet: bool
    meeting_type: Literal['VIDEO_CALL', 'IN_PERSON', 'STILL_CHATTING', 'NO_CONTACT']
    
    # If met
    would_meet_again: Optional[bool]
    connection_quality: Optional[int] = Field(ge=1, le=5)
    
    # What worked/didn't
    positive_factors: Optional[List[Literal[
        'great_conversation',
        'shared_interests', 
        'physical_attraction',
        'similar_values',
        'good_communication',
        'felt_safe',
        'fun_personality',
    ]]]
    
    negative_factors: Optional[List[Literal[
        'no_chemistry',
        'different_than_photos',
        'different_than_profile',
        'poor_communicator',
        'ghosted',
        'felt_unsafe',
        'incompatible_values',
        'no_shared_interests',
    ]]]
    
    # Optional free text
    notes: Optional[str] = Field(max_length=500)
```

### 7.3 Score Update from Feedback

```python
# app/workers/tasks/feedback_processing.py

async def process_connection_feedback(feedback_id: UUID):
    """
    Update user scores based on connection feedback.
    This is the "secret sauce" that trains our algorithm on real outcomes.
    """
    
    async with get_db_session() as db:
        feedback = await db.get(ConnectionFeedback, feedback_id)
        match = await db.get(Match, feedback.match_id)
        
        # Get the OTHER user in the match
        other_user_id = (
            match.user2_id if match.user1_id == feedback.user_id 
            else match.user1_id
        )
        
        other_scores = await db.get(UserScores, other_user_id)
        
        # Update their scores based on this feedback
        
        # 1. Did they lead to a meeting?
        if feedback.did_you_meet:
            other_scores.dates_from_matches_ratio = recalculate_ratio(
                current=other_scores.dates_from_matches_ratio,
                new_outcome=1.0,
                total_feedbacks=await count_feedbacks(other_user_id)
            )
        else:
            other_scores.dates_from_matches_ratio = recalculate_ratio(
                current=other_scores.dates_from_matches_ratio,
                new_outcome=0.0,
                total_feedbacks=await count_feedbacks(other_user_id)
            )
        
        # 2. Positive feedback ratio
        if feedback.connection_quality and feedback.connection_quality >= 4:
            outcome = 1.0
        elif feedback.connection_quality and feedback.connection_quality <= 2:
            outcome = 0.0
        else:
            outcome = 0.5
        
        other_scores.positive_feedback_ratio = recalculate_ratio(
            current=other_scores.positive_feedback_ratio,
            new_outcome=outcome,
            total_feedbacks=await count_feedbacks(other_user_id)
        )
        
        # 3. Ghost tracking
        if 'ghosted' in (feedback.negative_factors or []):
            other_scores.ghost_count += 1
        
        other_scores.updated_at = datetime.now(UTC)
        await db.commit()
        
        # Queue discovery queue refresh for affected users
        await enqueue_queue_refresh(other_user_id)
```

---

## 8. Anti-Ghost Mechanics

### 8.1 Match Expiration

```python
# app/workers/tasks/match_expiration.py

async def process_expiring_matches():
    """
    Run every hour to process matches approaching expiration.
    """
    
    async with get_db_session() as db:
        # Matches expiring in next 12 hours without first message
        expiring_matches = await db.execute(
            select(Match)
            .where(Match.status == 'ACTIVE')
            .where(Match.first_message_at.is_(None))
            .where(Match.expires_at <= datetime.now(UTC) + timedelta(hours=12))
        )
        
        for match in expiring_matches.scalars():
            # Send reminder notifications
            hours_remaining = (match.expires_at - datetime.now(UTC)).total_seconds() / 3600
            
            if hours_remaining <= 12 and not match.reminder_12h_sent:
                await send_expiration_reminder(match, hours=12)
                match.reminder_12h_sent = True
            
            if hours_remaining <= 0:
                # Match expired
                match.status = 'EXPIRED'
                
                # Update ghost count for both users
                await increment_ghost_count(match.user1_id)
                await increment_ghost_count(match.user2_id)
        
        await db.commit()
```

### 8.2 Response Rate Badge

```python
# In profile response

class ProfileResponse(BaseModel):
    # ... other fields
    
    response_badge: Optional[Literal[
        'VERY_RESPONSIVE',  # > 90% response rate
        'RESPONSIVE',        # > 70% response rate
        'SOMETIMES_RESPONDS', # > 40% response rate
        None                  # < 40% (no badge shown)
    ]]
    
    @staticmethod
    def calculate_badge(response_rate: float) -> Optional[str]:
        if response_rate >= 0.9:
            return 'VERY_RESPONSIVE'
        elif response_rate >= 0.7:
            return 'RESPONSIVE'
        elif response_rate >= 0.4:
            return 'SOMETIMES_RESPONDS'
        return None
```

---

## 9. API Specification

### 9.1 Discovery Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/discovery/profiles` | Get discovery profiles |
| POST | `/api/v1/discovery/swipe` | Record swipe action |
| GET | `/api/v1/discovery/stats` | Get user's discovery stats |

### 9.2 Matches Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/matches` | Get all matches |
| GET | `/api/v1/matches/{id}` | Get match details |
| DELETE | `/api/v1/matches/{id}` | Unmatch |

### 9.3 Feedback Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/feedback/pending` | Get matches needing feedback |
| POST | `/api/v1/feedback` | Submit connection feedback |
| GET | `/api/v1/feedback/{match_id}` | Get feedback for match |

### 9.4 Preferences Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/preferences` | Get user preferences |
| PUT | `/api/v1/preferences` | Update preferences |

---

## 10. Background Workers

### 10.1 Worker Tasks

| Task | Schedule | Purpose |
|------|----------|---------|
| `refresh_discovery_queues` | Every 1 hour | Refresh stale queues |
| `process_match_expirations` | Every 1 hour | Handle expiring matches |
| `request_feedback` | Every 6 hours | Send "We Connected" requests |
| `process_feedback` | On feedback submit | Update user scores |
| `recalculate_user_scores` | Every 24 hours | Full score recalculation |
| `cleanup_old_swipes` | Weekly | Archive old swipe data |

### 10.2 Worker Setup

```python
# app/workers/main.py

from arq import create_pool
from arq.connections import RedisSettings

async def startup(ctx):
    ctx['db'] = await create_db_pool()

async def shutdown(ctx):
    await ctx['db'].close()

class WorkerSettings:
    functions = [
        refresh_discovery_queues,
        process_match_expirations,
        request_feedback,
        process_feedback,
        recalculate_user_scores,
        cleanup_old_swipes,
    ]
    
    cron_jobs = [
        cron(refresh_discovery_queues, hour=None, minute=0),  # Every hour
        cron(process_match_expirations, hour=None, minute=30),  # Every hour
        cron(request_feedback, hour={0, 6, 12, 18}),  # 4x daily
        cron(recalculate_user_scores, hour=3),  # 3 AM daily
    ]
    
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
```

---

## 11. Frontend Components

### 11.1 Component Tree

```
src/components/features/discovery/
├── SwipeStack.tsx          # Main swipe interface
├── SwipeCard.tsx           # Individual profile card
├── ProfileDetail.tsx       # Expanded profile view
├── CommentModal.tsx        # Comment input for likes
├── ActionButtons.tsx       # Pass/Like/Super Like buttons
├── MatchModal.tsx          # "It's a Match!" celebration
├── MatchReasons.tsx        # "Why this match" display
└── DailyLimitBanner.tsx    # Like limit indicator

src/components/features/matches/
├── MatchList.tsx           # List of all matches
├── MatchCard.tsx           # Individual match card
├── ExpirationTimer.tsx     # Countdown to expiry
└── FeedbackPrompt.tsx      # "We Connected" modal

src/hooks/
├── useDiscovery.ts         # Discovery API + state
├── useSwipe.ts             # Swipe actions
├── useMatches.ts           # Match management
└── useFeedback.ts          # Feedback submission
```

### 11.2 Key UI Patterns

```tsx
// Comment Modal (Required for Likes)
const CommentModal: React.FC<Props> = ({ profile, onSubmit }) => {
  const [comment, setComment] = useState('');
  const [selectedTarget, setSelectedTarget] = useState<string | null>(null);
  
  const isValid = comment.length >= 10 && selectedTarget;
  
  return (
    <Modal>
      <h2>What caught your eye?</h2>
      <p>Select a photo or prompt to comment on:</p>
      
      <div className="targets">
        {profile.photos.map((photo, i) => (
          <PhotoTarget 
            key={i}
            selected={selectedTarget === `photo_${i}`}
            onClick={() => setSelectedTarget(`photo_${i}`)}
          />
        ))}
        {profile.prompts.map((prompt, i) => (
          <PromptTarget
            key={i}
            selected={selectedTarget === `prompt_${i}`}
            onClick={() => setSelectedTarget(`prompt_${i}`)}
          />
        ))}
      </div>
      
      <textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="Write something thoughtful..."
        minLength={10}
      />
      
      <p className="hint">
        Profiles with comments are 2x more likely to get a response!
      </p>
      
      <Button 
        disabled={!isValid}
        onClick={() => onSubmit({ comment, target: selectedTarget })}
      >
        Send Like
      </Button>
    </Modal>
  );
};
```

```tsx
// Match Reasons Display
const MatchReasons: React.FC<{ reasons: string[] }> = ({ reasons }) => (
  <div className="match-reasons">
    <span className="label">Why you might connect:</span>
    <ul>
      {reasons.map((reason, i) => (
        <li key={i}>
          <CheckIcon /> {reason}
        </li>
      ))}
    </ul>
  </div>
);
```

---

## 12. Performance & Scaling

### 12.1 Database Optimization

| Optimization | Implementation |
|--------------|----------------|
| Geospatial Index | GIST index on `profiles.location` |
| Discovery Queue | Pre-computed, cached for 1 hour |
| Connection Pooling | Supabase managed pooling |
| Partial Indexes | Active matches only |

### 12.2 Caching Strategy

```python
# Cache keys
CACHE_KEYS = {
    'discovery_queue': 'dq:{user_id}',  # TTL: 1 hour
    'user_scores': 'us:{user_id}',       # TTL: 24 hours
    'daily_likes': 'dl:{user_id}:{date}', # TTL: 24 hours
}
```

### 12.3 Load Estimates

| Metric | Estimate | Solution |
|--------|----------|----------|
| Discovery queries | 100/sec at 10K users | Pre-computed queues |
| Swipes | 500/sec at 10K users | Direct insert, async processing |
| Real-time matches | 50/sec | Supabase Realtime |

---

## 13. Privacy & Transparency

### 13.1 Algorithm Transparency

Users can see:
- Why they were matched (match reasons)
- Their response rate badge
- Their profile completion score

Users cannot see:
- Their internal ranking score
- Others' raw preference data
- Feedback others gave about them

### 13.2 Data Minimization

- Swipe history older than 90 days is archived
- Feedback details are aggregated, not stored individually
- Location is stored at ~1km precision, not exact

### 13.3 PIPEDA Compliance

- All PII access logged
- Data export available
- Deletion removes all personal data

---

## 14. Implementation Roadmap

### Phase 1: Core Discovery (Week 1-2)

- [ ] Database schema migrations
- [ ] Discovery service with PostGIS
- [ ] Basic scoring algorithm
- [ ] Swipe API endpoints
- [ ] Match detection

### Phase 2: Required Comments (Week 2-3)

- [ ] Comment validation
- [ ] Comment modal UI
- [ ] Comment target selection

### Phase 3: Feedback Loop (Week 3-4)

- [ ] Feedback schema
- [ ] "We Connected" prompt flow
- [ ] Score updates from feedback
- [ ] Background workers

### Phase 4: Anti-Ghost (Week 4-5)

- [ ] Match expiration logic
- [ ] Reminder notifications
- [ ] Response rate tracking
- [ ] Badges UI

### Phase 5: Polish & Optimization (Week 5-6)

- [ ] Discovery queue caching
- [ ] Match reasons UI
- [ ] Analytics dashboard
- [ ] Performance tuning

---

## Appendix A: Configuration

```python
# app/api/core/config.py

class MatchingConfig:
    # Limits
    DAILY_LIKE_LIMIT_FREE = 10
    DAILY_LIKE_LIMIT_PREMIUM = 50
    DAILY_SUPER_LIKE_LIMIT = 1
    
    # Timing
    MATCH_EXPIRY_HOURS = 72
    FEEDBACK_REQUEST_DELAY_DAYS = 3
    QUEUE_REFRESH_HOURS = 1
    
    # Scoring weights
    WEIGHT_PREFERENCE_OVERLAP = 0.25
    WEIGHT_BEHAVIORAL_COMPAT = 0.25
    WEIGHT_EFFORT = 0.20
    WEIGHT_FRESHNESS = 0.15
    WEIGHT_FEEDBACK_HISTORY = 0.10
    WEIGHT_EXPLORATION = 0.05
    
    # Thresholds
    MIN_PROFILE_COMPLETION = 0.3
    MIN_COMMENT_LENGTH = 10
    MAX_REPORTS_BEFORE_HIDE = 3
```

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| **Discovery Queue** | Pre-computed list of candidate profiles for a user |
| **Effort Score** | Measure of how much effort a user puts into the platform |
| **Feedback Loop** | System that uses real-world outcome data to improve matching |
| **Gale-Shapley** | Nobel Prize-winning stable matching algorithm |
| **Ghost Count** | Number of matches a user let expire without messaging |
| **Match Reasons** | Human-readable explanations for why two users were matched |
| **We Connected** | Post-date feedback prompt inspired by Hinge's "We Met" |

---

*This specification is a living document and will be updated as we learn from user behavior and feedback.*
