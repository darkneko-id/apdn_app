# TKDN Finder — Design System

**Style:** Trust & Authority · Minimal Enterprise Tool  
**Stack:** Tailwind CSS v3 · Alpine.js · HTMX · Jinja2  
**Dark mode:** Class-based (`dark:`) via Alpine.js store + `localStorage`

---

## 1. Color Tokens

### Light Mode (default)

| Token | Value | Usage |
|-------|-------|-------|
| `--color-bg` | `#F8FAFC` (gray-50) | Page background |
| `--color-surface` | `#FFFFFF` | Card, table, input background |
| `--color-surface-muted` | `#F9FAFB` (gray-50) | Table header, card footer |
| `--color-border` | `#E5E7EB` (gray-200) | Border divider |
| `--color-border-strong` | `#D1D5DB` (gray-300) | Input border (resting) |
| `--color-text-primary` | `#111827` (gray-900) | Heading, main content |
| `--color-text-secondary` | `#374151` (gray-700) | Body text |
| `--color-text-muted` | `#6B7280` (gray-500) | Labels, helper text, metadata |
| `--color-text-subtle` | `#9CA3AF` (gray-400) | Placeholder, empty state |
| `--color-primary` | `#1D4ED8` (blue-700) | Primary button, link |
| `--color-primary-nav` | `#1E3A8A` (blue-800) | Top navigation bar |
| `--color-primary-hover` | `#1E40AF` (blue-800) | Primary button hover |
| `--color-focus-ring` | `#3B82F6` (blue-500) | Focus ring |
| `--color-success` | `#15803D` (green-700) | TKDN ≥ 40%, valid badge text |
| `--color-success-bg` | `#DCFCE7` (green-100) | Valid badge background |
| `--color-warning` | `#A16207` (yellow-700) | TKDN 25–39%, expiring badge text |
| `--color-warning-bg` | `#FEF9C3` (amber-100) | Expiring badge background |
| `--color-danger` | `#B91C1C` (red-700) | TKDN < 25%, expired badge text |
| `--color-danger-bg` | `#FEE2E2` (red-100) | Expired badge background |

### Dark Mode (`dark:` prefix)

| Token | Tailwind | Usage |
|-------|----------|-------|
| Page background | `dark:bg-gray-950` | `#030712` |
| Surface | `dark:bg-gray-900` | `#111827` — card, table, input |
| Surface muted | `dark:bg-gray-800` | `#1F2937` — table header, card footer |
| Border | `dark:border-gray-800` | `#1F2937` |
| Border input | `dark:border-gray-700` | `#374151` |
| Text primary | `dark:text-gray-100` | `#F3F4F6` |
| Text secondary | `dark:text-gray-300` | `#D1D5DB` |
| Text muted | `dark:text-gray-500` | `#6B7280` |
| Text subtle | `dark:text-gray-600` | `#4B5563` |
| Nav bar | `dark:bg-gray-900` | Same surface as cards |
| Success text | `dark:text-green-400` | `#4ADE80` |
| Warning text | `dark:text-yellow-400` | `#FACC15` |
| Danger text | `dark:text-red-400` | `#F87171` |
| Success bg | `dark:bg-green-900/40` | Semi-transparent |
| Warning bg | `dark:bg-amber-900/40` | Semi-transparent |
| Danger bg | `dark:bg-red-900/40` | Semi-transparent |

### TKDN Value Color Logic

```
nilai_tkdn >= 40  → green-700  / dark:green-400   (Memenuhi syarat)
nilai_tkdn >= 25  → yellow-700 / dark:yellow-400  (Borderline)
nilai_tkdn < 25   → red-700    / dark:red-400      (Tidak memenuhi)
null / unknown    → gray-300   / dark:gray-700
```

---

## 2. Typography

**Font:** Inter (Google Fonts) — single family throughout.

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

### Type Scale

| Role | Class | Size | Weight | Usage |
|------|-------|------|--------|-------|
| Page title | `text-lg font-semibold` | 18px / 600 | Heading per halaman |
| Section heading | `text-base font-semibold` | 16px / 600 | Card header, section |
| Body | `text-sm` | 14px / 400 | Default body, table cell |
| Label | `text-xs font-medium` | 12px / 500 | Form label, column header |
| Caption / Meta | `text-xs` | 12px / 400 | Timestamp, helper text |
| Stat large | `text-3xl font-bold` | 30px / 700 | TKDN % di detail page |
| Stat medium | `text-lg font-semibold` | 18px / 600 | Secondary stat values |
| Code / ID | `font-mono text-xs` | 12px / 400 | Kode HS, KBLI, internal ID |
| Numeric data | `tabular-nums` | — | Semua angka di tabel |

### Text Color Pattern

```
Heading content  → text-gray-900   dark:text-gray-100
Body content     → text-gray-700   dark:text-gray-300
Label/metadata   → text-gray-500   dark:text-gray-500
Placeholder      → text-gray-400   dark:text-gray-600
Disabled/subtle  → text-gray-300   dark:text-gray-700
Link             → text-blue-600   dark:text-blue-400
Link hover       → text-blue-800   dark:text-blue-300 + underline
Nav text (on dark) → text-blue-100 dark:text-gray-400
```

---

## 3. Spacing & Layout

**Base unit:** 4px (Tailwind default). Selalu gunakan kelipatan 4.

### Page Layout

```
Max width     : max-w-screen-2xl mx-auto   (1536px)
Horizontal pad: px-4 sm:px-6
Vertical pad  : py-6
Stack gap     : space-y-5 (page sections), space-y-3 (form groups)
```

### Component Spacing

| Context | Class | Value |
|---------|-------|-------|
| Nav height | `h-14` | 56px |
| Button padding (primary) | `px-5 py-2.5` | 20px × 10px |
| Button padding (small) | `px-3 py-1.5` | 12px × 6px |
| Input padding | `px-3.5 py-2.5` | 14px × 10px |
| Input height (compact) | `h-9` | 36px |
| Table cell padding | `px-3 py-2.5` (header) · `px-3 py-0` (row, h-10) | — |
| Card padding | `px-6 py-5` | — |
| Badge padding | `px-2 py-0.5` | — |
| Badge padding (large) | `px-3 py-1` | Detail page |

---

## 4. Components

### 4.1 Navigation Bar

```html
<nav class="bg-blue-800 dark:bg-gray-900 border-b border-blue-900 dark:border-gray-800 shadow-sm">
  <div class="max-w-screen-2xl mx-auto px-4 sm:px-6">
    <div class="flex items-center justify-between h-14">
      <!-- Brand -->
      <div class="flex items-center gap-3">
        <a href="/" class="text-base font-semibold tracking-tight text-white hover:text-blue-200 dark:hover:text-gray-300 transition-colors">
          App Name
        </a>
        <span class="text-blue-400 dark:text-gray-600 text-xs hidden sm:block">Subtitle / tagline</span>
      </div>
      <!-- Right actions -->
      <div class="flex items-center gap-1">
        <!-- Dark mode toggle button -->
        <button class="p-2 rounded-md text-blue-200 dark:text-gray-400 hover:text-white dark:hover:text-gray-200 hover:bg-blue-700 dark:hover:bg-gray-800 transition-colors">
          <!-- SVG icon -->
        </button>
        <div class="w-px h-4 bg-blue-600 dark:bg-gray-700 mx-1"></div>
        <!-- Nav links -->
        <a href="/" class="px-3 py-1.5 text-xs font-medium text-blue-100 dark:text-gray-400 hover:text-white dark:hover:text-gray-200 hover:bg-blue-700 dark:hover:bg-gray-800 rounded-md transition-colors">
          Menu Item
        </a>
      </div>
    </div>
  </div>
</nav>
```

**Pattern:** Solid blue-800 (light) / gray-900 (dark). Nav links are small (`text-xs`), subtle by default, full white on hover.

---

### 4.2 Primary Search Input

```html
<input
  type="text"
  placeholder="Cari..."
  class="flex-1 px-3.5 py-2.5 text-sm bg-white dark:bg-gray-900
         border border-gray-300 dark:border-gray-700 rounded-lg shadow-sm
         text-gray-900 dark:text-gray-100
         placeholder:text-gray-400 dark:placeholder:text-gray-600
         focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-600
         focus:border-blue-500 dark:focus:border-blue-600
         transition-colors"
/>
```

---

### 4.3 Primary Button

```html
<button class="px-5 py-2.5 bg-blue-700 dark:bg-blue-800 text-white text-sm font-medium rounded-lg
               hover:bg-blue-800 dark:hover:bg-blue-700
               focus:outline-none focus:ring-2 focus:ring-blue-500
               transition-colors whitespace-nowrap">
  Cari
</button>
```

---

### 4.4 Secondary / Ghost Button

```html
<button class="inline-flex items-center gap-1.5 text-xs
               text-gray-500 dark:text-gray-500
               hover:text-blue-700 dark:hover:text-blue-400
               border border-gray-300 dark:border-gray-700
               hover:border-blue-400 dark:hover:border-blue-600
               rounded-md px-2.5 py-1 transition-colors
               bg-white dark:bg-gray-900">
  Action
</button>
```

---

### 4.5 Form Controls (Compact)

```html
<!-- Number input -->
<input type="number"
  class="h-9 w-24 px-3 text-sm bg-white dark:bg-gray-900
         border border-gray-300 dark:border-gray-700
         text-gray-900 dark:text-gray-100
         rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500
         transition-colors"/>

<!-- Select -->
<select class="h-9 px-3 text-sm bg-white dark:bg-gray-900
               border border-gray-300 dark:border-gray-700
               text-gray-900 dark:text-gray-100
               rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500
               transition-colors">
  <option value="">Semua</option>
</select>

<!-- Checkbox -->
<input type="checkbox"
  class="h-4 w-4 rounded border-gray-300 dark:border-gray-600
         text-blue-600 focus:ring-blue-500
         bg-white dark:bg-gray-900"/>
```

**Form label pattern:**
```html
<div class="flex flex-col gap-1">
  <label class="h-5 flex items-center text-xs font-medium text-gray-500 dark:text-gray-500">
    Label
  </label>
  <!-- input here -->
</div>
```

---

### 4.6 Data Table

```html
<div class="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-800 shadow-sm">
  <table class="min-w-full text-xs">
    <thead>
      <tr class="bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800">
        <th class="px-3 py-2.5 text-left text-xs font-semibold text-gray-600 dark:text-gray-400 whitespace-nowrap">
          Column
        </th>
      </tr>
    </thead>
    <tbody class="bg-white dark:bg-gray-900 divide-y divide-gray-100 dark:divide-gray-800">
      <tr class="hover:bg-blue-50 dark:hover:bg-gray-800 transition-colors h-10">
        <td class="px-3 py-0 align-middle">
          <div class="truncate font-medium text-gray-900 dark:text-gray-100" title="Full text on hover">
            Content
          </div>
        </td>
      </tr>
    </tbody>
  </table>
</div>
```

**Row hierarchy:**
- Primary cell (e.g. nama_perusahaan): `font-medium text-gray-900 dark:text-gray-100`
- Secondary cell (e.g. nama_produk): `text-gray-700 dark:text-gray-300`
- Tertiary cell (e.g. spesifikasi, tipe): `text-gray-600 dark:text-gray-400`
- Empty value: `—` rendered as `text-gray-300 dark:text-gray-700`

---

### 4.7 Status Badges

```html
<!-- Valid / Berlaku -->
<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium
             bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-300">
  Berlaku
</span>

<!-- Expiring / Segera Habis -->
<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium
             bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300">
  Habis
</span>

<!-- Expired / Kadaluarsa -->
<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium
             bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-300">
  Kadaluarsa
</span>

<!-- Unknown / Neutral -->
<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium
             bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-500">
  —
</span>
```

**Large badge variant (detail page, on dark header):**
```html
<span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold
             bg-green-400/20 text-green-100 border border-green-400/30">
  Berlaku
</span>
```

---

### 4.8 Card / Detail Panel

```html
<div class="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm overflow-hidden">
  <!-- Colored header -->
  <div class="bg-blue-800 dark:bg-blue-900 px-6 py-5 text-white">
    <h1 class="text-xl font-bold">Title</h1>
    <p class="mt-1 text-blue-200 text-sm">Subtitle</p>
  </div>

  <!-- Highlight stat strip -->
  <div class="bg-gray-50 dark:bg-gray-800 px-6 py-4 border-b border-gray-200 dark:border-gray-700">
    <!-- Stat items side by side -->
    <div class="flex items-center gap-8">
      <div>
        <p class="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Label</p>
        <p class="text-3xl font-bold mt-0.5 text-green-700 dark:text-green-400">42.50<span class="text-lg font-normal">%</span></p>
      </div>
    </div>
  </div>

  <!-- Detail grid -->
  <div class="px-6 py-5 grid grid-cols-1 sm:grid-cols-2 gap-5">
    <div>
      <p class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Field Label</p>
      <p class="mt-1 text-gray-900 dark:text-gray-100">Value</p>
    </div>
  </div>

  <!-- Card footer -->
  <div class="bg-gray-50 dark:bg-gray-800 px-6 py-3 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between">
    <p class="text-xs text-gray-400 dark:text-gray-600">Meta info</p>
    <a href="#" class="text-xs text-blue-600 dark:text-blue-400 hover:underline">Action</a>
  </div>
</div>
```

---

### 4.9 Loading Spinner (HTMX Indicator)

```html
<!-- Spinner element — shown automatically by HTMX during requests -->
<div id="spinner" class="htmx-indicator h-9 items-center">
  <svg class="animate-spin h-4 w-4 text-blue-500 dark:text-blue-400" fill="none" viewBox="0 0 24 24">
    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
  </svg>
</div>

<!-- CSS required -->
<style>
  .htmx-indicator { display: none; }
  .htmx-request .htmx-indicator { display: inline-flex; }
  .htmx-request.htmx-indicator { display: inline-flex; }
</style>
```

---

### 4.10 Empty State

```html
<div class="text-center py-16 text-gray-400 dark:text-gray-600">
  <svg class="mx-auto h-8 w-8 mb-3 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <!-- relevant icon -->
  </svg>
  <p class="text-sm font-medium text-gray-500 dark:text-gray-500">Tidak ada hasil ditemukan.</p>
  <p class="text-xs mt-1 text-gray-400 dark:text-gray-600">Coba ubah kata kunci atau kurangi filter.</p>
</div>
```

---

### 4.11 Results Summary Bar

```html
<div class="flex items-center justify-between mb-3 gap-4">
  <p class="text-xs text-gray-500 dark:text-gray-500 shrink-0">
    <span class="font-medium text-gray-700 dark:text-gray-300">50</span>
    dari <span class="font-medium text-gray-700 dark:text-gray-300">1240</span> hasil
    <span class="text-gray-400 dark:text-gray-600 ml-1">42 ms</span>
  </p>
  <div class="flex items-center gap-3 shrink-0">
    <!-- action buttons -->
  </div>
</div>
```

---

### 4.12 Pagination

```html
<div class="flex items-center justify-between mt-3">
  <p class="text-xs text-gray-400 dark:text-gray-600">Halaman 2 dari 25</p>
  <div class="flex gap-1.5">
    <button class="px-3 py-1 text-xs border border-gray-300 dark:border-gray-700 rounded-md
                   hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors
                   text-gray-600 dark:text-gray-400 bg-white dark:bg-gray-900">
      &laquo; Sebelumnya
    </button>
    <button class="px-3 py-1 text-xs border border-gray-300 dark:border-gray-700 rounded-md
                   hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors
                   text-gray-600 dark:text-gray-400 bg-white dark:bg-gray-900">
      Berikutnya &raquo;
    </button>
  </div>
</div>
```

---

### 4.13 Back Link

```html
<a href="javascript:history.back()"
   class="text-sm text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1">
  <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/>
  </svg>
  Kembali
</a>
```

---

### 4.14 Sortable Table Header Button

```html
<!-- Active, ascending -->
<button class="group inline-flex items-center gap-1 text-xs font-semibold
               text-gray-600 dark:text-gray-400
               hover:text-gray-900 dark:hover:text-gray-100
               whitespace-nowrap transition-colors">
  Label
  <!-- Active sort indicator: blue -->
  <svg class="h-3 w-3 text-blue-600 dark:text-blue-400 shrink-0" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" d="M5 15l7-7 7 7"/>
  </svg>
</button>

<!-- Inactive: gray, shows on group-hover -->
<button class="group inline-flex items-center gap-1 ...">
  Label
  <svg class="h-3 w-3 text-gray-300 dark:text-gray-700 group-hover:text-gray-400 dark:group-hover:text-gray-500 shrink-0 transition-colors" ...>
    <path d="M8 9l4-4 4 4M16 15l-4 4-4-4"/>
  </svg>
</button>
```

---

### 4.15 Detail Field (Label + Value pattern)

```html
<div>
  <p class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
    Field Label
  </p>
  <p class="mt-1 text-gray-900 dark:text-gray-100">Value</p>
</div>

<!-- Full-width variant -->
<div class="sm:col-span-2">
  <p class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Spesifikasi</p>
  <p class="mt-1 text-gray-900 dark:text-gray-100 whitespace-pre-wrap">{{ value }}</p>
</div>
```

---

## 5. Dark Mode Setup

### Alpine.js Store Pattern

```html
<!-- In <head> — prevents flash of wrong theme -->
<script>
  if (localStorage.getItem('theme') === 'dark')
    document.documentElement.classList.add('dark');
</script>

<!-- Alpine store registration -->
<script>
  document.addEventListener('alpine:init', () => {
    Alpine.store('ui', {
      dark: localStorage.getItem('theme') === 'dark',
      toggleDark() {
        this.dark = !this.dark;
        localStorage.setItem('theme', this.dark ? 'dark' : 'light');
        document.documentElement.classList.toggle('dark', this.dark);
      }
    });
  });
</script>
```

### Tailwind Config

```js
tailwind.config = {
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] }
    }
  }
}
```

### `<body>` base classes

```html
<body x-data
  class="bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100
         min-h-screen flex flex-col text-sm transition-colors duration-150">
```

---

## 6. Icons

All icons: inline SVG only. Style: `stroke="currentColor"`, `fill="none"`, `stroke-width="2"`.

| Size | Class | Usage |
|------|-------|-------|
| xs | `h-3 w-3` | Sort arrows, inline indicators |
| sm | `h-3.5 w-3.5` | Button icons, download link |
| md | `h-4 w-4` | Nav toggle, back arrow, spinner |
| lg | `h-8 w-8` | Empty state illustration |

**Spinner:** `animate-spin` on a `circle` + `path` SVG. Outer circle `opacity-25`, fill path `opacity-75`.

---

## 7. Responsive Breakpoints

| Breakpoint | Tailwind prefix | Min-width |
|------------|-----------------|-----------|
| Mobile | (default) | 0px |
| Small | `sm:` | 640px |
| Medium | `md:` | 768px |
| Large | `lg:` | 1024px |
| XL | `xl:` | 1280px |
| 2XL | `2xl:` | 1536px |

Page max-width: `max-w-screen-2xl` (1536px). Detail page max-width: `max-w-3xl` (768px).

---

## 8. Transitions

| Pattern | Class |
|---------|-------|
| Color/bg transitions | `transition-colors` (150ms ease) |
| Body theme switch | `transition-colors duration-150` |
| All properties (if needed) | `transition` |

Avoid animating layout properties (width, height, top, left). Stick to `color`, `background-color`, `border-color`, `opacity`.

---

## 9. Anti-patterns (Avoid)

- ❌ Emojis as icons — use inline SVG
- ❌ Hardcoded hex colors — use Tailwind semantic classes
- ❌ Raw SQL or logic in templates
- ❌ Mixing `px`-based sizes and Tailwind utilities arbitrarily
- ❌ Nested scrollable regions inside the main table container
- ❌ Using `100vh` on mobile — prefer `min-h-screen` (Tailwind handles this)
- ❌ Removing focus rings — always keep `focus:ring-*`
- ❌ Inline `style=""` for theme-aware properties
- ❌ Icon-only buttons without `title` attribute for accessibility
- ❌ Placeholder text as label substitute — always use `<label>` or `sr-only`

---

## 10. Page Structure Template

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Page Title — App Name</title>

  <!-- Prevent dark mode flash -->
  <script>if (localStorage.getItem('theme') === 'dark') document.documentElement.classList.add('dark');</script>

  <!-- Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">

  <!-- Tailwind CDN (dev) or built CSS (prod) -->
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: { extend: { fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] } } }
    }
  </script>

  <!-- Alpine store -->
  <script>
    document.addEventListener('alpine:init', () => {
      Alpine.store('ui', {
        dark: localStorage.getItem('theme') === 'dark',
        toggleDark() {
          this.dark = !this.dark;
          localStorage.setItem('theme', this.dark ? 'dark' : 'light');
          document.documentElement.classList.toggle('dark', this.dark);
        }
      });
    });
  </script>

  <!-- Alpine.js — pin to exact version + SRI for CDN integrity -->
  <script defer
    src="https://cdn.jsdelivr.net/npm/alpinejs@3.14.9/dist/cdn.min.js"
    integrity="sha384-9Ax3MmS9AClxJyd5/zafcXXjxmwFhZCdsT6HJoJjarvCaAkJlk5QDzjLJm+Wdx5F"
    crossorigin="anonymous"></script>

  <!-- HTMX — pin to exact version + SRI -->
  <script
    src="https://unpkg.com/htmx.org@1.9.10/dist/htmx.min.js"
    integrity="sha384-D1Kt99CQMDuVetoL1lrYwg5t+9QdHe7NLX/SoJYkXDFfX37iInKRy5xLSi8nO7UC"
    crossorigin="anonymous"></script>

  <style>
    body { font-family: 'Inter', system-ui, sans-serif; }
    [x-cloak] { display: none !important; }
    .htmx-indicator { display: none; }
    .htmx-request .htmx-indicator { display: inline-flex; }
    .htmx-request.htmx-indicator { display: inline-flex; }
  </style>
</head>
<body x-data class="bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100 min-h-screen flex flex-col text-sm transition-colors duration-150">

  <!-- NAV -->
  <nav class="bg-blue-800 dark:bg-gray-900 border-b border-blue-900 dark:border-gray-800 shadow-sm">
    <!-- see Section 4.1 -->
  </nav>

  <!-- MAIN CONTENT -->
  <main class="flex-1 max-w-screen-2xl mx-auto w-full px-4 sm:px-6 py-6">
    <!-- page content here -->
  </main>

  <!-- FOOTER -->
  <footer class="border-t border-gray-200 dark:border-gray-800 mt-auto">
    <div class="max-w-screen-2xl mx-auto px-4 py-3 text-center text-xs text-gray-400 dark:text-gray-600">
      App Name v1.0.0
    </div>
  </footer>

</body>
</html>
```

---

## 11. Checklist Sebelum Deploy

- [ ] Semua icon pakai inline SVG (bukan emoji)
- [ ] Semua interactive element punya `focus:ring-*`
- [ ] Dark mode diuji di semua komponen baru
- [ ] Angka/numerik pakai `tabular-nums`
- [ ] Tabel punya `overflow-x-auto` wrapper
- [ ] Empty state tersedia di semua list/table
- [ ] Loading indicator terpasang untuk async request
- [ ] `title=""` ada di semua elemen yang di-truncate
- [ ] `sr-only` label ada untuk input tanpa visible label
- [ ] Font Inter loaded sebelum first paint
