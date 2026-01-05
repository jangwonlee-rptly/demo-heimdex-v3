# Ground Truth UI & Design Specification
## Heimdex Demo Application (demo.heimdex.co)

**Document Purpose**: This document extracts the actual design system, UI patterns, colors, typography, and copy from the Heimdex demo codebase. All claims are evidence-based and cite source code.

---

## 0. Repo Snapshot

### Commit Hash
```
ea6a52c55ed7cef50450583b4da6144f13f4b053
```

### Tech Stack
- **Framework**: Next.js 14.2.35 (App Router, React 18.2.0)
- **Styling**: Tailwind CSS 3.4.0 with extensive custom configuration
- **UI Components**: Custom component library (no external UI framework like shadcn, Radix, MUI detected)
- **Icons**: Inline SVG icons (no icon library like Lucide or Heroicons)
- **Fonts**: Google Fonts via CDN
  - Display/Body: Outfit (weights 300-800)
  - Monospace: JetBrains Mono (weights 400-600)
- **Backend Client**: Supabase JS 2.38.4
- **Language**: TypeScript 5.3.0

**Evidence**: `services/frontend/package.json:11-25`, `services/frontend/src/app/globals.css:1`

### Rendering Model
- **Router**: Next.js 14 App Router (file-based routing in `src/app/`)
- **Client-side rendering**: All pages marked `'use client'` with dynamic rendering (`export const dynamic = 'force-dynamic'`)
- **No server components**: All pages are client components with client-side data fetching
- **Auth gates**: Client-side session checks redirect unauthenticated users

**Evidence**: `services/frontend/src/app/page.tsx:1,15`, `services/frontend/src/app/dashboard/page.tsx:1,19`

### Theming Mechanism
- **CSS Variables**: Defined in `:root` for colors, gradients, shadows
- **Tailwind Extension**: Custom colors, fonts, animations, keyframes
- **Dark Mode**: Hardcoded dark theme (no light mode detected)
  - HTML element has `className="dark"` attribute
  - All color tokens are dark theme values
- **No theme provider component**: Theme is static, applied via CSS variables

**Evidence**:
```css
/* services/frontend/src/app/globals.css:7-38 */
:root {
  --font-display: 'Outfit', system-ui, sans-serif;
  --color-bg-primary: #050709;
  --color-accent-cyan: #06b6d4;
  /* ... */
}
```
```tsx
/* services/frontend/src/app/layout.tsx:30 */
<html lang="en" className="dark">
```

### i18n Mechanism
- **Languages**: English (en), Korean (ko)
- **Implementation**: Custom React Context provider
- **Translation files**: `services/frontend/src/lib/i18n/translations.ts`
- **Type-safe**: TypeScript interfaces for all translation keys
- **Usage**: `const { t } = useLanguage()` hook provides translations
- **Structure**: Nested objects organized by feature area (nav, common, landing, dashboard, search, etc.)

**Evidence**:
```tsx
/* services/frontend/src/lib/i18n/types.ts:1 */
export type Language = 'en' | 'ko';

/* services/frontend/src/app/layout.tsx:10,36 */
import { LanguageProvider } from '@/lib/i18n';
<LanguageProvider>
```

---

## 1. Design Philosophy (Evidence-Based)

### Spacing Rhythm

**Observed Pattern**: Consistent use of Tailwind spacing scale with emphasis on 4px increments (gap-2, gap-3, gap-4, gap-6, gap-8, py-12, py-16, py-24)

**Evidence**:
```css
/* services/frontend/src/app/globals.css:114 */
.card {
  @apply rounded-2xl p-6;
}

/* services/frontend/src/app/page.tsx:64,129,200 */
<section className="relative pt-32 pb-24 px-4 sm:px-6 lg:px-8">
<section className="relative py-24 px-4 sm:px-6 lg:px-8">
```

**Implication**: The design follows an 8px base unit (2 * 4px) for major spacing, with occasional 4px adjustments for fine-tuning. This creates visual rhythm and predictable layout spacing.

---

### Layout Patterns

**Observed Pattern**: Consistent max-width containers (max-w-7xl, max-w-5xl, max-w-4xl) with responsive padding

**Evidence**:
```css
/* services/frontend/src/app/globals.css:303-305 */
.section-container {
  @apply max-w-7xl mx-auto px-4 sm:px-6 lg:px-8;
}

/* services/frontend/src/app/page.tsx:65,130,201 */
<div className="max-w-5xl mx-auto text-center">
<div className="max-w-7xl mx-auto">
```

**Implication**: The design uses a constrained-width layout with centered content. Widths vary by section importance (5xl for hero, 7xl for feature grids). Responsive padding increases with viewport size (4px → 6px → 8px).

---

### Interaction Style

**Observed Pattern**: Smooth transitions with hover state elevation and glow effects

**Evidence**:
```css
/* services/frontend/src/app/globals.css:121-128 */
.card-hover {
  @apply transition-all duration-300;
}
.card-hover:hover {
  border-color: rgba(6, 182, 212, 0.3);
  box-shadow: 0 8px 32px -4px rgba(0, 0, 0, 0.4), 0 0 20px -5px rgba(6, 182, 212, 0.2);
  transform: translateY(-2px);
}

/* services/frontend/src/app/globals.css:142-145 */
.btn-primary:hover {
  box-shadow: 0 6px 20px -2px rgba(6, 182, 212, 0.5);
  transform: translateY(-1px);
}
```

**Implication**: Hover interactions use subtle vertical translation (-1px to -2px) combined with enhanced shadows and cyan glow effects. All transitions use 300ms duration for consistency.

---

### Micro-interactions

**Observed Pattern**: Custom animations for page entry, loading states, and emphasis

**Evidence**:
```js
/* services/frontend/tailwind.config.js:76-129 */
keyframes: {
  shimmer: { '0%': { transform: 'translateX(-100%)' }, '100%': { transform: 'translateX(100%)' } },
  'slide-up': { '0%': { transform: 'translateY(10px)', opacity: '0' }, '100%': { transform: 'translateY(0)', opacity: '1' } },
  'pulse-glow': { '0%, 100%': { boxShadow: '0 0 20px -5px rgba(6, 182, 212, 0.4)' }, '50%': { boxShadow: '0 0 30px -5px rgba(6, 182, 212, 0.6)' } },
  float: { '0%, 100%': { transform: 'translateY(0px)' }, '50%': { transform: 'translateY(-10px)' } }
}

/* services/frontend/src/app/page.tsx:76-77 */
<h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold mb-6 tracking-tight animate-slide-up">
```

**Implication**: The design uses entrance animations (slide-up, fade-in, scale-in) with staggered delays for visual hierarchy. Floating orbs and pulsing elements create ambient motion without being distracting.

---

### Accessibility Patterns

**Observed Pattern**: Focus-visible outlines with cyan accent, semantic HTML, ARIA-friendly structure

**Evidence**:
```css
/* services/frontend/src/app/globals.css:86-89 */
:focus-visible {
  outline: 2px solid var(--color-accent-cyan);
  outline-offset: 2px;
}

/* services/frontend/src/app/globals.css:80-83 */
::selection {
  background: rgba(6, 182, 212, 0.3);
  color: var(--color-text-primary);
}
```

**Implication**: Focus states are clearly visible with cyan accent matching the brand color. Text selection uses the same color for consistency. All interactive elements are semantic buttons/links (no div onClick).

---

### Responsiveness Approach

**Observed Pattern**: Mobile-first with breakpoint-specific adjustments (sm:, md:, lg:)

**Evidence**:
```css
/* services/frontend/src/app/globals.css:522-532 */
.video-card-grid {
  @apply grid gap-5;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
}
@media (min-width: 640px) {
  .video-card-grid {
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  }
}
@media (min-width: 1024px) {
  .video-card-grid {
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  }
}

/* services/frontend/src/app/page.tsx:88 */
<div className="flex flex-col sm:flex-row gap-4 justify-center animate-slide-up">
```

**Implication**: The design uses responsive grids with auto-fill for flexible layouts. Padding and font sizes scale up at breakpoints. Layouts switch from vertical stacking to horizontal flexbox/grid at sm (640px).

---

## 2. Color System

### Primary Colors

**Token**: `accent-cyan` (primary brand color)
- **Value**: `#06b6d4` (cyan-500 equivalent)
- **Usage**: Primary buttons, links, focus states, gradient start
- **Components**: `.btn-primary`, `.nav-link.active::after`, focus outlines, logo icon
- **Example**:
```css
/* services/frontend/tailwind.config.js:27 */
accent: { cyan: '#06b6d4' }

/* services/frontend/src/app/globals.css:137-138 */
.btn-primary {
  background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);
}
```

---

**Token**: `accent-violet` (secondary brand color)
- **Value**: `#8b5cf6` (violet-500 equivalent)
- **Usage**: Gradient middle, feature icons, accent elements
- **Components**: Feature cards, gradient text, decorative orbs
- **Example**:
```css
/* services/frontend/tailwind.config.js:29 */
accent: { violet: '#8b5cf6' }

/* services/frontend/src/app/globals.css:294 */
.gradient-text {
  background-image: linear-gradient(135deg, #06b6d4 0%, #8b5cf6 50%, #ec4899 100%);
}
```

---

**Token**: `accent-pink` (tertiary brand color)
- **Value**: `#ec4899` (pink-500 equivalent)
- **Usage**: Gradient end, accent highlights
- **Components**: Gradient text, decorative elements, feature cards
- **Example**:
```css
/* services/frontend/tailwind.config.js:31 */
accent: { pink: '#ec4899' }
```

---

### Background Colors

**Token**: `surface-950` (primary background)
- **Value**: `#050709` (near-black)
- **Usage**: Page backgrounds, base layer
- **Components**: `body`, page containers
- **Example**:
```css
/* services/frontend/src/app/globals.css:14 */
--color-bg-primary: #050709;

/* services/frontend/src/app/layout.tsx:35 */
<body className="font-body antialiased bg-surface-950 text-surface-100">
```

---

**Token**: `surface-900` (secondary background)
- **Value**: `#0a0f1a` (dark slate)
- **Usage**: Navigation bar, elevated surfaces
- **Components**: GlobalNav, card backgrounds
- **Example**:
```css
/* services/frontend/src/app/globals.css:15 */
--color-bg-secondary: #0a0f1a;

/* services/frontend/src/components/GlobalNav.tsx:64 */
className="bg-surface-900/80 backdrop-blur-xl"
```

---

**Token**: `surface-800` (tertiary background)
- **Value**: `#0f172a` (slate-900 equivalent)
- **Usage**: Input backgrounds, dropdown backgrounds
- **Components**: `.input`, `.select`, card inner backgrounds
- **Example**:
```css
/* services/frontend/tailwind.config.js:22 */
surface: { 800: '#0f172a' }
```

---

**Token**: `surface-700` (elevated surface)
- **Value**: `#1e293b` (slate-800 equivalent)
- **Usage**: Hover states, borders, secondary buttons
- **Components**: `.btn-secondary`, `.nav-link:hover`
- **Example**:
```css
/* services/frontend/tailwind.config.js:20 */
surface: { 700: '#1e293b' }
```

---

### Text Colors

**Token**: `surface-100` (primary text)
- **Value**: `#f1f5f9` (near-white)
- **Usage**: Headings, body text, primary labels
- **Components**: All text content
- **Example**:
```css
/* services/frontend/src/app/globals.css:19 */
--color-text-primary: #f1f5f9;
```

---

**Token**: `surface-400` (secondary text)
- **Value**: `#94a3b8` (slate-400)
- **Usage**: Descriptions, subtitles, metadata
- **Components**: Hero subtitle, feature descriptions
- **Example**:
```css
/* services/frontend/src/app/globals.css:20 */
--color-text-secondary: #94a3b8;
```

---

**Token**: `surface-500` (muted text)
- **Value**: `#64748b` (slate-500)
- **Usage**: Placeholders, disabled text, captions
- **Components**: Input placeholders, stat labels
- **Example**:
```css
/* services/frontend/src/app/globals.css:21 */
--color-text-muted: #64748b;
```

---

### Semantic Colors

**Status Success**
- **Token**: `status.success` / `emerald-400`
- **Value**: `#10b981` (emerald-500)
- **Usage**: Ready status badges, success toasts
- **Example**:
```css
/* services/frontend/tailwind.config.js:48 */
status: { success: '#10b981' }

/* services/frontend/src/app/globals.css:243-244 */
.badge-success {
  @apply bg-emerald-500/20 text-emerald-400 border-emerald-500/30;
}
```

---

**Status Warning**
- **Token**: `status.warning` / `amber-400`
- **Value**: `#f59e0b` (amber-500)
- **Usage**: Pending/processing status badges, warning toasts
- **Example**:
```css
/* services/frontend/tailwind.config.js:49 */
status: { warning: '#f59e0b' }
```

---

**Status Error**
- **Token**: `status.error` / `red-400`
- **Value**: `#ef4444` (red-500)
- **Usage**: Failed status badges, error toasts
- **Example**:
```css
/* services/frontend/tailwind.config.js:50 */
status: { error: '#ef4444' }
```

---

**Status Info**
- **Token**: `status.info` / `blue-400`
- **Value**: `#3b82f6` (blue-500)
- **Usage**: Processing status badges, info toasts
- **Example**:
```css
/* services/frontend/tailwind.config.js:51 */
status: { info: '#3b82f6' }
```

---

### Border Colors

**Token**: `rgba(148, 163, 184, 0.1)` (default border)
- **Value**: `surface-400` at 10% opacity
- **Usage**: Card borders, dividers, default borders
- **Example**:
```css
/* services/frontend/src/app/globals.css:27 */
--color-border: rgba(148, 163, 184, 0.1);

/* services/frontend/src/app/globals.css:99 */
border: 1px solid rgba(148, 163, 184, 0.1);
```

---

### Gradients

**Brand Gradient** (cyan → violet → pink)
- **Definition**: `linear-gradient(135deg, #06b6d4 0%, #8b5cf6 50%, #ec4899 100%)`
- **Usage**: Gradient text, gradient buttons, feature card borders
- **Example**:
```css
/* services/frontend/src/app/globals.css:31 */
--gradient-brand: linear-gradient(135deg, #06b6d4 0%, #8b5cf6 50%, #ec4899 100%);

/* services/frontend/src/app/globals.css:174-176 */
.btn-gradient {
  background: linear-gradient(135deg, #06b6d4 0%, #8b5cf6 50%, #ec4899 100%);
  background-size: 200% 200%;
}
```

---

**Card Gradient** (dark surface with transparency)
- **Definition**: `linear-gradient(145deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.95) 100%)`
- **Usage**: Card backgrounds, elevated surfaces
- **Example**:
```css
/* services/frontend/src/app/globals.css:115 */
background: linear-gradient(145deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.95) 100%);
```

---

### Dark Mode

**Is there dark mode?** Yes, but only dark mode exists (no light mode toggle).

**How is it enabled?** The `<html>` element has `className="dark"` hardcoded. All color values are dark theme values with no light theme alternatives.

**What changes?** Nothing changes—the entire application is dark theme only.

**Evidence**:
```tsx
/* services/frontend/src/app/layout.tsx:30 */
<html lang="en" className="dark">
```

---

## 3. Typography System

### Font Families

**Display/Body Font**: Outfit
- **Source**: Google Fonts CDN
- **Weights**: 300 (Light), 400 (Regular), 500 (Medium), 600 (Semi-bold), 700 (Bold), 800 (Extra-bold)
- **Fallback**: `system-ui, sans-serif`
- **Loading**: `@import` in globals.css
- **Evidence**:
```css
/* services/frontend/src/app/globals.css:1 */
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');

/* services/frontend/tailwind.config.js:55 */
fontFamily: {
  display: ['var(--font-display)', 'system-ui', 'sans-serif'],
  body: ['var(--font-body)', 'system-ui', 'sans-serif'],
}
```

---

**Monospace Font**: JetBrains Mono
- **Source**: Google Fonts CDN
- **Weights**: 400 (Regular), 500 (Medium), 600 (Semi-bold)
- **Fallback**: `monospace`
- **Evidence**:
```css
/* services/frontend/src/app/globals.css:1 */
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&display=swap');

/* services/frontend/tailwind.config.js:57 */
fontFamily: {
  mono: ['var(--font-mono)', 'monospace'],
}
```

---

### Type Scale

| Role | Classes | Font Weight | Line Height | Example Usage | Evidence |
|------|---------|-------------|-------------|---------------|----------|
| Hero Heading (H1) | `text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight` | 700 | Default | Page hero titles | `services/frontend/src/app/page.tsx:76` |
| Section Heading (H2) | `text-3xl sm:text-4xl font-bold` | 700 | Default | Section titles | `services/frontend/src/app/page.tsx:132` |
| Card Heading (H3) | `text-xl font-semibold` | 600 | Default | Feature card titles | `services/frontend/src/app/page.tsx:152` |
| Body Large | `text-xl sm:text-2xl leading-relaxed` | 400 | 1.625 | Hero subtitle | `services/frontend/src/app/page.tsx:83` |
| Body Regular | `text-base` (default) | 400 | 1.5 | Paragraph text | Global default |
| Body Small | `text-sm` | 400-500 | Default | Metadata, captions | `services/frontend/src/components/VideoCard.tsx:619` |
| Stat Value | `text-3xl font-bold` | 700 | Default | Dashboard stats, landing stats | `services/frontend/src/app/page.tsx:113` |
| Badge/Label | `text-xs font-medium uppercase tracking-wide` | 500 | Default | Status badges | `services/frontend/src/app/globals.css:272` |

---

### Font Weight Usage

- **300 (Light)**: Not actively used in components
- **400 (Regular)**: Default body text, descriptions
- **500 (Medium)**: Labels, buttons, emphasized body text
- **600 (Semi-bold)**: Card headings, sub-headings
- **700 (Bold)**: Page headings, section titles
- **800 (Extra-bold)**: Not actively used in components

**Evidence**: Weights inferred from class usage across page components and button definitions.

---

### Line Height Patterns

- **Default**: Tailwind default (1.5 for body, 1.2 for headings)
- **Relaxed**: `leading-relaxed` (1.625) used for hero subtitle and feature descriptions
- **Tight**: Not used
- **Evidence**:
```tsx
/* services/frontend/src/app/page.tsx:83-84 */
<p className="text-xl sm:text-2xl text-surface-400 mb-12 max-w-3xl mx-auto leading-relaxed animate-slide-up">
```

---

### Letter Spacing (Tracking)

- **Tight**: `tracking-tight` used for large headings to improve readability
- **Wide**: `tracking-wide` used for uppercase badge text
- **Evidence**:
```tsx
/* services/frontend/src/app/page.tsx:76 */
<h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold mb-6 tracking-tight animate-slide-up">

/* services/frontend/src/app/globals.css:272 */
.status-badge {
  @apply px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wide;
}
```

---

## 4. Spacing, Layout, and Components

### Container Widths

| Container Class | Max Width | Usage | Evidence |
|----------------|-----------|-------|----------|
| `max-w-7xl` | 1280px | Main content sections (features, dashboard) | `services/frontend/src/app/page.tsx:130` |
| `max-w-5xl` | 1024px | Hero sections, narrow content | `services/frontend/src/app/page.tsx:65` |
| `max-w-4xl` | 896px | CTA sections, modals | `services/frontend/src/app/page.tsx:273` |
| `max-w-3xl` | 768px | Single-column content, subtitles | `services/frontend/src/app/page.tsx:83` |
| `max-w-2xl` | 672px | Stats grids, narrow cards | `services/frontend/src/app/page.tsx:111` |

---

### Layout Primitives

**Section Container**
```css
/* services/frontend/src/app/globals.css:303-305 */
.section-container {
  @apply max-w-7xl mx-auto px-4 sm:px-6 lg:px-8;
}
```
- **Purpose**: Standard section wrapper with responsive padding
- **Padding**: 16px (mobile) → 24px (sm) → 32px (lg)

---

**Page Wrapper**
```css
/* services/frontend/src/app/globals.css:308-310 */
.page-wrapper {
  @apply min-h-screen pt-20 pb-12;
}
```
- **Purpose**: Full-height page container with nav clearance
- **Padding**: 80px top (clears fixed nav), 48px bottom

---

**Video Card Grid**
```css
/* services/frontend/src/app/globals.css:517-532 */
.video-card-grid {
  @apply grid gap-5;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
}
@media (min-width: 640px) {
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
}
@media (min-width: 1024px) {
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
}
```
- **Purpose**: Responsive grid for video cards
- **Behavior**: Auto-fills with cards min 280px → 300px (sm) → 320px (lg)
- **Gap**: 20px between cards

---

### Component Inventory

#### Button (`.btn`)
- **Path**: `services/frontend/src/app/globals.css:131-193`
- **Purpose**: Primary interactive element
- **Variants**:
  - `.btn-primary`: Cyan gradient, white text, glow shadow
  - `.btn-secondary`: Dark gray with border, muted text
  - `.btn-ghost`: Transparent with hover background
  - `.btn-gradient`: Animated 3-color gradient (cyan → violet → pink)
- **Sizes**:
  - `.btn-sm`: Small (px-3.5 py-1.5 text-sm rounded-lg)
  - Default: Medium (px-5 py-2.5 rounded-xl)
  - `.btn-lg`: Large (px-8 py-4 text-lg rounded-xl)
- **States**: Hover (lift + glow), active (press down), disabled (50% opacity)
- **Visual Behavior**: 300ms transitions, translateY on hover, shadow intensifies

---

#### Card (`.card`, `.glass-card`)
- **Path**: `services/frontend/src/app/globals.css:94-128`
- **Purpose**: Content container with depth
- **Variants**:
  - `.card`: Solid card with gradient background
  - `.glass-card`: Glassmorphic card with backdrop blur
  - `.card-hover`: Adds hover state with border color change and lift
- **Structure**: Rounded-2xl, padding 24px, gradient background, subtle border
- **Visual Behavior**: Hover adds cyan border tint, shadow, and 2px lift

---

#### Badge (`.badge`, `.status-badge`)
- **Path**: `services/frontend/src/app/globals.css:237-289`
- **Purpose**: Status indicators and labels
- **Variants**:
  - `.badge-success`: Emerald green (ready state)
  - `.badge-warning`: Amber orange (pending state)
  - `.badge-error`: Red (failed state)
  - `.badge-info`: Blue (processing state)
  - `.badge-neutral`: Gray (default)
  - `.badge-accent`: Cyan (highlighted)
- **Structure**: Rounded-full, px-2.5 py-1, text-xs font-medium
- **Status badges**: Uppercase tracking-wide, semibold font

---

#### Input (`.input`)
- **Path**: `services/frontend/src/app/globals.css:196-211`
- **Purpose**: Text input fields
- **Structure**: Full width, rounded-xl, padding 12px 16px
- **Background**: surface-800/50 (semi-transparent dark)
- **Border**: surface-600/30 default, accent-cyan/50 on focus
- **Focus State**: Cyan border + ring shadow (0 0 0 3px rgba(6, 182, 212, 0.1))
- **Placeholder**: surface-500 (muted gray)

---

#### Select (`.select`)
- **Path**: `services/frontend/src/app/globals.css:214-229`
- **Purpose**: Dropdown selectors
- **Structure**: Same as input + custom chevron icon
- **Icon**: SVG chevron (surface-400 color) positioned right 12px center
- **Behavior**: Native select with custom styling, no JavaScript

---

#### Modal (`.modal-overlay`, `.modal-content`)
- **Path**: `services/frontend/src/app/globals.css:456-467`
- **Purpose**: Overlays for dialogs
- **Overlay**: Fixed inset-0, dark backdrop with blur
- **Content**: Rounded-2xl, max-w-md, gradient background, elevated shadow
- **Animation**: Scale-in entrance animation

---

#### Toast (`.toast`)
- **Path**: `services/frontend/src/app/globals.css:318-340`
- **Purpose**: Notification messages
- **Position**: Fixed top-24 right-4
- **Variants**:
  - `.toast-success`: Emerald gradient with green border
  - `.toast-error`: Red gradient with red border
  - `.toast-info`: Cyan gradient with cyan border
- **Animation**: Slide-in-right entrance
- **Structure**: Rounded-xl, min-w-320px, backdrop-blur-xl

---

#### Video Card (`.video-card`)
- **Path**: `services/frontend/src/app/globals.css:535-634`, `services/frontend/src/components/VideoCard.tsx`
- **Purpose**: Displays video thumbnail, metadata, status, actions
- **Structure**:
  - `.video-card-thumbnail`: 16:9 aspect ratio container
  - `.video-card-duration`: Absolute positioned duration badge
  - `.video-card-hover-overlay`: Hidden overlay with play button
  - `.video-card-content`: Padding 16px with title, meta, actions
- **States**: Processing (spinner overlay), hover (play button appears)
- **Animation**: Fade-in + slide-up on mount, hover lift + glow

---

#### Navigation Link (`.nav-link`)
- **Path**: `services/frontend/src/app/globals.css:399-422`
- **Purpose**: Top navigation links
- **Structure**: Rounded-lg, padding 8px 16px, font-medium
- **Colors**: surface-400 default, surface-100 on hover/active
- **Active State**: Gradient underline (cyan → violet)
- **Behavior**: 300ms color + background transitions

---

#### Scene Card (`.scene-card`)
- **Path**: `services/frontend/src/app/globals.css:439-453`
- **Purpose**: Search result scene preview
- **Structure**: Rounded-xl, padding 16px, gradient background
- **States**: Default (border surface-700/50), hover (cyan border tint + darker background), active (cyan border + cyan-tinted background)
- **Behavior**: Cursor pointer, 300ms transitions

---

#### Feature Card (`.feature-card`)
- **Path**: `services/frontend/src/app/globals.css:366-374`
- **Purpose**: Landing page feature showcase
- **Structure**: Rounded-2xl with 1px gradient border wrapper
- **Inner**: `.feature-card-inner` has dark gradient background
- **Border**: 3-color gradient (cyan → violet → pink)
- **Behavior**: Group hover scales icon by 110%

---

#### Progress Bar (`.progress-bar`)
- **Path**: `services/frontend/src/app/globals.css:343-351`
- **Purpose**: Loading/progress indicators
- **Structure**: Full width, height 8px, rounded-full
- **Background**: surface-800/80
- **Fill**: Gradient (cyan → violet), smooth 300ms transitions

---

#### Spinner (`.spinner`)
- **Path**: `services/frontend/src/app/globals.css:354-356`
- **Purpose**: Loading indicator
- **Structure**: Circular border with transparent top section
- **Animation**: Continuous 360° rotation
- **Colors**: surface-600 border, accent-cyan top border

---

### Page-Level Layout Components

#### GlobalNav
- **Path**: `services/frontend/src/components/GlobalNav.tsx`
- **Purpose**: Fixed top navigation with auth state
- **Structure**:
  - Fixed top-0, full width, z-50
  - Background: transparent default, surface-900/80 + backdrop-blur when scrolled
  - Height: 64px (h-16)
  - Container: max-w-7xl with responsive padding
  - Logo (left), Nav links (center, hidden on mobile), Auth buttons (right)
- **Behavior**:
  - Shows/hides based on route (hidden on onboarding)
  - Adds background + border on scroll (y > 20px)
  - Gradient line appears at bottom when scrolled
  - Auth state determines button display

---

#### Root Layout
- **Path**: `services/frontend/src/app/layout.tsx`
- **Purpose**: Wraps all pages
- **Structure**:
  ```tsx
  <html lang="en" className="dark">
    <body className="font-body antialiased bg-surface-950 text-surface-100">
      <LanguageProvider>
        <GlobalNav />
        <main>{children}</main>
      </LanguageProvider>
    </body>
  </html>
  ```
- **Provides**: Global styles, font loading, nav, i18n context

---

## 5. Navigation & Information Architecture

### Route Map

| Path | Component | Purpose | Auth Required | Evidence |
|------|-----------|---------|---------------|----------|
| `/` | `page.tsx` | Landing page with marketing content | No | `services/frontend/src/app/page.tsx` |
| `/login` | `login/page.tsx` | Sign in / sign up forms | No | Route exists |
| `/onboarding` | `onboarding/page.tsx` | First-time user profile setup | Yes (session) | Route exists |
| `/dashboard` | `dashboard/page.tsx` | User video library with stats | Yes | `services/frontend/src/app/dashboard/page.tsx:1-150` |
| `/upload` | `upload/page.tsx` | Video upload interface | Yes | Route exists |
| `/search` | `search/page.tsx` | Semantic video search with results | Yes | `services/frontend/src/app/search/page.tsx:1-150` |
| `/videos/[id]` | `videos/[id]/page.tsx` | Video detail view with scenes | Yes | Route exists |
| `/people` | `people/page.tsx` | Face profile management | Yes | Route exists |
| `/admin` | `admin/page.tsx` | Admin panel | Yes (admin role) | Route exists |
| `/admin/users/[id]` | `admin/users/[id]/page.tsx` | User management | Yes (admin role) | Route exists |

---

### Navigation Structure

**Top Navigation** (GlobalNav component):
- **Logo** (left): "Heimdex" with gradient text + icon, links to dashboard (auth) or home (no auth)
- **Nav Links** (center, hidden on mobile sm:flex):
  - Dashboard (grid icon)
  - Upload (upload icon)
  - Search (search icon)
- **Right Side**:
  - Language toggle (all pages)
  - Sign In button (unauthenticated)
  - Get Demo button (unauthenticated, gradient)
  - Sign Out button (authenticated)

**Evidence**:
```tsx
/* services/frontend/src/components/GlobalNav.tsx:69-182 */
<div className="flex justify-between items-center h-16">
  {/* Logo */}
  <button onClick={() => router.push(isAuthenticated ? '/dashboard' : '/')}>
    <span className="text-xl font-bold gradient-text">Heimdex</span>
  </button>

  {/* Navigation Links */}
  {isAuthenticated && (
    <div className="hidden sm:flex items-center gap-1">
      <button className={`nav-link ${isDashboard ? 'active' : ''}`}>Dashboard</button>
      <button className={`nav-link ${isUpload ? 'active' : ''}`}>Upload</button>
      <button className={`nav-link ${isSearch ? 'active' : ''}`}>Search</button>
    </div>
  )}

  {/* Right side */}
  <div className="flex items-center gap-3">
    <LanguageToggle />
    {isAuthenticated ? <SignOut /> : <SignIn + GetDemo />}
  </div>
</div>
```

---

### Key User Flows

#### Flow 1: New User → Video Search
1. Land on `/` (landing page)
2. Click "Get Started" or "Sign In"
3. Navigate to `/login`, sign up with email
4. Email confirmation → redirected to `/onboarding`
5. Complete profile (name, industry, language preference)
6. Redirected to `/dashboard`
7. Click "Upload Video" → `/upload`
8. Drag/drop video, configure scene detection, upload
9. Wait for processing (real-time status updates)
10. Click "Search Videos" or nav link → `/search`
11. Enter natural language query, adjust weights
12. View results, click scene to watch

**Evidence**: Flow inferred from auth gates, redirects in page components, and button actions.

---

#### Flow 2: Returning User → Video Details
1. Land on `/` → auto-redirect to `/dashboard`
2. View video library grid
3. Click "View Details" on ready video
4. Navigate to `/videos/[id]`
5. Watch video, browse scenes, view transcript
6. Filter by tags, export to short (YouTube Shorts)
7. Return to dashboard or search

**Evidence**:
```tsx
/* services/frontend/src/app/page.tsx:22-32 */
useEffect(() => {
  const checkAuth = async () => {
    const { data: { session } } = await supabase.auth.getSession();
    if (session) {
      router.push('/dashboard');
    }
  };
  checkAuth();
}, [router]);
```

---

#### Flow 3: Person-Based Search
1. Navigate to `/search`
2. Type person name at start of query (e.g., "J Lee presentation")
3. Person detection banner appears
4. Submit search → backend boosts person's face in results
5. Results show scenes with detected person highlighted

**Evidence**:
```tsx
/* services/frontend/src/app/search/page.tsx:90-117 */
// Detect person in query (longest-match-first, case-insensitive, word-boundary safe)
useEffect(() => {
  const normalizedQuery = query.toLowerCase().trim();
  const sortedPeople = [...people].sort((a, b) => b.display_name.length - a.display_name.length);
  const detected = sortedPeople.find((person) => {
    const normalizedName = person.display_name.toLowerCase();
    if (!normalizedQuery.startsWith(normalizedName)) return false;
    const charAfter = normalizedQuery[normalizedName.length];
    return !charAfter || /\s/.test(charAfter);
  });
  setDetectedPerson(detected || null);
}, [query, people]);
```

---

### Page Descriptions (from code)

**Landing Page (`/`)**:
- Hero section with gradient text title, subtitle, CTA buttons
- Stats grid (10x Faster, 99% Accuracy, 24/7 Processing)
- Features section (3 cards: Natural Language Search, Lightning Fast Processing, Secure & Private)
- How It Works section (3 steps: Upload, AI Processing, Search & Discover)
- CTA section with gradient background
- Footer with logo, tagline, copyright

**Evidence**: `services/frontend/src/app/page.tsx:46-337`

---

**Dashboard Page (`/dashboard`)**:
- Welcome message with user name
- Stats grid (Total Videos, Ready, Processing, Pending counts)
- Action buttons (Upload Video, Search Videos)
- Video library grid (VideoCard components)
- Empty state if no videos ("Upload your first video to get started!")
- Real-time status updates via Supabase subscriptions

**Evidence**: `services/frontend/src/app/dashboard/page.tsx:1-150`

---

**Search Page (`/search`)**:
- Search input with placeholder "Search for scenes, moments, or content..."
- Search weight controls (expandable panel)
- File filter toggle bar (show/hide videos)
- Results grid (scene cards with thumbnails)
- Video player panel (right side)
- Selected scenes tray (highlight reel builder)
- Person detection banner (when person name in query)
- Empty state if no results

**Evidence**: `services/frontend/src/app/search/page.tsx:1-150`

---

## 6. UI Copy & Messaging

### Product Name Usage

**"Heimdex"** appears in:
- **Logo**: Gradient text in GlobalNav (all pages)
- **Page title**: `<title>Heimdex - Vector-Native Video Archive</title>`
- **Hero headline**: Landing page hero section
- **Footer**: Landing page footer
- **Auth forms**: "Sign in to Heimdex", "Create your Heimdex account"

**Evidence**:
```tsx
/* services/frontend/src/app/layout.tsx:14 */
title: 'Heimdex - Vector-Native Video Archive'

/* services/frontend/src/components/GlobalNav.tsx:96 */
<span className="text-xl font-bold gradient-text">Heimdex</span>
```

---

### Headings & Subheadings

#### Landing Page (English)
```typescript
/* services/frontend/src/lib/i18n/translations.ts:35-61 */
heroTitle1: 'Search Your Videos'
heroTitle2: 'Like Never Before'
heroDescription: 'Heimdex indexes your entire video library directly from your existing storage—no uploading or moving files required. Search your videos in natural language and find the exact scene instantly.'

featuresTitle: 'Powerful Features'
featuresSubtitle: 'Everything you need to manage and search your video archive'

feature1Title: 'Natural Language Search'
feature1Description: 'Search your videos using everyday language. Ask questions like "show me the meeting where we discussed the budget" and get instant results.'

feature2Title: 'Lightning Fast Processing'
feature2Description: 'Advanced AI extracts audio, transcribes content, and creates searchable embeddings automatically. Your videos are ready to search in minutes.'

feature3Title: 'Secure & Private'
feature3Description: 'Your videos stay secure with enterprise-grade encryption and access controls. Self-hosted options available for maximum privacy.'

howItWorksTitle: 'How It Works'
ctaTitle: 'Ready to Transform Your Video Archive?'
```

---

#### Dashboard (English)
```typescript
/* services/frontend/src/lib/i18n/translations.ts:96-133 */
title: 'Heimdex Dashboard'
welcome: 'Welcome back'
uploadVideo: 'Upload Video'
searchVideos: 'Search Videos'
noVideos: 'No videos yet'
uploadFirst: 'Upload your first video to get started!'
yourVideos: 'Your Videos'
```

---

#### Search (English)
```typescript
/* services/frontend/src/lib/i18n/translations.ts:143-182 */
title: 'Search Videos'
subtitle: 'Search your videos with natural language'
searchPlaceholder: 'Search for scenes, moments, or content...'
enterQuery: 'Enter a search query'
enterQueryDescription: 'Search for anything in your videos using natural language'
noResults: 'No results found'
tryAdjusting: 'Try adjusting your search query'
```

---

### Call-to-Action (CTA) Text

**Landing Page**:
- Primary CTA: "Request a Demo" (gradient button)
- Secondary CTA: "Get Started" (secondary button)
- Nav CTA: "Get Demo" (gradient button)
- Footer CTA: "Schedule a Demo", "Contact Sales"

**Dashboard**:
- "Upload Video" (primary action)
- "Search Videos" (primary action)
- "Start Processing" (on pending videos)
- "View Details" (on ready videos)

**Evidence**:
```typescript
/* services/frontend/src/lib/i18n/translations.ts:38-39,58-59 */
requestDemo: 'Request a Demo'
getStarted: 'Get Started'
scheduleDemo: 'Schedule a Demo'
contactSales: 'Contact Sales'
```

---

### Tooltips & Placeholders

**Input Placeholders**:
```typescript
/* services/frontend/src/lib/i18n/translations.ts */
emailPlaceholder: 'Enter your email'
passwordPlaceholder: 'Enter your password'
searchPlaceholder: 'Search for scenes, moments, or content...'
industryPlaceholder: 'e.g., Technology, Healthcare, Education'
jobTitlePlaceholder: 'e.g., Software Engineer, Product Manager'
personNamePlaceholder: 'e.g., J Lee'
```

---

**Help Text**:
```typescript
preferredLanguageHelp: 'Choose the language for video transcriptions, summaries, and search results'
sceneDetectionHelp: 'Choose how scenes should be detected in your video'
modifyHint: 'Uncheck "Use my saved defaults" to modify weights'
```

---

### Empty States

**Dashboard (No Videos)**:
```typescript
noVideos: 'No videos yet'
uploadFirst: 'Upload your first video to get started!'
```
**Visual**: Large icon, title, description, "Upload Video" button

---

**Search (No Query)**:
```typescript
enterQuery: 'Enter a search query'
enterQueryDescription: 'Search for anything in your videos using natural language'
```

---

**Search (No Results)**:
```typescript
noResults: 'No results found'
tryAdjusting: 'Try adjusting your search query'
```

---

**People (No People)**:
```typescript
noPeople: 'No people profiles yet'
addFirstPerson: 'Add your first person to enable face recognition in search'
```

---

### Error Messages

**Auth Errors**: (Displayed via toast notifications, generic)
```typescript
error: 'Error'
```

---

**Upload Errors**:
```typescript
uploadError: 'Failed to upload video'
```

---

**Processing Errors**:
```typescript
failedToProcess: 'Failed to start processing'
failed: 'Video processing failed'
```

---

**Search Errors**:
```typescript
allFilesHidden: 'All files hidden'
enableFiles: 'Enable at least one file to see results'
```

---

**Export Errors**:
```typescript
exportFailed: 'Export Failed'
unknownError: 'Unknown error occurred'
limitReached: 'Export Limit Reached'
```

---

### Toast Notifications

**Success**:
```typescript
uploadSuccess: 'Video uploaded successfully!'
created: 'Person created successfully'
photoUploadSuccess: 'Photos uploaded successfully'
exportSuccess: 'Export started successfully!'
savedAsDefault: 'Saved as default'
```

---

**Info**:
```typescript
processingStarted: 'Video processing started!'
started: 'Video is now processing...'
```

---

**Error**:
```typescript
uploadError: 'Failed to upload video'
deleteError: 'Failed to delete person'
photoUploadError: 'Failed to upload photos'
exportError: 'Export failed'
```

---

### Onboarding & Help Text

**Onboarding**:
```typescript
title: 'Welcome to Heimdex'
subtitle: 'Let\'s get you set up. Please complete your profile to continue.'
fullName: 'Full Name'
fullNameRequired: '*'
preferredLanguage: 'Preferred Language'
preferredLanguageRequired: '*'
preferredLanguageHelp: 'Choose the language for video transcriptions, summaries, and search results'
marketingConsent: 'I agree to receive product updates and marketing communications from Heimdex'
continueButton: 'Continue to Dashboard'
```

---

**Person Detection (Search)**:
```typescript
personDetected: 'Person detected'
notReadyWarning: 'profile is still processing. Results may not be boosted yet.'
```
**Display**: "Person detected: J Lee" + warning if profile not ready

---

### i18n: Languages & Translation Keys

**Supported Languages**: English (en), Korean (ko)

**Translation Structure** (by feature area):
- `nav`: Navigation labels (Dashboard, Upload, Search)
- `common`: Shared UI text (Loading, Save, Cancel, etc.)
- `landing`: Landing page marketing copy
- `auth`: Sign in/up forms
- `onboarding`: Profile setup
- `dashboard`: Video library
- `upload`: Upload flow
- `search`: Search interface
- `videoDetails`: Video detail page
- `reprocess`: Reprocess modal
- `searchWeights`: Weight controls
- `fileFilter`: File toggle bar
- `export`: YouTube Shorts export
- `highlightReel`: Highlight reel builder
- `people`: Face profile management

**Evidence**: `services/frontend/src/lib/i18n/translations.ts:1-774`

**Korean Translation Example**:
```typescript
/* services/frontend/src/lib/i18n/translations.ts:420-422 */
ko: {
  landing: {
    heroTitle1: '영상 검색의 새로운 기준',
    heroTitle2: '영상 검색, 이제 차원이 다릅니다',
    heroDescription: 'Heimdex는 영상 이동 없이 기존 스토리지에서 직접 인덱싱하여, 전체 라이브러리를 자연어로 검색 가능하게 만듭니다. 필요한 장면을 즉시 찾아보세요.'
  }
}
```

---

## 7. Visual "Feel" Summary (Evidence-Based)

**Adjectives** (max 10, backed by code):
1. **Cinematic** - Deep blacks, gradient accents, wide aspect ratios
2. **Futuristic** - Gradient text, glow effects, glassmorphic surfaces
3. **Premium** - Subtle animations, smooth transitions, elevated shadows
4. **Technical** - Monospace font for code, precise spacing rhythm
5. **Dark** - Near-black backgrounds, no light mode
6. **Vibrant** - Cyan-violet-pink gradient as primary brand element
7. **Polished** - Rounded corners (2xl, xl), consistent borders
8. **Spacious** - Generous padding, breathing room
9. **Responsive** - Fluid layouts, mobile-first design
10. **Glowing** - Hover states add cyan glow shadows

---

**5 Concrete Examples from Code**:

1. **Gradient Text on Hero Headline**
```tsx
/* services/frontend/src/app/page.tsx:76-79 */
<h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold mb-6 tracking-tight animate-slide-up">
  <span className="text-surface-100">Search Your Videos</span>
  <br />
  <span className="gradient-text">Like Never Before</span>
</h1>
```
```css
/* services/frontend/src/app/globals.css:292-295 */
.gradient-text {
  @apply bg-clip-text text-transparent;
  background-image: linear-gradient(135deg, #06b6d4 0%, #8b5cf6 50%, #ec4899 100%);
}
```
**Effect**: Creates vibrant, eye-catching text with smooth color transition.

---

2. **Glassmorphic Card with Noise Texture**
```css
/* services/frontend/src/app/globals.css:95-110 */
.glass-card {
  @apply relative overflow-hidden;
  background: linear-gradient(145deg, rgba(30, 41, 59, 0.6) 0%, rgba(15, 23, 42, 0.8) 100%);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(148, 163, 184, 0.1);
  box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.36), inset 0 1px 0 0 rgba(255, 255, 255, 0.05);
}

.glass-card::before {
  content: '';
  position: absolute;
  inset: 0;
  background: url("data:image/svg+xml...");
  opacity: 0.02;
  pointer-events: none;
}
```
**Effect**: Creates depth with transparency, blur, and subtle grain texture.

---

3. **Hover Lift with Cyan Glow**
```css
/* services/frontend/src/app/globals.css:121-128 */
.card-hover:hover {
  border-color: rgba(6, 182, 212, 0.3);
  box-shadow: 0 8px 32px -4px rgba(0, 0, 0, 0.4), 0 0 20px -5px rgba(6, 182, 212, 0.2);
  transform: translateY(-2px);
}
```
**Effect**: Interactive elements float up with glowing cyan aura on hover.

---

4. **Rounded-2xl Cards with Gradient Backgrounds**
```css
/* services/frontend/src/app/globals.css:114-117 */
.card {
  @apply rounded-2xl p-6;
  background: linear-gradient(145deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.95) 100%);
  border: 1px solid rgba(148, 163, 184, 0.08);
}
```
**Effect**: Large border radius (32px) creates pill-like shapes with depth from gradient.

---

5. **Animated Gradient Background Orbs**
```tsx
/* services/frontend/src/app/page.tsx:48-52 */
<div className="fixed inset-0 pointer-events-none">
  <div className="absolute top-0 left-1/4 w-[600px] h-[600px] bg-accent-cyan/10 rounded-full blur-[120px] animate-float" />
  <div className="absolute top-1/3 right-1/4 w-[500px] h-[500px] bg-accent-violet/10 rounded-full blur-[100px] animate-float" style={{ animationDelay: '1s' }} />
  <div className="absolute bottom-0 left-1/2 w-[400px] h-[400px] bg-accent-pink/8 rounded-full blur-[80px]" />
</div>
```
```js
/* services/frontend/tailwind.config.js:109-112 */
float: {
  '0%, 100%': { transform: 'translateY(0px)' },
  '50%': { transform: 'translateY(-10px)' },
}
```
**Effect**: Large, blurred, floating gradient orbs create ambient background motion.

---

## 8. Design Debt / Inconsistencies (Evidence-Based)

### Issue 1: Multiple Button Hover States

**Issue**: Different hover transform values across button types.

**Evidence**:
```css
/* services/frontend/src/app/globals.css:142-145 */
.btn-primary:hover {
  box-shadow: 0 6px 20px -2px rgba(6, 182, 212, 0.5);
  transform: translateY(-1px); /* -1px lift */
}

/* services/frontend/src/app/globals.css:183-185 */
.btn-gradient:hover {
  box-shadow: 0 8px 30px -2px rgba(139, 92, 246, 0.5);
  transform: translateY(-2px); /* -2px lift */
}
```

**Suggested Normalization**: Standardize all button hovers to `-2px` translateY for consistency with card hovers.

---

### Issue 2: Inconsistent Rounded Corners

**Issue**: Mix of rounded-xl (12px), rounded-2xl (16px), rounded-full across similar components.

**Evidence**:
```css
/* services/frontend/src/app/globals.css:114 */
.card { @apply rounded-2xl p-6; } /* 16px */

/* services/frontend/src/app/globals.css:132 */
.btn { @apply relative px-5 py-2.5 rounded-xl /* 12px */ }

/* services/frontend/src/app/globals.css:197 */
.input { @apply w-full px-4 py-3 rounded-xl; /* 12px */ }

/* services/frontend/src/app/globals.css:238 */
.badge { @apply inline-flex items-center px-2.5 py-1 rounded-full; /* fully rounded */ }
```

**Suggested Normalization**: Define semantic rounding scale:
- `rounded-full` for pills/badges
- `rounded-2xl` for cards/modals
- `rounded-xl` for buttons/inputs
- Document the rationale (buttons = interactive, cards = content containers)

---

### Issue 3: Mixed Typography Scale on Metadata

**Issue**: Video card metadata uses `text-xs` while scene metadata uses `text-sm`.

**Evidence**:
```tsx
/* services/frontend/src/components/VideoCard.tsx:619 */
<div className="video-card-meta">
  {/* Uses text-xs from global CSS */}
```
```css
/* services/frontend/src/app/globals.css:619 */
.video-card-meta {
  @apply flex flex-wrap items-center gap-3 text-xs text-surface-500 mb-3;
}
```

Comparison: Scene cards appear to use larger text for similar metadata.

**Suggested Normalization**: Audit all metadata text sizes and standardize to `text-xs` for consistency.

---

### Issue 4: Ad-hoc Opacity Values

**Issue**: Inconsistent use of opacity values in rgba colors (0.1, 0.08, 0.05, 0.15, 0.2, 0.3, etc.)

**Evidence**:
```css
/* services/frontend/src/app/globals.css:99,116 */
border: 1px solid rgba(148, 163, 184, 0.1);
border: 1px solid rgba(148, 163, 184, 0.08);
```

**Suggested Normalization**: Define opacity scale:
- 0.05 - Barely visible (inner glow)
- 0.1 - Subtle (default borders)
- 0.2 - Visible (hover borders)
- 0.3 - Strong (active states)
Use only these values unless special cases require deviation.

---

### Issue 5: Status Badge Color Inconsistency

**Issue**: Status badges use different color value formats (named classes vs inline styles).

**Evidence**:
```css
/* services/frontend/src/app/globals.css:275-289 */
.status-pending {
  @apply bg-amber-500/15 text-amber-400 border border-amber-500/25;
}

.status-processing {
  @apply bg-blue-500/15 text-blue-400 border border-blue-500/25;
}
```

Compared to general badges:
```css
/* services/frontend/src/app/globals.css:243-244 */
.badge-success {
  @apply bg-emerald-500/20 text-emerald-400 border-emerald-500/30;
}
```

**Inconsistency**: Status badges use 15% bg opacity, general badges use 20%. Border opacity also differs (25% vs 30%).

**Suggested Normalization**: Unify badge opacity values across both types or document rationale for different opacities.

---

## 9. Appendix: Key Snippets

### Tailwind Config (Complete)
```javascript
/* services/frontend/tailwind.config.js:1-142 */
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Core palette - Deep cinematic darks
        surface: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#1e293b',
          800: '#0f172a',
          900: '#0a0f1a',
          950: '#050709',
        },
        // Accent - Vivid cyan to violet gradient stops
        accent: {
          cyan: '#06b6d4',
          teal: '#14b8a6',
          violet: '#8b5cf6',
          purple: '#a855f7',
          pink: '#ec4899',
        },
        // Primary brand colors
        primary: {
          50: '#ecfeff',
          100: '#cffafe',
          200: '#a5f3fc',
          300: '#67e8f9',
          400: '#22d3ee',
          500: '#06b6d4',
          600: '#0891b2',
          700: '#0e7490',
          800: '#155e75',
          900: '#164e63',
        },
        // Status colors - refined
        status: {
          success: '#10b981',
          warning: '#f59e0b',
          error: '#ef4444',
          info: '#3b82f6',
        },
      },
      fontFamily: {
        display: ['var(--font-display)', 'system-ui', 'sans-serif'],
        body: ['var(--font-body)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'monospace'],
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic': 'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
        'gradient-mesh': 'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 400 400\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'noiseFilter\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.9\' numOctaves=\'3\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23noiseFilter)\'/%3E%3C/svg%3E")',
        'hero-gradient': 'linear-gradient(135deg, rgba(6, 182, 212, 0.15) 0%, rgba(139, 92, 246, 0.15) 50%, rgba(236, 72, 153, 0.1) 100%)',
        'card-gradient': 'linear-gradient(145deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%)',
        'glass-gradient': 'linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%)',
      },
      boxShadow: {
        'glow-sm': '0 0 15px -3px rgba(6, 182, 212, 0.3)',
        'glow': '0 0 30px -5px rgba(6, 182, 212, 0.4)',
        'glow-lg': '0 0 50px -10px rgba(6, 182, 212, 0.5)',
        'glow-violet': '0 0 30px -5px rgba(139, 92, 246, 0.4)',
        'glass': '0 8px 32px 0 rgba(0, 0, 0, 0.36)',
        'elevated': '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
        'inner-glow': 'inset 0 1px 0 0 rgba(255,255,255,0.1)',
      },
      keyframes: {
        shimmer: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
        'slide-up': {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        'slide-down': {
          '0%': { transform: 'translateY(-10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        'slide-in-right': {
          '0%': { transform: 'translateX(100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'scale-in': {
          '0%': { transform: 'scale(0.95)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 20px -5px rgba(6, 182, 212, 0.4)' },
          '50%': { boxShadow: '0 0 30px -5px rgba(6, 182, 212, 0.6)' },
        },
        'gradient-shift': {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        'spin-slow': {
          '0%': { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' },
        },
      },
      animation: {
        shimmer: 'shimmer 2s infinite',
        'slide-up': 'slide-up 0.4s ease-out',
        'slide-down': 'slide-down 0.4s ease-out',
        'slide-in-right': 'slide-in-right 0.4s ease-out',
        'fade-in': 'fade-in 0.3s ease-out',
        'scale-in': 'scale-in 0.3s ease-out',
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
        'gradient-shift': 'gradient-shift 8s ease infinite',
        float: 'float 3s ease-in-out infinite',
        'spin-slow': 'spin-slow 8s linear infinite',
      },
      backdropBlur: {
        xs: '2px',
      },
      transitionDuration: {
        '400': '400ms',
      },
      borderRadius: {
        '4xl': '2rem',
      },
    },
  },
  plugins: [],
}
```

---

### Global CSS Variables
```css
/* services/frontend/src/app/globals.css:7-38 */
:root {
  /* Font families */
  --font-display: 'Outfit', system-ui, sans-serif;
  --font-body: 'Outfit', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;

  /* Core colors */
  --color-bg-primary: #050709;
  --color-bg-secondary: #0a0f1a;
  --color-bg-tertiary: #0f172a;
  --color-bg-elevated: #1e293b;

  --color-text-primary: #f1f5f9;
  --color-text-secondary: #94a3b8;
  --color-text-muted: #64748b;

  --color-accent-cyan: #06b6d4;
  --color-accent-violet: #8b5cf6;
  --color-accent-pink: #ec4899;

  --color-border: rgba(148, 163, 184, 0.1);
  --color-border-hover: rgba(148, 163, 184, 0.2);

  /* Gradients */
  --gradient-brand: linear-gradient(135deg, #06b6d4 0%, #8b5cf6 50%, #ec4899 100%);
  --gradient-brand-subtle: linear-gradient(135deg, rgba(6, 182, 212, 0.2) 0%, rgba(139, 92, 246, 0.2) 50%, rgba(236, 72, 153, 0.15) 100%);
  --gradient-surface: linear-gradient(180deg, rgba(15, 23, 42, 0.5) 0%, rgba(10, 15, 26, 0.8) 100%);

  /* Shadows */
  --shadow-glow: 0 0 30px -5px rgba(6, 182, 212, 0.4);
  --shadow-glass: 0 8px 32px 0 rgba(0, 0, 0, 0.36);
}
```

---

### Main Layout Shell
```tsx
/* services/frontend/src/app/layout.tsx:24-45 */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body className="font-body antialiased bg-surface-950 text-surface-100">
        <LanguageProvider>
          <GlobalNav />
          <main>
            {children}
          </main>
        </LanguageProvider>
      </body>
    </html>
  );
}
```

---

### Primary Button Component
```css
/* services/frontend/src/app/globals.css:131-155 */
.btn {
  @apply relative px-5 py-2.5 rounded-xl font-medium transition-all duration-300 overflow-hidden;
  @apply flex items-center justify-center gap-2;
}

.btn-primary {
  background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);
  color: white;
  box-shadow: 0 4px 14px -2px rgba(6, 182, 212, 0.4);
}

.btn-primary:hover {
  box-shadow: 0 6px 20px -2px rgba(6, 182, 212, 0.5);
  transform: translateY(-1px);
}

.btn-primary:active {
  transform: translateY(0);
}

.btn-primary:disabled {
  @apply opacity-50 cursor-not-allowed;
  transform: none;
  box-shadow: none;
}
```

---

### GlobalNav Component (Condensed)
```tsx
/* services/frontend/src/components/GlobalNav.tsx:60-189 */
return (
  <nav className={`fixed top-0 w-full z-50 transition-all duration-300 ${
    scrolled ? 'bg-surface-900/80 backdrop-blur-xl border-b border-surface-700/50' : 'bg-transparent'
  }`}>
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div className="flex justify-between items-center h-16">
        {/* Logo */}
        <button onClick={() => router.push(isAuthenticated ? '/dashboard' : '/')}>
          <div className="relative w-8 h-8">
            <div className="absolute inset-0 rounded-lg bg-gradient-to-br from-accent-cyan via-accent-violet to-accent-pink opacity-80" />
            <div className="absolute inset-[2px] rounded-[6px] bg-surface-900 flex items-center justify-center">
              <svg className="w-4 h-4 text-accent-cyan" viewBox="0 0 24 24">
                <polygon points="23 7 16 12 23 17 23 7" />
                <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
              </svg>
            </div>
          </div>
          <span className="text-xl font-bold gradient-text">Heimdex</span>
        </button>

        {/* Navigation Links */}
        {isAuthenticated && (
          <div className="hidden sm:flex items-center gap-1">
            <button className={`nav-link ${isDashboard ? 'active' : ''}`}>Dashboard</button>
            <button className={`nav-link ${isUpload ? 'active' : ''}`}>Upload</button>
            <button className={`nav-link ${isSearch ? 'active' : ''}`}>Search</button>
          </div>
        )}

        {/* Right side */}
        <div className="flex items-center gap-3">
          <LanguageToggle />
          {isAuthenticated ? (
            <button onClick={handleSignOut} className="btn btn-ghost text-sm">Sign Out</button>
          ) : (
            <button className="btn btn-gradient text-sm">Get Demo</button>
          )}
        </div>
      </div>
    </div>

    {/* Gradient line at bottom when scrolled */}
    {scrolled && (
      <div className="absolute bottom-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-accent-cyan/20 to-transparent" />
    )}
  </nav>
);
```

---

**End of Document**
