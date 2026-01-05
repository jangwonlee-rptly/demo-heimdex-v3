# Heimdex Frontend Codebase Guide - People Feature Implementation

## Overview

This guide covers the Heimdex frontend architecture and patterns you need to follow when implementing the "People" feature. The frontend is a **Next.js 14** application with TypeScript, using **Tailwind CSS** for styling, **Supabase** for authentication, and follows specific conventions for API communication and component patterns.

---

## 1. Frontend Framework & Structure

### Framework Stack
- **Framework**: Next.js 14.2.35 (App Router, not Pages Router)
- **Language**: TypeScript 5.3
- **Styling**: Tailwind CSS 3.4 + custom CSS in `globals.css`
- **UI Components**: Custom component library (no external UI library)
- **State Management**: React hooks (useState, useEffect, useCallback)
- **HTTP Client**: Native `fetch` with auth token injection
- **Authentication**: Supabase JS SDK with JWT tokens

### Directory Structure
```
services/frontend/src/
├── app/                          # Next.js App Router pages
│   ├── layout.tsx               # Root layout with providers
│   ├── page.tsx                 # Landing page
│   ├── login/page.tsx
│   ├── dashboard/page.tsx
│   ├── upload/page.tsx
│   ├── search/page.tsx          # Main search interface
│   ├── videos/[id]/page.tsx     # Video detail page
│   ├── admin/
│   │   ├── page.tsx
│   │   └── users/[id]/page.tsx
│   ├── onboarding/page.tsx
│   └── globals.css              # Global styles & component classes
├── components/                   # Reusable React components
│   ├── VideoCard.tsx            # Video grid card component
│   ├── SearchWeightControls.tsx # Search weight adjustment UI
│   ├── SelectionTray.tsx        # Highlight reel selection UI
│   ├── HighlightJobStatus.tsx   # Job status display
│   ├── FileToggleBar.tsx        # Filter by video file
│   ├── GlobalNav.tsx            # Navigation header
│   ├── LanguageToggle.tsx       # Language selector
│   ├── ReprocessModal.tsx       # Reprocess dialog
│   ├── ExportShortModal.tsx     # Export options modal
│   ├── highlightReelUtils.ts    # Highlight reel logic
│   └── fileToggleUtils.ts       # File filtering logic
├── lib/                          # Utilities & configuration
│   ├── api-config.ts            # API versioning (v1)
│   ├── supabase.ts              # Auth & API request handler
│   └── i18n/                    # Internationalization
│       ├── index.ts
│       ├── context.tsx
│       ├── types.ts
│       └── translations.ts
└── types/                        # TypeScript interfaces
    └── index.ts                 # All type definitions
```

---

## 2. Existing API Client Patterns

### API Request Function
Location: `/Users/jangwonlee/Projects/demo-heimdex-v3/services/frontend/src/lib/supabase.ts`

**Key Pattern:**
```typescript
export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = await getAccessToken();
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const versionedEndpoint = apiEndpoint(endpoint);

  const response = await fetch(`${apiUrl}${versionedEndpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API request failed: ${response.statusText}`);
  }

  return response.json();
}
```

### Key Features
1. **Automatic Versioning**: All endpoints are automatically prefixed with `/v1` via `apiEndpoint()`
2. **Auth Token Injection**: Bearer token from Supabase session automatically added to headers
3. **Generic Type Support**: `apiRequest<T>` for type-safe responses
4. **Error Handling**: Catches API errors and throws with detail message

### Usage Examples
```typescript
// GET request
const profile = await apiRequest<UserProfile>('/me/profile');

// POST request with payload
const searchResults = await apiRequest<SearchResult>('/search', {
  method: 'POST',
  body: JSON.stringify({ query: 'test', limit: 20 })
});

// GET with specific ID
const video = await apiRequest<Video>(`/videos/${scene.video_id}`);

// DELETE request
await apiRequest(`/persons/${person_id}`, { method: 'DELETE' });
```

### Authentication Pattern
```typescript
// Get current user session
const { data: { session } } = await supabase.auth.getSession();
if (!session) {
  router.push('/login');
}

// Check auth in useEffect
useEffect(() => {
  const checkAuth = async () => {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) {
      router.push('/login');
    }
  };
  checkAuth();
}, [router]);
```

---

## 3. Search Page Location & Architecture

**Location**: `/Users/jangwonlee/Projects/demo-heimdex-v3/services/frontend/src/app/search/page.tsx`

### Features
- Natural language search query input
- Video file filtering (toggle bar)
- Search weight controls (transcript, visual, summary, lexical)
- Scene results with thumbnails and metadata
- Video player preview with scene timing
- Highlight reel selection (checkbox on each scene)
- Selection tray for building and exporting highlight reels

### Component Composition
The search page orchestrates:
- `SearchWeightControls` - Weight adjustment UI
- `FileToggleBar` - Video file filtering
- `SelectionTray` - Highlight reel management
- `HighlightJobStatus` - Job status polling

### Reference Implementation Pattern
Search page demonstrates:
- Form submission with validation
- API request with complex payload
- State management for search results, selections, UI toggles
- Memoization for derived data (`useMemo`)
- Real-time polling for async jobs
- Responsive two-column layout (results + player)

---

## 4. Routing Conventions

### Next.js App Router Structure
Heimdex uses **file-based routing** with the App Router:

**Route Files**:
```
app/
  search/page.tsx          → /search
  upload/page.tsx          → /upload
  dashboard/page.tsx       → /dashboard
  videos/[id]/page.tsx     → /videos/{id}
  admin/page.tsx           → /admin
  admin/users/[id]/page.tsx → /admin/users/{id}
  login/page.tsx           → /login
  onboarding/page.tsx      → /onboarding
  page.tsx                 → / (home)
```

### Navigation Pattern
```typescript
import { useRouter } from 'next/navigation';

const router = useRouter();

// Navigation
router.push('/search');
router.push(`/videos/${videoId}`);
```

### Active Route Detection
```typescript
import { usePathname } from 'next/navigation';

const pathname = usePathname();
const isSearch = pathname === '/search';
const isDashboard = pathname === '/dashboard';
```

### Protected Routes
Add auth check in page component:
```typescript
useEffect(() => {
  const checkAuth = async () => {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) router.push('/login');
  };
  checkAuth();
}, [router]);
```

---

## 5. UI Component Patterns

### Layout & Styling Architecture

#### Color Palette (Tailwind Theme)
Defined in `tailwind.config.js`:

**Surface Colors** (Dark theme):
- `surface-50` to `surface-950` (from light to dark)
- Default: `surface-950` (#050709) for background
- `surface-100` (#f1f5f9) for text
- `surface-700` (#1e293b) for cards
- `surface-800` (#0f172a) for input backgrounds

**Accent Colors**:
- `accent-cyan` (#06b6d4) - Primary accent
- `accent-violet` (#8b5cf6) - Secondary
- `accent-pink` (#ec4899) - Tertiary
- Used in gradients and highlights

#### Card Component
Location: `globals.css` - `.card` class

```tsx
<div className="card">
  <h2 className="text-lg font-semibold text-surface-100 mb-4">
    Title
  </h2>
  {/* content */}
</div>
```

**Styling**:
- Border radius: 2xl
- Padding: 6
- Gradient background
- Subtle border and shadow
- Hover effect on `.card-hover` variant

#### Button Variants
```tsx
// Primary button (cyan gradient)
<button className="btn btn-primary">
  Action
</button>

// Secondary button (subdued)
<button className="btn btn-secondary">
  Alternative
</button>

// Ghost button (transparent)
<button className="btn btn-ghost">
  Text only
</button>

// Gradient button (animated)
<button className="btn btn-gradient">
  Call to action
</button>

// Size variants
<button className="btn btn-sm">Small</button>
<button className="btn btn-lg">Large</button>
```

#### Status Badges
```tsx
// Status based on type
<span className="status-badge status-pending">PENDING</span>
<span className="status-badge status-processing">PROCESSING</span>
<span className="status-badge status-ready">READY</span>
<span className="status-badge status-failed">FAILED</span>

// Semantic badges
<span className="badge badge-success">Approved</span>
<span className="badge badge-warning">Warning</span>
<span className="badge badge-error">Error</span>
<span className="badge badge-accent">Featured</span>
```

#### Form Inputs
```tsx
// Text input
<input
  type="text"
  className="input"
  placeholder="Enter query"
  value={query}
  onChange={(e) => setQuery(e.target.value)}
/>

// Select dropdown
<select className="select">
  <option>Option 1</option>
</select>

// Label
<label className="label">Label text</label>
```

#### Empty States
```tsx
<div className="empty-state py-12">
  <div className="empty-state-icon">
    <svg>...</svg>
  </div>
  <p className="empty-state-title">No results found</p>
  <p className="empty-state-description">
    Try adjusting your search
  </p>
</div>
```

### Example Component: VideoCard
Location: `/Users/jangwonlee/Projects/demo-heimdex-v3/services/frontend/src/components/VideoCard.tsx`

**Key Patterns**:
1. **Props Interface**: Defines all component inputs with JSDoc
2. **Animations**: Staggered animation delay: `animationDelay: ${index * 0.05}s`
3. **Status-based Rendering**: Shows different buttons based on `video.status`
4. **Icon Usage**: Inline SVG icons (no icon library)
5. **Metadata Display**: Shows resolution, date, location, camera info
6. **Error Handling**: Displays error messages if present
7. **Action Handlers**: Callbacks for process, view, reprocess actions

**Structure**:
```tsx
export default function VideoCard({ 
  video, 
  onProcess, 
  onView, 
  onReprocess, 
  index = 0 
}: VideoCardProps) {
  const { t } = useLanguage(); // Translation hook
  
  return (
    <div className="video-card group" style={{ animationDelay }}>
      {/* Thumbnail Container */}
      {/* Status Overlay */}
      {/* Hover Overlay */}
      {/* Content Section */}
      {/* Metadata Row */}
      {/* EXIF Metadata */}
      {/* Error Message */}
      {/* Action Buttons */}
    </div>
  );
}
```

### Modal Patterns
Example: `ReprocessModal.tsx`

**Pattern**:
1. Modal state in parent component
2. Conditional rendering based on `isOpen`
3. Overlay (backdrop) with click handler
4. Form for user input
5. Action buttons (confirm/cancel)
6. Close animation on state change

```tsx
{reprocessModal.isOpen && (
  <div className="modal-overlay" onClick={closeModal}>
    <div className="modal-content" onClick={(e) => e.stopPropagation()}>
      <h2>Modal Title</h2>
      {/* Form inputs */}
      <div className="flex gap-3">
        <button onClick={handleConfirm}>Confirm</button>
        <button onClick={closeModal}>Cancel</button>
      </div>
    </div>
  </div>
)}
```

### Grid/List Patterns
```tsx
// Grid layout for cards
<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
  {items.map((item) => (
    <Card key={item.id} item={item} />
  ))}
</div>

// List with hover state
<div className="space-y-3">
  {items.map((item) => (
    <button
      key={item.id}
      className={`scene-card w-full text-left ${
        selectedItem?.id === item.id ? 'active' : ''
      }`}
      onClick={() => handleSelect(item)}
    >
      {/* Content */}
    </button>
  ))}
</div>
```

### Dark Theme Implementation
- All pages have `'use client'` directive (client component)
- Root `<html>` has `className="dark"` 
- CSS variables in `:root` for colors
- Tailwind extends with custom color palette
- No light mode (cinematic dark-only design)

### Animation Classes
Custom animations in `tailwind.config.js`:
- `animate-slide-up` / `animate-slide-down` / `animate-slide-in-right`
- `animate-fade-in` / `animate-scale-in`
- `animate-pulse-glow` - Glowing effect
- `animate-gradient-shift` - Gradient animation
- `animate-spin-slow` - Slow rotation

---

## 6. Docker Setup

### Frontend Dockerfile
Location: `/Users/jangwonlee/Projects/demo-heimdex-v3/services/frontend/Dockerfile`

**Multi-stage build**:
1. **Dependencies stage**: `node:20-alpine` - Install dependencies
2. **Builder stage**: Build Next.js app with build args for environment variables
3. **Runner stage**: Production image with optimized output

**Build Args** (from `docker-compose.yml`):
```dockerfile
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ARG NEXT_PUBLIC_API_URL
```

**Environment Variables**:
```dockerfile
ENV NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL
ENV NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NODE_ENV=production
ENV PORT=3000
```

### Docker Compose Configuration
Location: `/Users/jangwonlee/Projects/demo-heimdex-v3/docker-compose.yml`

**Frontend Service**:
```yaml
frontend:
  build:
    context: ./services/frontend
    dockerfile: Dockerfile
    args:
      NEXT_PUBLIC_SUPABASE_URL: ${SUPABASE_URL}
      NEXT_PUBLIC_SUPABASE_ANON_KEY: ${SUPABASE_ANON_KEY}
      NEXT_PUBLIC_API_URL: http://localhost:8000
  ports:
    - "3000:3000"
  environment:
    NEXT_PUBLIC_SUPABASE_URL: ${SUPABASE_URL}
    NEXT_PUBLIC_SUPABASE_ANON_KEY: ${SUPABASE_ANON_KEY}
    NEXT_PUBLIC_API_URL: http://localhost:8000
  depends_on:
    - api
```

### Development
```bash
# Install dependencies
npm install

# Dev server (hot reload)
npm run dev

# Build for production
npm run build

# Run production build locally
npm run start
```

---

## 7. Internationalization Pattern

Location: `/Users/jangwonlee/Projects/demo-heimdex-v3/services/frontend/src/lib/i18n/`

**Hook Usage**:
```typescript
import { useLanguage } from '@/lib/i18n';

export default function MyComponent() {
  const { t } = useLanguage();
  
  return (
    <h1>{t.search.title}</h1>
    <p>{t.search.subtitle}</p>
  );
}
```

**Translation Structure**:
```typescript
const translations = {
  common: { signIn: '...', signOut: '...' },
  nav: { dashboard: '...', upload: '...', search: '...' },
  search: { title: '...', results: '...' },
  // ... more sections
};
```

---

## 8. Backend API Patterns for People Feature

### Existing People Routes
Location: `/Users/jangwonlee/Projects/demo-heimdex-v3/services/api/src/routes/persons.py`

**API Endpoints**:
```
POST   /v1/persons                              # Create person
GET    /v1/persons                              # List persons
GET    /v1/persons/{person_id}                  # Get person details
POST   /v1/persons/{person_id}/photos/upload-url
GET    /v1/persons/{person_id}/photos/{photo_id}/complete
DELETE /v1/persons/{person_id}                  # Delete person
```

### API Response Types
From backend schemas:

**PersonResponse**:
```typescript
{
  id: string (UUID);
  display_name: string | null;
  status: "active" | "archived";
  ready_photos_count: number;
  total_photos_count: number;
  has_query_embedding: boolean;
  created_at: string;
  updated_at: string;
}
```

**PersonListResponse**:
```typescript
{
  persons: PersonResponse[];
}
```

**PersonDetailResponse**:
```typescript
{
  person: PersonResponse;
  photos: PersonPhotoResponse[];
}
```

**PersonPhotoResponse**:
```typescript
{
  id: string (UUID);
  person_id: string (UUID);
  storage_path: string;
  state: "UPLOADED" | "PROCESSING" | "READY" | "FAILED";
  quality_score: number | null;
  error_message: string | null;
  created_at: string;
}
```

---

## 9. Key Conventions to Follow

### Component Structure
1. Use `'use client'` directive at top of client components
2. Import hooks and dependencies at top
3. Define interfaces for props
4. Export default function as component
5. Add JSDoc comments for public APIs

### State Management
1. Use `useState` for local state
2. Use `useEffect` for side effects (auth checks, data loading)
3. Use `useCallback` for event handlers (especially in lists)
4. Use `useMemo` for expensive derived data
5. Keep state as close to where it's needed as possible

### Type Safety
1. Define explicit types for all props: `interface ComponentProps { ... }`
2. Use generic types for API responses: `apiRequest<T>(...)`
3. Import types from `@/types` for domain models
4. Don't use `any` type

### Error Handling
1. Show user-friendly error messages
2. Log full errors to console in development
3. Use try-catch for async operations
4. Show validation errors inline in forms

### Authentication
1. Always check session in useEffect on protected pages
2. Use `supabase.auth.getSession()` to check auth
3. Redirect to `/login` if not authenticated
4. Token is automatically injected by `apiRequest()`

### CSS & Styling
1. Use Tailwind utility classes primarily
2. Use custom `.card`, `.btn`, `.badge` classes for consistency
3. Use `surface-*` colors for backgrounds/text
4. Use `accent-*` colors for highlights
5. Use pre-defined animations: `animate-*`
6. Keep dark theme consistent (no light mode)

---

## 10. Example: Implementing a People Page

### Directory Structure You'll Create
```
src/
  app/
    people/
      page.tsx                    # Main people management page
      [id]/page.tsx              # Person detail page
  components/
    PersonCard.tsx               # List card for person
    PersonPhotoUpload.tsx        # Photo upload component
    PersonPhotoGrid.tsx          # Grid of reference photos
    PersonModal.tsx              # Create/edit person dialog
  types/
    people.ts                    # Types export (or extend index.ts)
```

### Pattern for People Page
```typescript
'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { supabase, apiRequest } from '@/lib/supabase';
import { useLanguage } from '@/lib/i18n';

interface PersonWithPhotos extends PersonResponse {
  photos: PersonPhotoResponse[];
}

export default function PeoplePage() {
  const { t } = useLanguage();
  const router = useRouter();
  const [persons, setPersons] = useState<PersonResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const init = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        router.push('/login');
        return;
      }

      try {
        const result = await apiRequest<PersonListResponse>('/persons');
        setPersons(result.persons);
      } catch (error) {
        console.error('Failed to load persons:', error);
      } finally {
        setLoading(false);
      }
    };

    init();
  }, [router]);

  return (
    <div className="min-h-screen bg-surface-950 pt-20 pb-12">
      <div className="relative max-w-7xl mx-auto px-4">
        {/* Header with title and create button */}
        <div className="card mb-6">
          <div className="flex justify-between items-center">
            <h1 className="text-2xl font-bold text-surface-100">
              People
            </h1>
            <button className="btn btn-primary">
              Add Person
            </button>
          </div>
        </div>

        {/* People Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {persons.map((person) => (
            <PersonCard 
              key={person.id} 
              person={person}
              onView={() => router.push(`/people/${person.id}`)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
```

---

## Summary

**To implement the People feature, follow these patterns:**

1. **Use the existing `apiRequest()` function** - it handles auth and versioning
2. **Create TypeScript interfaces** for all API responses
3. **Add navigation link** to GlobalNav component
4. **Use Tailwind + custom classes** for styling (follow dark theme)
5. **Handle auth** with session checks in useEffect
6. **Use React hooks** for state (no Redux or other managers)
7. **Reuse component patterns** (cards, buttons, modals, grids)
8. **Add translations** to i18n for all UI text
9. **Follow the file structure** (routes in app/, components in components/)
10. **Keep components as client components** with `'use client'` at the top

The existing codebase is very consistent in its patterns - study the Search page and VideoCard component for reference implementations.

