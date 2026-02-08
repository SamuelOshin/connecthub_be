# ConnectHub - Implementation Tasks (Supabase Hybrid)

> Master checklist for ConnectHub dating app using Supabase + FastAPI + Next.js

---

## Milestone 1: Foundation & Auth

### 1.1 Supabase Project Setup
- [x] Create Supabase project
- [x] Enable PostGIS extension
- [x] Configure Google OAuth provider
- [ ] Configure Apple OAuth provider
- [x] Set up storage bucket for photos
- [x] Configure RLS policies

### 1.2 Database Schema
- [x] Create `profiles` table (extends auth.users)
- [x] Create `photos` table
- [x] Create `swipes` table
- [x] Create `matches` table
- [x] Create `messages` table
- [x] Add GIST index for location column
- [x] Add indexes for swipes/messages
- [x] Enable Realtime for messages/matches

### 1.3 Backend Setup (FastAPI)
- [x] Update `pyproject.toml` with Supabase dependencies
- [x] Create `app/core/config.py` (settings)
- [x] Create `app/core/supabase.py` (client init)
- [x] Create `app/core/dependencies.py` (auth middleware)
- [x] Create `docker-compose.yml` (Redis for ARQ)
- [x] Update `main.py` with FastAPI app

### 1.4 Frontend Supabase Integration
- [x] Install `@supabase/supabase-js` and `@supabase/ssr`
- [x] Create `src/lib/supabase/client.ts`
- [x] Create `src/lib/supabase/server.ts`
- [x] Create `src/middleware.ts` (auth middleware)
- [x] Create `src/hooks/useAuth.ts`
- [x] Add environment variables

### 1.5 Auth Pages (Frontend)
- [x] Create `src/app/(auth)/login/page.tsx` (updated with Supabase)
- [x] Create `src/app/(auth)/sign-up/page.tsx` (updated with Supabase)
- [x] Create `src/app/(auth)/callback/route.ts`
- [x] Create `src/components/ui/social-button.tsx` (OAuth integration)
- [x] Create `src/components/features/auth/LoginForm.tsx`

✅ **Milestone 1 Complete!**


---

## Milestone 2: Profile & Photo Management

### 2.1 Profile API (FastAPI)
- [x] Create `app/api/modules/v1/profiles/schemas.py`
- [x] Create `app/api/modules/v1/profiles/service.py`
- [x] Create `app/api/modules/v1/profiles/router.py`
- [x] Implement `GET /api/v1/profiles/me`
- [x] Implement `PATCH /api/v1/profiles/me`
- [x] Implement `PUT /api/v1/profiles/me/location`
- [x] Implement `POST /api/v1/profiles/me/heartbeat`

### 2.2 Photo Management
- [x] Configure Supabase Storage bucket RLS
- [x] Create `app/api/modules/v1/photos/` (schemas, service, router)
- [x] Create `src/components/features/profile/PhotoUpload.tsx`
- [x] Implement photo reordering (drag-and-drop)
- [x] Implement photo upload via signed URLs
- [ ] Create media validation worker (TODO: NSFW deferred)

### 2.3 Profile Page (Frontend)
- [x] Create `src/app/(dashboard)/profile/page.tsx`
- [x] Create `src/components/features/profile/ProfileEditForm.tsx`
- [x] Create `src/lib/api.ts` (profile & photos API client)
- [x] Create `src/components/providers/QueryProvider.tsx`

### 2.4 Profile Hooks
- [x] Using TanStack Query (installed via npm)
- [x] Using inline queries in components

✅ **Milestone 2 Complete!**

---

## Milestone 3: Geospatial Match Engine

> Based on [matching_engine_spec.md](file:///c:/Users/PC/Documents/connecthub/connecthub_be/docs/matching_engine_spec.md)

### 3.1 Database Schema Extensions
- [ ] Create `user_preferences` table (hard/soft filters)
- [ ] Update `swipes` table (add comment requirement, analytics)
- [ ] Create `user_scores` table (behavioral scoring)
- [ ] Create `discovery_queue` table (pre-computed recommendations)
- [ ] Create `connection_feedback` table ("We Connected" data)
- [ ] Add indexes for discovery performance
- [ ] Add RLS policies for matching tables

### 3.2 Discovery Service (FastAPI)
- [ ] Create `app/api/modules/v1/discovery/schemas.py`
- [ ] Create `app/api/modules/v1/discovery/scoring.py` (6-component algorithm)
- [ ] Create `app/api/modules/v1/discovery/service.py`
- [ ] Create `app/api/modules/v1/discovery/router.py`
- [ ] Implement `GET /api/v1/discovery/profiles` (PostGIS + scoring)
- [ ] Implement `POST /api/v1/discovery/swipe` (with comment validation)
- [ ] Implement `GET /api/v1/discovery/stats`
- [ ] Implement bidirectional preference matching
- [ ] Implement match reason generation

### 3.3 Matches API (FastAPI)
- [ ] Create `app/api/modules/v1/matches/schemas.py`
- [ ] Create `app/api/modules/v1/matches/service.py`
- [ ] Create `app/api/modules/v1/matches/router.py`
- [ ] Implement `GET /api/v1/matches` (list active matches)
- [ ] Implement `GET /api/v1/matches/{id}` (match details + expiration)
- [ ] Implement `DELETE /api/v1/matches/{id}` (unmatch)
- [ ] Implement mutual like detection → match creation

### 3.4 Feedback System ("We Connected")
- [ ] Create `app/api/modules/v1/feedback/schemas.py`
- [ ] Create `app/api/modules/v1/feedback/service.py`
- [ ] Create `app/api/modules/v1/feedback/router.py`
- [ ] Implement `GET /api/v1/feedback/pending`
- [ ] Implement `POST /api/v1/feedback`
- [ ] Update user_scores from feedback outcomes

### 3.5 Background Workers (ARQ)
- [ ] Create `app/workers/settings.py`
- [ ] Create `app/workers/main.py`
- [ ] Create `app/workers/tasks/matching.py` (match expiration, ghost tracking)
- [ ] Create `app/workers/tasks/feedback.py` (score updates)
- [ ] Create `app/workers/tasks/discovery.py` (queue refresh)
- [ ] Schedule: hourly queue refresh, hourly expiration check, daily score recalc

### 3.6 Discovery UI (Frontend)
- [ ] Create `src/hooks/useDiscovery.ts`
- [ ] Create `src/components/features/discovery/SwipeStack.tsx`
- [ ] Create `src/components/features/discovery/SwipeCard.tsx`
- [ ] Create `src/components/features/discovery/CommentModal.tsx` ⭐ Key differentiator
- [ ] Create `src/components/features/discovery/ActionButtons.tsx`
- [ ] Create `src/components/features/discovery/MatchModal.tsx`
- [ ] Create `src/components/features/discovery/MatchReasons.tsx`
- [ ] Create `src/components/features/discovery/DailyLimitBanner.tsx`
- [ ] Create `src/app/(dashboard)/discover/page.tsx`

### 3.7 Matches UI (Frontend)
- [ ] Create `src/hooks/useMatches.ts`
- [ ] Create `src/components/features/matches/MatchList.tsx`
- [ ] Create `src/components/features/matches/MatchCard.tsx`
- [ ] Create `src/components/features/matches/ExpirationTimer.tsx`
- [ ] Create `src/components/features/matches/FeedbackPrompt.tsx`
- [ ] Create `src/app/(dashboard)/matches/page.tsx`

### 3.8 Preferences UI (Frontend)
- [ ] Create `src/hooks/usePreferences.ts`
- [ ] Create `src/components/features/preferences/PreferencesForm.tsx`
- [ ] Create `src/app/(dashboard)/preferences/page.tsx`

---

## Milestone 4: Real-Time Chat

### 4.1 Chat API (FastAPI)
- [ ] Create `app/api/v1/chat/schemas.py`
- [ ] Create `app/api/v1/chat/service.py`
- [ ] Create `app/api/v1/chat/router.py`
- [ ] Implement `GET /api/v1/chat/rooms`
- [ ] Implement `GET /api/v1/chat/rooms/{id}/messages`
- [ ] Implement `POST /api/v1/chat/rooms/{id}/messages`

### 4.2 Real-time Subscriptions (Frontend)
- [ ] Create `src/hooks/useRealtimeMessages.ts`
- [ ] Create `src/hooks/usePresence.ts`
- [ ] Set up Supabase Realtime channels

### 4.3 Chat UI (Frontend)
- [ ] Create `src/components/features/chat/ConversationList.tsx`
- [ ] Create `src/components/features/chat/ConversationItem.tsx`
- [ ] Create `src/components/features/chat/ChatRoom.tsx`
- [ ] Create `src/components/features/chat/MessageBubble.tsx`
- [ ] Create `src/components/features/chat/MessageInput.tsx`
- [ ] Create `src/components/features/chat/TypingIndicator.tsx`
- [ ] Create `src/app/(dashboard)/matches/page.tsx`
- [ ] Create `src/app/(dashboard)/chat/[matchId]/page.tsx`

---

## Milestone 5: Security & Compliance

### 5.1 Row Level Security
- [ ] RLS policy: Users can update own profile
- [ ] RLS policy: Users can view discoverable profiles
- [ ] RLS policy: Users can read own messages
- [ ] RLS policy: Users can access own photos

### 5.2 Audit & Privacy (FastAPI)
- [ ] Create `audit_logs` table
- [ ] Create `app/core/audit.py`
- [ ] Implement audit middleware
- [ ] Implement `GET /api/v1/privacy/export`
- [ ] Implement `DELETE /api/v1/privacy/account`

### 5.3 Settings UI (Frontend)
- [ ] Create `src/components/features/settings/AccountSettings.tsx`
- [ ] Create `src/components/features/settings/PrivacySettings.tsx`
- [ ] Create `src/app/(dashboard)/settings/page.tsx`

---

## Testing & Polish

### Backend Tests
- [ ] Discovery service tests
- [ ] Match detection tests
- [ ] PostGIS query tests

### Frontend Tests
- [ ] Component tests (Vitest)
- [ ] E2E tests (Playwright)

### Performance
- [ ] PostGIS query optimization (EXPLAIN ANALYZE)
- [ ] Image optimization (next/image)
- [ ] Bundle size audit

---

## Future Enhancements
- [ ] Push notifications (FCM/APNs)
- [ ] AI-based NSFW content scanning
- [ ] Premium subscription (Stripe)
- [ ] Report/Block functionality
- [ ] Super Likes
- [ ] Video chat
