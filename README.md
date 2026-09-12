<div align="center">

<img src="logo.ico" width="96" height="96" alt="Bager Library Logo" />

# 📚 سامانه مدیریت کتابخانه باقر العلوم
### Bager Library Management System

**نرم‌افزار دسکتاپ مدرن، آفلاین‌محور و امن برای مدیریت کتاب، اعضا، امانات، هشدارهای سررسید و احراز هویت دومرحله‌ای**

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Version](https://img.shields.io/badge/Version-0.2.2-0284c7?style=for-the-badge)](https://github.com/amirkabir18/bager_library/releases)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/amirkabir18/bager_library)
[![Pytest Suite](https://img.shields.io/badge/Tests-69%20Passed-16a34a?style=for-the-badge&logo=pytest&logoColor=white)](https://github.com/amirkabir18/bager_library)
[![Code Style](https://img.shields.io/badge/Code%20Style-Ruff-black?style=for-the-badge&logo=ruff&logoColor=white)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/badge/License-MIT-amber?style=for-the-badge)](LICENSE)

[English Summary](#-english-overview) • [امکانات سامانه](#-ویژگیهای-کلیدی-و-برجسته) • [راهنمای شروع سریع](#-راهنمای-شروع-سریع-کاربران-و-کتابداران) • [راه‌اندازی توسعه](#-راهنمای-راه‌اندازی-برای-توسعه‌دهندگان) • [تنظیمات و متغیرهای محیطی](#-تنظیمات-و-متغیرهای-محیطی-env) • [توسعه‌دهندگان](#-توسعه‌دهندگان-و-پدیدآورندگان)

---

</div>

## 📖 فهرست مطالب

1. [درباره سامانه](#-درباره-سامانه)
2. [ویژگی‌های کلیدی و برجسته](#-ویژگیهای-کلیدی-و-برجسته)
3. [پشته فنی و معماری فناوری‌ها](#-پشته-فنی-و-معماری-فناوریها)
4. [راهنمای شروع سریع کاربران و کتابداران](#-راهنمای-شروع-سریع-کاربران-و-کتابداران)
5. [راهنمای راه‌اندازی برای توسعه‌دهندگان](#-راهنمای-راه‌اندازی-برای-توسعه‌دهندگان)
6. [دستورات کنترل کیفیت و تست‌ها](#-دستورات-کنترل-کیفیت-و-تستها)
7. [بسته‌بندی و بیلد خروجی ویندوز (PyInstaller)](#-بستهبندی-و-بیلد-خروجی-ویندوز-pyinstaller)
8. [تنظیمات و متغیرهای محیطی (.env)](#-تنظیمات-و-متغیرهای-محیطی-env)
9. [پیکربندی ربات و رله ضد فیلتر تلگرام](#-پیکربندی-ربات-و-رله-ضد-فیلتر-تلگرام)
10. [ساختار درختی پروژه](#-ساختار-درختی-پروژه)
11. [توسعه‌دهندگان و پدیدآورندگان](#-توسعهدهندگان-و-پدیدآورندگان)
12. [مجوز و قدردانی](#-مجوز-و-قدردانی)
13. [English Overview](#-english-overview)

---

## 🌟 درباره سامانه

**سامانه کتابخانه باقر العلوم** یک نرم‌افزار دسکتاپ مدرن و بهینه‌سازی‌شده برای مدیریت کتابخانه‌های عمومی، تخصصی، مدارس، مساجد و مراکز پژوهشی است. این پروژه با هدف حذف وابستگی‌های سنگین اینترنتی و ارائه یک سیستم **کاملاً آفلاین، سریع، سبک و امن** طراحی گردیده است.

در عین حال، در صورت دسترسی به اینترنت، قابلیت‌های ابری مفیدی همچون **ارسال کدهای ورود یکبار مصرف (OTP) به تلگرام از طریق رله‌های اختصاصی ضد تحریم/فیلتر** و **سامانه به‌روزرسانی خودکار و اتمیک از طریق گیت‌هاب** به سادگی فعال می‌شوند.

---

## 🚀 ویژگی‌های کلیدی و برجسته

### 🎨 ۱. رابط کاربری مدرن، زیبا و بومی فارسی
- پیاده‌سازی‌شده بر پایه **CustomTkinter** با پشتیبانی از حالت‌های تاریک (Dark Mode)، روشن (Light Mode) و پیرو سیستم.
- لود خودکار و بی‌نقص قلم محبوب **IRANSans** در ویندوز از طریق فراخوانی مستقیم Windows GDI32 API (`AddFontResourceExW`).
- چیدمان استاندارد راست‌چین (RTL) به همراه اصلاح و نمایش ارقام فارسی (`۰-۹`).
- استفاده از آیکون‌های مدرن Lucide به همراه بهینه‌سازی رنگ و شفافیت برای هر تم.

### 📚 ۲. مدیریت پیشرفته مخزن کتاب‌ها
- ثبت، ویرایش، حذف و نمایش شناسنامه کامل کتاب‌ها (عنوان، پدیدآورنده/نویسنده، شابک یا ISBN).
- سیستم جستجوی بلادرنگ با فیلترهای منعطف:
  - جستجو در تمام فیلدها یا فیلد اختصاصی.
  - فیلتر بر اساس وضعیت در دسترس بودن (امانت داده شده / موجود در کتابخانه).
  - حالت‌های انطباق (شامل بودن، انطباق دقیق، شروع با عبارت).
  - مرتب‌سازی بر اساس ستون‌های مختلف به صورت صعودی و نزولی.

### 👥 ۳. مدیریت اعضا و کاربران کتابخانه
- تشکیل پرونده اعضا با شناسه یکتا و شماره تماس نرمال‌سازی‌شده.
- تشخیص خودکار الگوهای مختلف شماره تلفن‌های ایرانی (`+98`, `0098`, `09...`).
- سیستم کنترل سطح دسترسی و کاربران سامانه با نقش‌های **Super Admin**، **Admin** و **Librarian (کتابدار)**.

### 🔄 ۴. چرخه امانت و گردش کتاب (Circulation)
- ثبت هوشمند امانت و اتصال پویای عضو و کتاب با تکمیل خودکار (Autocomplete).
- پشتیبانی کامل از **تقویم خورشیدی / جلالی (Shamsi Calendar)** با کتابخانه `jdatetime`.
- ثبت و محاسبه دقیق تاریخ امانت و موعد بازگشت.
- تسویه سریع و ثبت برگشت کتاب تنها با یک کلیک یا میانبر دابل‌کلیک.
- امکان ثبت یادداشت، تمدید و فیلتر کتاب‌های سررسیدشده یا در امانت.

### 🔔 ۵. سامانه اعلان‌ها و هشدارهای سررسید (Desktop Push Notifications)
- **موتور اعلان ۱۰۰٪ آفلاین:** بدون نیاز به اینترنت، هشدارهای سررسید را به کاربر نمایش می‌دهد.
- **اعلان‌های بومی ویندوز ۱۰ و ۱۱:** ادغام مستقیم با Action Center ویندوز از طریق `winotify` به همراه آیکون سامانه و صدای زنگ هشدار.
- **پاپ‌آپ شناور اختصاصی (Fallback):** نمایش پنجره شناور در گوشه صفحه در صورت عدم در دسترس بودن نوتیفیکیشن ویندوز.
- **دیمن پس‌زمینه (Background Daemon):** پایش خودکار وضعیت امانات در بازه‌های زمانی قابل تنظیم (۱۵، ۳۰، ۶۰، ۱۲۰ دقیقه).
- **دسته‌بندی هوشمند وضعیت:**
  - هشدارهای نزدیک به سررسید (Due Soon - ۱ تا ۷ روز قبل).
  - هشدارهای موعد امروز (Due Today).
  - هشدارهای دیرکرد و جریمه (Overdue).
- **دفتر ثبت و لاگ اعلان‌ها (Audit Logs):** ثبت تاریخچه تمام هشدارهای ارسال‌شده، جلوگیری از ارسال تکراری در یک روز و امکان جستجو و فیلتر گزارش‌ها.

### 🔐 ۶. امنیت، احراز هویت دومرحله‌ای و ورود اضطراری
- هش کردن کلمات عبور با استاندارد **PBKDF2-HMAC-SHA256** با **۱۰۰٬۰۰۰ دور تکرار** و نمک تصادفی (Cryptographic Salt).
- ارسال کد یکبار مصرف ۶ رقمی امن (OTP) به حساب تلگرام کاربر با زمان اعتبار ۲ دقیقه‌ای و محدودیت نرخ درخواست (Rate Limiting).
- مکانیزم اعتبارسنجی آفلاین مدیر سیستم در زمان‌های قطعی شبکه یا اختلالات اینترنت.
- راه‌اندازی خودکار کاربر ریشه سیستم (Bootstrap Admin) در اولین اجرا.

### 🛡 ۷. رله اختصاصی تلگرام ضد فیلترینگ (Serverless Relays)
- شامل کدهای آماده و سبک سرورلس برای عبور امن از فیلترینگ تلگرام:
  - **Cloudflare Worker** (`relays/cloudflare/worker.js`)
  - **Vercel Edge Function** (`relays/vercel/api/telegram.js`)
- محافظت‌شده با توکن امنیتی اختصاصی `X-Relay-Secret` برای ممانعت از سوءاستفاده عمومی.

### ⚡ ۸. سیستم به‌روزرسانی خودکار و اتمیک (Auto-Updater)
- بررسی انتشار نسخه‌های جدید در GitHub Releases به همراه فال‌بک به متادیتای مخزن.
- دانلود جریانی چندبخشی (Chunked Streaming) با نمایش نوار پیشرفت زنده، سرعت دانلود و زمان تخمینی باقیمانده.
- جایگزینی اتمیک و امن فایل اجرایی فعال در ویندوز از طریق اسکریپت رانر مستقل موقت بدون ایجاد اختلال در داده‌ها.

### 💾 ۹. ذخیره‌سازی داده‌های مستقل و حالت پرتابل (Portable Mode)
- پایگاه داده سبک و با کارایی بالای **SQLite3** با فعال‌سازی خودکار Foreign Keys، ایندکس‌های بهینه‌ساز و تراکنش‌های امن.
- **رفتار خودکار پرتابل:** نرم‌افزار ابتدا سعی می‌کند دیتابیس `bager_library.db` را در کنار فایل اجرایی ایجاد کند (مناسب فلش‌مموری و سیستم‌های متحرک). در صورت نداشتن مجوز نوشتن (مانند پوشه Program Files)، فایل‌ها به صورت استاندارد در `%LOCALAPPDATA%/bager_library` ذخیره می‌شوند.

---

## 🛠 پشته فنی و معماری فناوری‌ها

```
┌──────────────────────────────────────────────────────────────┐
│                    Bager Library Desktop                     │
│         CustomTkinter GUI • RTL Layout • IRANSans Font       │
├──────────────────────────────┬───────────────────────────────┤
│         Core Logic           │          Data & Sync          │
│ • main.py (UI & Controllers) │ • database.py (SQLite & Migr) │
│ • auth.py (PBKDF2 & OTP)     │ • notifications.py (winotify) │
│ • updater.py (GitHub Stream) │ • jdatetime (Shamsi Calendar) │
└──────────────┬───────────────┴───────────────┬───────────────┘
               │                               │
        [Offline Mode]                  [Online Services]
   • Local SQLite Database          • GitHub Releases API
   • Windows Action Center          • Telegram Bot via Relays
   • Encrypted Password Auth          (Cloudflare / Vercel Edge)
```

| حوزه | تکنولوژی / کتابخانه | هدف و کاربرد |
| :--- | :--- | :--- |
| **زبان و محیط اجرا** | Python 3.10+ | زبان اصلی توسعه پروژه |
| **رابط کاربری دسکتاپ** | CustomTkinter + Tkinter ttk | طراحی مدرن، پشتیبانی از تم تاریک و المان‌های تعاملی |
| **قلم و گرافیک** | IRANSans + Pillow (PIL) + Lucide | تایپوگرافی اصیل فارسی و آیکون‌های وکتور بهینه‌شده |
| **پایگاه داده** | SQLite3 | پایگاه داده مستقل، بدون نیاز به سرور و با مهاجرت خودکار |
| **تقویم و زمان** | `jdatetime` | مدیریت دقیق تاریخ و تبدیل‌های هجری شمسی (جلالی) |
| **اعلان‌های دسکتاپ** | `winotify` | ارسال نوتیفیکیشن‌های استاندارد ویندوز ۱۰ و ۱۱ به صورت آفلاین |
| **امنیت و احراز هویت** | `hashlib` (PBKDF2-SHA256) + OTP | ذخیره‌سازی امن رمز و احراز هویت دوعاملی تلگرامی |
| **پروکسی و رله** | Cloudflare Workers / Vercel Edge | دور زدن محدودیت‌های تلگرام با توکن امنیتی اختصاصی |
| **بسته‌بندی اجرایی** | PyInstaller | کامپایل و تولید خروجی اجرایی مستقل ویندوز (`.exe`) |
| **کنترل کیفیت** | Ruff + Pytest | اعتبارسنجی استانداردهای کدنویسی و آزمون‌های خودکار |

---

## 📥 راهنمای شروع سریع کاربران و کتابداران

اگر قصد استفاده از نرم‌افزار را دارید و نیازی به کدنویسی یا تغییر سورس ندارید:

1. به بخش [GitHub Releases](https://github.com/amirkabir18/bager_library/releases) بروید.
2. آخرین نسخه فشرده `bager_library-windows-x64.zip` یا فایل اجرایی تک‌فایل `bager_library.exe` را دانلود کنید.
3. فایل را از حالت فشرده خارج کرده و برنامه `bager_library.exe` را اجرا نمایید.
4. **اطلاعات ورود اولیه (Bootstrap Super Admin):**
   - **نام کاربری:** `admin`
   - **رمز عبور:** `admin1234`
   - **شماره تماس:** `09120000000`
5. پس از ورود اولیه، می‌توانید از تب **تنظیمات و کاربران** رمز عبور را تغییر داده، کاربران و کتابداران جدید تعریف کرده و ربات تلگرام را برای دریافت کدهای ورود متصل کنید.

---

## 💻 راهنمای راه‌اندازی برای توسعه‌دهندگان

### پیش‌نیازها
- سیستم‌عامل **ویندوز ۱۰ یا ۱۱** (به دلیل وابستگی به توابع نوتیفیکیشن و فونت GDI32).
- **پایتون نسخه 3.10 یا بالاتر** (نصب‌شده به همراه افزودن به PATH).
- ابزار **Git**.

### ۱. کلون مخزن
```bash
git clone https://github.com/amirkabir18/bager_library.git
cd bager_library
```

### ۲. ساخت و فعال‌سازی محیط مجازی (Virtual Environment)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### ۳. نصب وابستگی‌های اجرایی و توسعه
```powershell
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### ۴. اجرای نرم‌افزار
```powershell
python main.py
```

---

## 🧪 دستورات کنترل کیفیت و تست‌ها

این پروژه دارای مجموعه جامع ۶۹ آزمون واحد و یکپارچگی است که بخش‌های احراز هویت، تقویم شمسی، دیتابیس، مهاجرت‌ها، اعلان‌ها و به‌روزرسانی را پوشش می‌دهند.

### اجرای آزمون‌ها (Pytest)
```powershell
python -m pytest -v
```

### اعتبارسنجی و بررسی قواعد کدنویسی (Ruff Lint)
```powershell
python -m ruff check .
```

### فرمت‌بندی خودکار کدها بر اساس استانداردهای مدرن
```powershell
python -m ruff format .
```

---

## 📦 بسته‌بندی و بیلد خروجی ویندوز (PyInstaller)

این مخزن شامل کانفیگ کامل `bager_library.spec` و تسک‌های آماده برای ویژوال استودیو کد (`.vscode/tasks.json`) است.

### ساخت فایل اجرایی تک‌فایل (Single-file Executable)
```powershell
pyinstaller --noconfirm --onefile --windowed --name bager_library --icon logo.ico --add-data "assets;assets" --add-data "logo.ico;." --add-data "app_info.json;." --hidden-import jdatetime --hidden-import dotenv main.py
```

### ساخت نسخه پوشه‌ای به همراه فایل زیپ خروجی (Onedir + Zip)
```powershell
# مرحله ۱: ساخت دایرکتوری توزیع
pyinstaller --noconfirm --onedir --windowed --name bager_library --icon logo.ico --add-data "assets;assets" --add-data "logo.ico;." --add-data "app_info.json;." --hidden-import jdatetime --hidden-import dotenv main.py

# مرحله ۲: فشرده‌سازی برای انتشار در گیت‌هاب
powershell -NoProfile -Command "Compress-Archive -Path 'dist/bager_library' -DestinationPath 'dist/bager_library-windows-x64.zip' -Force"
```

> **نکته:** در صورت باز بودن پروژه در VS Code، می‌توانید مستقیماً از منوی **Terminal > Run Task** تسک‌های `build exe` یا `build onedir:zip` را بدون نیاز به تایپ دستورات طولانی اجرا کنید.

---

## ⚙️ تنظیمات و متغیرهای محیطی (.env)

سامانه می‌تواند از طریق ایجاد یک فایل با نام `.env` در مسیر برنامه، یا از طریق متغیرهای محیطی سیستم‌عامل، پیکربندی گردد:

| نام متغیر | مقدار پیش‌فرض | توضیحات کاربردی |
| :--- | :--- | :--- |
| `BAGER_DATA_DIR` | خودکار (مسیر برنامه یا AppData) | مسیر پوشه ذخیره‌سازی فایل‌های پایگاه داده و گزارش‌ها |
| `BAGER_DB_PATH` | `{BAGER_DATA_DIR}/bager_library.db` | آدرس دقیق فایل دیتابیس SQLite |
| `SUPER_ADMIN_USERNAME` | `admin` | نام کاربری مدیر ارشد در هنگام بارگذاری اولیه |
| `SUPER_ADMIN_PASSWORD` | `admin1234` | رمز عبور مدیر ارشد در هنگام بارگذاری اولیه |
| `SUPER_ADMIN_PHONE` | `09120000000` | شماره همراه مدیر ارشد جهت دریافت کد OTP |
| `TELEGRAM_BOT_TOKEN` | _خالی_ | توکن ربات تلگرام دریافتی از @BotFather |
| `TELEGRAM_RELAY_URL` | _خالی_ | آدرس URL ورکر کلودفلر یا ورسل جهت رله درخواست‌ها |
| `TELEGRAM_RELAY_SECRET` | _خالی_ | رمز عبور هدر `X-Relay-Secret` جهت برقراری امنیت رله |
| `TELEGRAM_PROXY` | _خالی_ | پروکسی محلی (مثلاً `http://127.0.0.1:10809`) در صورت نیاز |

---

## 🤖 پیکربندی ربات و رله ضد فیلتر تلگرام

اگر می‌خواهید کدهای ورود به صورت خودکار به تلگرام پرسنل و کتابداران ارسال شود:

### ۱. ساخت ربات تلگرام
1. در تلگرام به ربات رسمی [@BotFather](https://t.me/BotFather) پیام دهید.
2. با دستور `/newbot` یک ربات جدید بسازید و توکن اختصاصی دریافتی را کپی کنید.

### ۲. استقرار رله معکوس (جهت دور زدن مسدودی در ایران)

#### روش الف: Cloudflare Workers (توصیه‌شده و رایگان)
1. به پنل [Cloudflare Dashboard](https://dash.cloudflare.com/) وارد شده و به بخش **Workers & Pages** بروید.
2. یک ورکر جدید ایجاد کنید و محتویات فایل `relays/cloudflare/worker.js` را در ویرایشگر آن قرار دهید.
3. در تب **Settings > Variables** یک متغیر محرمانه با نام `RELAY_SECRET` و مقداری دلخواه و طولانی تعریف کنید.
4. ورکر را Deploy کرده و دامنه تولیدشده (مانند `https://my-tg-relay.subdomain.workers.dev`) را به همراه سکرت در برنامه وارد نمایید.

#### روش ب: Vercel Edge Function
1. مخزن را در [Vercel](https://vercel.com/) ایمپورت کنید (پیکربندی در `relays/vercel/` قرار دارد).
2. در تنظیمات پروژه Vercel متغیر `RELAY_SECRET` را اضافه نمایید.
3. آدرس سرویس منتشرشده را به عنوان رله معرفی نمایید.

### ۳. اتصال کاربر به ربات
1. کاربر مورد نظر به ربات در تلگرام رفته و دکمه `/start` را می‌زند.
2. با فشردن دکمه **«📱 ارسال شماره تماس برای اتصال»**، شماره خود را با ربات به اشتراک می‌گذارد.
3. سامانه به طور خودکار شماره را با جدول کاربران تطبیق داده و شناسه تلگرام را متصل می‌کند.

---

## 📂 ساختار درختی پروژه

```text
bager_library/
├── main.py                     # هسته اجرایی و کنترلر رابط کاربری گرافیکی
├── database.py                 # لایه تعامل با SQLite، اسکیما و مایگریشن‌ها
├── auth.py                     # رمزنگاری PBKDF2، سرویس OTP و ارتباط با تلگرام
├── notifications.py            # موتور اعلان آفلاین ویندوز و دیمن پایش امانات
├── updater.py                  # ماژول بررسی، دانلود جریانی و آپدیت اتمیک
├── app_info.json               # متادیتای شناسه نرم‌افزار، نام و شماره نسخه
├── bager_library.spec          # فایل تنظیمات و مشخصات کامپایل با PyInstaller
├── pyproject.toml              # پیکربندی استانداردهای Ruff و Pytest
├── requirements.txt            # پیش‌نیازهای اجرای نرم‌افزار
├── requirements-dev.txt        # پیش‌نیازهای محیط تست، لینت و بسته‌بندی
├── logo.ico                    # نشان‌واره و آیکون اصلی نرم‌افزار
│
├── assets/                     # دارایی‌های چندرسانه‌ای
│   ├── fonts/iransans/         # قلم فارسی ایران‌سنس (فرمت‌های TTF و وب)
│   ├── icons/lucide/           # آیکون‌های وکتور مدرن Lucide و اسکریپت ساخت
│   └── images/                 # تصاویر پیش‌نمایش و راهنمای برنامه
│
├── relays/                     # سرورلس‌های رله ضد تحریم/فیلتر تلگرام
│   ├── cloudflare/worker.js    # اسکریپت رله بر بستر Cloudflare Workers
│   └── vercel/                 # اسکریپت رله بر بستر Vercel Edge Functions
│
├── tests/                      # مجموعه آزمون‌های جامع واحد و یکپارچگی
│   ├── test_auth.py            # تست توابع امنیتی، هشینگ و سرویس OTP
│   ├── test_database.py        # تست ساخت پایگاه داده و مهاجرت جداول
│   ├── test_notifications.py   # تست موتور اعلان و زمان‌بندی یادآوری
│   ├── test_settings.py        # تست کلیدهای تنظیمات و فیلتر لاگ‌ها
│   └── test_updater.py         # تست نسخه، مقایسه سمانتیک و دانلودر
│
└── .vscode/tasks.json          # تسک‌های آماده VS Code برای تست، لینت و بیلد
```

---

## 👥 توسعه‌دهندگان و پدیدآورندگان

این سامانه با عشق و تعهد به ارتقای زیرساخت‌های نرم‌افزاری بومی توسط تیم توسعه زیر طراحی و پیاده‌سازی شده است:

* **امیرحسین اسدی** — [GitHub: @amirkabir18](https://github.com/amirkabir18)
* **سید محمد حسن موسوی** — [GitHub: @Aliomosavi](https://github.com/Aliomosavi)
* **امیررضا یونس‌زاده شیرازی** — [GitHub: @ARUSH221617](https://github.com/ARUSH221617)

برای گزارش باگ‌ها، ارائه نظرات یا ارسال قابلیت‌های جدید، خوشحال می‌شویم از بخش [ثبت گزارش خطا یا پیشنهاد (New Issue)](https://github.com/amirkabir18/bager_library/issues/new) با ما در ارتباط باشید.

---

## 📄 مجوز و قدردانی

- این نرم‌افزار تحت مجوز [MIT License](LICENSE) منتشر شده است و استفاده شخصی یا تجاری از آن آزاد می‌باشد.
- تشکر ویژه از جامعه متن‌باز برای ارائه ابزارهای فوق‌العاده نظیر **CustomTkinter**، **Lucide Icons** و کتابخانه تقویم جلالی **jdatetime**.

---

<div id="-english-overview"></div>

## 🌐 English Overview

### Bager Library Management System

**Bager Library** is an elegant, modern, offline-first library automation desktop application tailored for schools, mosques, cultural institutions, and community libraries.

#### Key Highlights
- **100% Offline Capability:** Powered by an embedded SQLite database with automatic migrations, indexes, and portable mode support.
- **Modern Persian GUI:** Crafted with CustomTkinter, supporting Dark/Light themes, fully RTL layout, and dynamic Windows GDI32 loading of the IRANSans font.
- **Solar Hijri (Jalali) Calendar:** Comprehensive loan and circulation tracking utilizing `jdatetime`.
- **Offline Push Notifications:** Native Windows 10/11 Action Center toast integration via `winotify` with sound and logo, complemented by a floating popup fallback.
- **Enterprise-Grade Security:** PBKDF2-HMAC-SHA256 password hashing (100k rounds) combined with Telegram OTP 2-Factor Authentication and offline admin emergency override.
- **Built-in Telegram Anti-Censorship Relays:** Ready-to-deploy serverless edge proxies for Cloudflare Workers and Vercel.
- **Resilient Auto-Update:** Semantic version comparison against GitHub Releases, chunked background downloads with ETA/speed indicators, and atomic in-place Windows executable swapping.
- **Comprehensive Test Suite:** 69 unit and integration tests passing with Pytest.

#### Developer Quickstart
```bash
# 1. Clone repository
git clone https://github.com/amirkabir18/bager_library.git
cd bager_library

# 2. Setup virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Run tests & launch application
python -m pytest -v
python main.py
```
