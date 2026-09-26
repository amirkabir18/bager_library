# System Design Document: Modern PySide6 UI Migration

This document specifies the UI/UX architecture, visual tokens, widget hierarchy, QSS styling, and implementation plan for upgrading the **Bager Library Management System** from CustomTkinter to **PySide6**, based on the target dashboard layout and brand guidelines.

---

## 1. Visual Design Tokens & Palette

### 1.1 Color Palette

| Token Key | Persian Role | Color Name | HEX Code | PySide6 / QSS Role |
| :--- | :--- | :--- | :--- | :--- |
| `color-primary` | رنگ اصلی | آبی برند | `#2945D3` | Primary interactive elements, active nav items, pagination active, brand links |
| `color-primary-dark` | آبی تیره | هدر / متن مهم | `#172B8F` | Global header background, dark text accents, critical emphasis |
| `color-primary-light` | آبی روشن | Hover / پس‌زمینه | `#EAF0FF` | Hover states, category pill backgrounds, selected table row highlight |
| `color-accent` | رنگ تأکیدی | زرد مؤسسه | `#FFC400` | CTA button ("افزودن کتاب"), primary action icons, active icon rail indicator |
| `color-accent-light` | زرد روشن | پس‌زمینه تأکیدی | `#FFF7D6` | Warning badges ("در حال امانت"), highlight cards, loan overdue warnings |
| `color-bg-main` | پس‌زمینه اصلی | سفید مایل به آبی | `#F7F9FC` | Global viewport background behind cards and navigation |
| `color-bg-card` | کارت‌ها | سفید | `#FFFFFF` | Table container cards, sidebar background, dropdown popups |
| `color-text-main` | متن اصلی | سرمه‌ای | `#172033` | Primary labels, table cell content, header titles |
| `color-text-muted` | متن فرعی | خاکستری آبی | `#64748B` | Subtitles, placeholders, breadcrumbs, table secondary headers |
| `color-border` | مرزها / خطوط | خاکستری خیلی روشن | `#E2E8F0` | Dividers, card borders, table grid lines, input outlines |

### 1.2 Semantic Status Colors

| State | Background | Text | Border | Role |
| :--- | :--- | :--- | :--- | :--- |
| **Available (موجود)** | `#DCFCE7` | `#15803D` | `#86EFAC` | In-stock inventory badge |
| **Borrowed (در حال امانت)** | `#FFF7D6` | `#B45309` | `#FDE68A` | Active loans badge |
| **Overdue / Error (تاخیر / خطا)** | `#FEE2E2` | `#DC2626` | `#FECACA` | Overdue loans, error dialogs |
| **Info / Tag (برچسب رده)** | `#EAF0FF` | `#2945D3` | `#BFDBFE` | Category chips, Dewey classification tags |

---

## 2. Typography & Fonts

### 2.1 Font Family Hierarchy
1. **Primary App Font:** `IRANSansWeb(FaNum)`
   - Files location: `assets/fonts/iransans/ttf/`
   - Files:
     - `IRANSansWeb(FaNum)_Bold.ttf` (Headers, CTA buttons, active tabs)
     - `IRANSansWeb(FaNum)_Medium.ttf` (Navigation items, table headings, filter tags)
     - `IRANSansWeb(FaNum).ttf` (Regular: table data, input text, body)
     - `IRANSansWeb(FaNum)_Light.ttf` (Placeholders, secondary metadata, tooltips)
   - **Persian Numerals (`FaNum`):** Automatically renders all digits in clean Persian digits without manual conversion helpers.
2. **Quranic / Arabic Text:** `AmiriQuran-Regular.ttf` (`assets/fonts/quran/`)
3. **Fallback Font Stack:** `"IRANSansWeb(FaNum)", "IRANSans", "Segoe UI", "Tahoma", sans-serif`

### 2.2 Typographic Scale

| Level | Size (pt / px) | Weight | Line Height | Usage |
| :--- | :--- | :--- | :--- | :--- |
| **Display** | 16pt / 21px | Bold | 28px | Institution header title ("موسسه آموزشی جهت") |
| **Heading 1** | 14pt / 19px | Bold | 24px | Section title ("کتابخانه") |
| **Heading 2** | 12pt / 16px | Medium / Bold | 20px | Table column headers, card titles |
| **Body / Inputs** | 10pt / 13px | Regular | 18px | Table row contents, search inputs, dropdown items |
| **Badge / Caption** | 8.5pt / 11px | Medium | 14px | Status chips ("موجود"), category tags, shortcut badges (`Ctrl+K`) |
| **Micro** | 7.5pt / 10px | Regular | 12px | Footer counts ("۱۰ کتاب"), subtitle slogans |

---

## 3. Layout Anatomy (Based on Screenshot)

```
+---------------------------------------------------------------------------------------------------+
| [User Profile ⌄]                                   [Sub: شتاب‌دهنده آموزش...] [Logo + موسسه آموزشی جهت] |  <- HeaderBar (60px)
+----+------------+---------------------------------------------------------------------------------+
|    | کتابخانه <  | [جستجوی کتاب...]             [فیلتر ⏚]  [دسته‌بندی: همه دسته‌ها ⌄]  [+ افزودن کتاب]   |  <- Action Bar
| [B]| [Search]   +---------------------------------------------------------------------------------+
| [H]|            | [x] # | نام کتاب | دسته‌بندی | نویسنده | قیمت/تعداد | وضعیت | جلد | عملیات           |  <- QTableView
| [U]| کتاب‌ها   |---------------------------------------------------------------------------------|
| [M]| عضویت‌ها  | [ ] 1 | شازده... | داستان    | سنت...  | ۳۵ جلد     | موجود | [img] | [👁] [✏] [︙]   |
| [T]| امانت‌ها  | [ ] 2 | ملت عشق  | رمان      | الیف... | ۲۲ جلد     | امانت | [img] | [👁] [✏] [︙]   |
| [S]| بازگشت‌ها | ...                                                                             |
|    | دسته‌بندی  |---------------------------------------------------------------------------------|
|    | نویسندگان  | [<] [1] [2] [3] [4] [5] [>]                                            [۱۰ کتاب]  |  <- Pagination Bar
| [FA| گزارش‌ها  |                                                                                 |
+----+------------+---------------------------------------------------------------------------------+
 Rail   Sidebar                                Main Content Card
```

### 3.1 App Header (`HeaderBar`)
- **Dimensions:** Height fixed to 60px, width 100%.
- **Background:** Primary gradient (`qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #172B8F, stop:1 #2945D3)`).
- **RTL Right Area:**
  - Institution Vector Emblem / Logo.
  - Title: "موسسه آموزشی جهت" (White, Bold, 15pt).
  - Subtitle: "شتاب دهنده آموزش، فردا متمایز" (Color `#EAF0FF`, Regular, 9pt).
- **RTL Left Area:**
  - User Profile Widget:
    - User circular avatar icon (diameter 36px).
    - Role title: "مدیر کتابخانه" (White, Medium, 10.5pt).
    - Dropdown indicator chevron (`⌄`).
    - Click triggers popup card for current user info, switch user, and logout.

### 3.2 Dual Navigation Shell
1. **Primary Icon Rail (Slim Left Bar):**
   - Width: 52px. Background: `#FFFFFF`. Border-right: `1px solid #E2E8F0`.
   - Top item: Rounded square accent badge (`#FFC400`) with Book Icon.
   - Middle icon actions:
     - Home / Dashboard
     - Members
     - Message / Notifications
     - Loan History / Clock
     - System Settings
   - Bottom item: Language toggle badge ("FA" capsule with green status dot).
2. **Secondary Navigation Drawer (Sub-Sidebar):**
   - Width: 210px. Background: `#FFFFFF`. Border-right: `1px solid #E2E8F0`.
   - Collapsible via toggle button (`<三`).
   - Quick Filter Input: "جستجوی کتاب، نویسنده یا موضوع..." + badge `Ctrl+K`.
   - Menu items with active and hover states:
     - `کتاب‌ها` (Books) -> Active state (`background: #EAF0FF; color: #2945D3; font-weight: bold; border-radius: 8px`).
     - `عضویت‌ها` (Members)
     - `امانت‌ها` (Loans)
     - `بازگشت‌ها` (Returns)
     - `دسته‌بندی‌ها` (Categories / Dewey)
     - `نویسندگان` (Authors / Contributors)
     - `گزارش‌ها` (Reports)

### 3.3 Main Content Area
- **Canvas:** Background `#F7F9FC`, padding 16px.
- **Card Container:** Background `#FFFFFF`, border `1px solid #E2E8F0`, border-radius `12px`.
- **Action & Filter Toolbar:**
  - **Add Book CTA Button (`#FFC400`):**
    - Text: "افزودن کتاب", icon: Book/Plus.
    - Style: Gold background, dark navy text `#172033`, corner-radius `8px`, height `38px`.
  - **Category Filter Dropdown:**
    - `QComboBox` styled with `#FFFFFF` background, border `#E2E8F0`, corner-radius `8px`, height `38px`. Default: "همه دسته‌ها".
  - **Filter Button:**
    - Icon: Funnel (`filter`). Text: "فیلتر".
    - Style: White background, border `1px solid #E2E8F0`, text `#2945D3`, hover `#EAF0FF`.
  - **Main Search Field:**
    - Placeholder: "جستجوی کتاب براساس عنوان، نویسنده یا کد کتاب...".
    - Styled with integrated search icon, clear button (`QLineEdit.TrailingPosition`), height `38px`, border-radius `8px`.
- **Books Table (`QTableView`):**
  - Columns (RTL):
    1. `Selection`: Checkbox (header has master checkbox).
    2. `Index`: `#` (1, 2, 3...).
    3. `Title`: نام کتاب (Bold `#172033`).
    4. `Category`: دسته‌بندی (Pill badge `#EAF0FF`, text `#2945D3`).
    5. `Author`: نویسنده (`#172033`).
    6. `Quantity`: قیمت / تعداد (`#64748B`, e.g. "۳۵ جلد").
    7. `Status`: وضعیت (Capsule badge: "موجود" in green, "در حال امانت" in amber).
    8. `Cover`: Book thumbnail (rounded 4px, 30x42px).
    9. `Actions`: Operations (Eye/View, Pen/Edit, Dots/More).
- **Pagination Footer:**
  - Record Counter: "۱۰ کتاب" / "صفحه ۱ از ۵".
  - Navigation Buttons: `<` Previous, `1` (Active: `#2945D3`, white text), `2`, `3`, `4`, `5`, `>` Next.

---

## 4. PySide6 Architecture & Component Tree

```
bager_library/
├── assets/
│   ├── fonts/iransans/ttf/*.ttf
│   ├── icons/lucide/*.svg
│   └── images/ui/*.png
├── config/
│   └── styles.py               # Palette constants, font loader, master QSS
├── core/
│   ├── app_context.py          # Session, user state, db path
│   └── signals.py              # Global EventBus (tab switch, refresh, alert)
├── models/
│   ├── book_table_model.py     # QAbstractTableModel with sorting/filtering
│   ├── loan_table_model.py
│   └── member_table_model.py
├── views/
│   ├── main_window.py          # QMainWindow holding Header, Rail, Sidebar, Stack
│   ├── components/
│   │   ├── header_bar.py       # Top blue brand header
│   │   ├── icon_rail.py        # 52px slim icon navigation
│   │   ├── nav_sidebar.py      # 210px collapsible menu
│   │   ├── table_delegates.py  # BadgeDelegate, CoverDelegate, ActionButtonsDelegate
│   │   ├── search_bar.py       # QLineEdit with integrated search icon
│   │   ├── pagination_bar.py   # Page numbers & record count
│   │   └── user_popover.py     # User details card dialog
│   ├── tabs/
│   │   ├── books_view.py       # Books dashboard (matches screenshot)
│   │   ├── loans_view.py       # Loans & returns view
│   │   ├── members_view.py     # Member management
│   │   ├── users_view.py       # Admin user management
│   │   └── settings_view.py    # Preferences & notifications
```

---

## 5. Master QSS Specification

```css
/* ==================== Global Application Style ==================== */
QWidget {
    font-family: "IRANSansWeb(FaNum)", "IRANSans", "Segoe UI", "Tahoma";
    font-size: 13px;
    color: #172033;
    background-color: transparent;
    selection-background-color: #2945D3;
    selection-color: #FFFFFF;
}

QMainWindow, QDialog {
    background-color: #F7F9FC;
}

/* ==================== Top Header Bar ==================== */
#AppHeader {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #172B8F, stop:1 #2945D3);
    min-height: 60px;
    max-height: 60px;
    border-bottom: 1px solid #172B8F;
}

#AppHeader QLabel#TitleLabel {
    color: #FFFFFF;
    font-size: 15px;
    font-weight: bold;
}

#AppHeader QLabel#SubtitleLabel {
    color: #EAF0FF;
    font-size: 10px;
}

#AppHeader QToolButton#UserProfileBtn {
    background-color: rgba(255, 255, 255, 0.12);
    color: #FFFFFF;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 18px;
    padding: 4px 14px;
    font-weight: 500;
}

#AppHeader QToolButton#UserProfileBtn:hover {
    background-color: rgba(255, 255, 255, 0.22);
}

/* ==================== Slim Icon Rail ==================== */
#IconRail {
    background-color: #FFFFFF;
    border-right: 1px solid #E2E8F0;
    min-width: 52px;
    max-width: 52px;
}

#IconRail QToolButton {
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 8px;
}

#IconRail QToolButton:hover {
    background-color: #EAF0FF;
}

#IconRail QToolButton#RailBrandIcon {
    background-color: #FFC400;
    border-radius: 10px;
}

/* ==================== Sidebar Navigation ==================== */
#NavSidebar {
    background-color: #FFFFFF;
    border-right: 1px solid #E2E8F0;
    min-width: 210px;
    max-width: 210px;
}

#NavSidebar QPushButton {
    text-align: right;
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 9px 14px;
    font-size: 13px;
    font-weight: 500;
    color: #172033;
}

#NavSidebar QPushButton:hover {
    background-color: #F7F9FC;
    color: #2945D3;
}

#NavSidebar QPushButton[active="true"] {
    background-color: #EAF0FF;
    color: #2945D3;
    font-weight: bold;
}

/* ==================== Buttons & Inputs ==================== */
QPushButton#PrimaryAccentBtn {
    background-color: #FFC400;
    color: #172033;
    border: 1px solid #E5B000;
    border-radius: 8px;
    padding: 8px 18px;
    font-weight: bold;
    font-size: 13px;
}

QPushButton#PrimaryAccentBtn:hover {
    background-color: #FFD033;
}

QPushButton#PrimaryAccentBtn:pressed {
    background-color: #E5B000;
}

QPushButton#OutlineFilterBtn {
    background-color: #FFFFFF;
    color: #2945D3;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 500;
}

QPushButton#OutlineFilterBtn:hover {
    background-color: #EAF0FF;
    border-color: #2945D3;
}

QLineEdit, QComboBox {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 6px 12px;
    color: #172033;
    min-height: 24px;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #2945D3;
    background-color: #FFFFFF;
}

/* ==================== Table Styling ==================== */
QTableView {
    background-color: #FFFFFF;
    gridline-color: #F1F5F9;
    border: none;
    outline: none;
}

QTableView::item {
    padding: 8px 6px;
    border-bottom: 1px solid #F1F5F9;
}

QTableView::item:selected {
    background-color: #EAF0FF;
    color: #172033;
}

QHeaderView::section {
    background-color: #FFFFFF;
    color: #64748B;
    border: none;
    border-bottom: 1px solid #E2E8F0;
    padding: 10px 8px;
    font-weight: bold;
    font-size: 12px;
    text-align: right;
}

/* ==================== Pagination Bar ==================== */
#PaginationBar QPushButton {
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    background-color: #FFFFFF;
    color: #172033;
    font-weight: 500;
}

#PaginationBar QPushButton:hover {
    background-color: #EAF0FF;
    border-color: #2945D3;
    color: #2945D3;
}

#PaginationBar QPushButton[active="true"] {
    background-color: #2945D3;
    color: #FFFFFF;
    border-color: #2945D3;
    font-weight: bold;
}
```

---

## 6. Migration Plan & Strategy

```
Phase 1: Foundation
├── 1. Add PySide6 to requirements.txt & pyproject.toml
├── 2. Create config/styles.py: load IRANSans TTF into QFontDatabase & expose QSS
└── 3. Implement core/signals.py & AppContext

Phase 2: Shell Scaffolding
├── 4. Implement MainWindow (QMainWindow) with Qt.RightToLeft layout
├── 5. Build HeaderBar, IconRail, and NavSidebar
└── 6. Wire collapsible sidebar & profile popover

Phase 3: Books View (Target Screenshot)
├── 7. Create BookTableModel (QAbstractTableModel) consuming existing BookService
├── 8. Build TableDelegates:
│      ├── BadgeDelegate (Category pills & Status pills)
│      ├── ThumbnailDelegate (Book covers)
│      └── ActionButtonsDelegate (View, Edit, More menu)
└── 9. Assemble BooksView toolbar, search, filter, and pagination

Phase 4: Porting Remaining Views
├── 10. Port MembersView, LoansView, and UsersView
└── 11. Port SettingsView and Notification engine integrations

Phase 5: Packaging & Cleanup
├── 12. Update PyInstaller spec for PySide6 plugin bindings
└── 13. Remove CustomTkinter and Tkinter legacy dependencies
```
