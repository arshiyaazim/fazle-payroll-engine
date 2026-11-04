# Fazle Payroll Engine — Standalone Installation Guide

বাংলা সংস্করণ নিচে দেওয়া আছে।

---

## English Version

### 1. What this is

Fazle Payroll Engine (FPE) is a WhatsApp-based payroll processing module. It can now run as a **standalone FastAPI service** without the full fazle-core host application.

All configuration values are read from `.env` — nothing is hard-coded. The app adjusts to whatever endpoints you provide.

### 2. External apps you need (and how to install)

| App | Purpose | Required? | Install command (Ubuntu/Debian) |
|-----|---------|-----------|---------------------------------|
| Python 3.11+ | Runtime | ✅ Yes | `sudo apt install python3.11 python3.11-venv python3.11-dev` |
| PostgreSQL | Database (stores `fpe_*` tables) | ✅ Yes | `sudo apt install postgresql postgresql-contrib` |
| Ollama | AI enhancement for low-confidence parses | ⚠️ Optional | See below |
| WhatsApp Bridge (bridge1/bridge2) | Cash/Income command WhatsApp replies | ⚠️ Optional | Provided by fazle-core infra |

#### PostgreSQL

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql

# Create a database and user for FPE
sudo -u postgres psql -c "CREATE DATABASE fazle_payroll;"
sudo -u postgres psql -c "CREATE USER azim WITH PASSWORD 'azim';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE fazle_payroll TO azim;"
```

Your `DATABASE_URL` will be:
```
postgresql+asyncpg://azim:azim@localhost:5432/fazle_payroll
```

#### Ollama (optional)

Only needed if you want AI-powered enhancement of low-confidence WhatsApp message parses.

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &   # or run as a system service
ollama pull hermes3:3b   # or whatever model you set in OLLAMA_MODEL
```

If you do not run Ollama, set `OLLAMA_URL` to an unreachable address in `.env` — AI enhancement will silently be skipped.

#### WhatsApp Bridge (optional)

Only needed if you want the engine to send WhatsApp replies for Cash/Income commands. The bridge is part of the fazle-core infrastructure and is **not** bundled with this repo.

If you do not have a bridge, leave `BRIDGE1_URL` and `BRIDGE2_URL` pointing to unreachable addresses — `send()` will return `False` and accounting will not be affected.

### 3. Install the package

```bash
# Clone the repo
git clone https://github.com/arshiyaazim/fazle-payroll-engine.git
cd fazle-payroll-engine
git checkout arena/dcbbab47-fazle-payroll-engine

# Create a virtual environment (recommended)
python3.11 -m venv venv
source venv/bin/activate

# Install the package (includes shim layer for standalone mode)
pip install -e .

# Install test dependencies (optional)
pip install pytest
```

### 4. Configure

```bash
cp .env.example .env
# Edit .env with your DATABASE_URL and INTERNAL_API_KEY at minimum
nano .env
```

**Required `.env` values:**
- `DATABASE_URL` — your PostgreSQL connection string
- `INTERNAL_API_KEY` — secret key for `X-Internal-Key` auth

**Optional `.env` values:**
- `OLLAMA_URL`, `OLLAMA_MODEL`
- `BRIDGE1_URL`, `BRIDGE2_URL`
- `FPE_CASH_AUTHORIZED_PHONES`, `FPE_INCOME_AUTHORIZED_PHONES`
- `FPE_SYNC_CHAT_JIDS`, `ACCOUNTANT_PHONE`
- `APP_PORT`, `LOG_LEVEL`, `DEBUG`

### 5. Run

```bash
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8200
```

The service will:
1. Connect to PostgreSQL via `DATABASE_URL`
2. Run idempotent migrations (`fpe_*` tables) automatically at startup
3. Start background workers (message processor, accounting, historical sync, gap scan)
4. Expose all `/api/fpe/*` endpoints

### 6. Verify it works

```bash
# Health check
curl http://localhost:8200/health

# Ingest a test message (replace INTERNAL_API_KEY)
curl -X POST http://localhost:8200/api/fpe/ingest \
  -H "X-Internal-Key: your-internal-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "wa_message_id": "test-001",
    "source": "meta",
    "source_number": "8801725494969",
    "chat_jid": "8801725494969@s.whatsapp.net",
    "sender_phone": "01725494969",
    "is_from_me": true,
    "raw_content": "Mainuddin 01933689128(B) 1500/-",
    "media_type": null,
    "timestamp_wa": "2026-11-05T10:00:00Z"
  }'
```

Expected response: `{"status": "ingested", "fpe_wa_message_id": <id>}`

### 7. Run tests

```bash
source venv/bin/activate
pytest tests/ -v
```

Expected: `69 passed`

---

## বাংলা সংস্করণ (Bengali)

### ১. এটি কী?

ফাজল-পে রোল ইঞ্জিন (FPE) একটি হাত্সঅ্যাপ-ভিত্তিক পে রোল প্রসেসিং মডিউল। এখন এটি ফাজল-কোর হোস্ট অ্যাপ্লিকেশন ছাড়াও একটি **স্ট্যান্ডঅ্যালোন ফাস্টএপিআই সার্ভিস** হিসেবে চলে।

সব কনফিগারেশন ভ্যালু `.env` ফাইল থেকে পড়া হয় — কোডে কিছু হার্ডকোড নেই। অ্যাপ আপনার দেওয়া এন্ডপয়েন্টের সাথে খাপ খেয়ে নেবে।

### ২. প্রয়োজনীয় বাহ্যিক অ্যাপ ও deren ইনস্টলেশন

| অ্যাপ | উদ্দেশ্য | প্রয়োজন? | ইনস্টলেশন কমান্ড (উবুন্টু/ডেবিয়ান) |
|-----|---------|-----------|---------------------------------|
| Python 3.11+ | রানটাইম | ✅ হ্যাঁ | `sudo apt install python3.11 python3.11-venv python3.11-dev` |
| PostgreSQL | ডাটাবেস (`fpe_*` টেবিল সংরক্ষণ) | ✅ হ্যাঁ | `sudo apt install postgresql postgresql-contrib` |
| Ollama | লো-কনফিডেন্স পার্সের জন্য AI এনহ্যান্সমেন্ট | ⚠️ আচ্ছাল্পক | নিচে দেখুন |
| WhatsApp Bridge (bridge1/bridge2) | ক্যাশ/ইনকম কমান্ডের জন্য হাত্সঅ্যাপ রিপ্লাই | ⚠️ আচ্ছাল্পক | ফাজল-কোর ইনফ্রাস্ট্রাকচার থেকে পাওয়া যায় |

#### PostgreSQL ইনস্টলেশন

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql

# ডাটাবেস ও ইউজার তৈরি
sudo -u postgres psql -c "CREATE DATABASE fazle_payroll;"
sudo -u postgres psql -c "CREATE USER azim WITH PASSWORD 'azim';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE fazle_payroll TO azim;"
```

আপনার `DATABASE_URL` হবে:
```
postgresql+asyncpg://azim:azim@localhost:5432/fazle_payroll
```

#### Ollama ইনস্টলেশন (আচ্ছাল্পক)

শুধু লো-কনফিডেন্স হাত্সঅ্যাপ মেসেজ পার্সের AI এনহ্যান্সমেন্টের জন্য প্রয়োজন।

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &   # অথবা সিস্টেম সার্ভিস হিসেবে চালান
ollama pull hermes3:3b   # অথবা আপনার OLLAMA_MODEL এ সেট করা যেকোনো মডেল
```

আপনি যদি Ollama চাল না থাকেন, তবে `.env`-এ `OLLAMA_URL`-কে অপৌঁছانے ঠিকানায় সেট করুন — AI এনহ্যান্সমেন্ট নীরবে স্কিপ হয়ে যাবে।

#### WhatsApp Bridge (আচ্ছাল্পক)

শুধু তখন প্রয়োজন যদি ইঞ্জিন ক্যাশ/ইনকম কমান্ডের জন্য হাত্সঅ্যাপ রিপ্লাই পাঠাতে চান। ব্রিজটি ফাজল-কোর ইনফ্রাস্ট্রাকচারের অংশ এবং এই রেপোতে বান্ডেলড নেই।

আপনার ব্রিজ না থাকলে, `BRIDGE1_URL` এবং `BRIDGE2_URL` অপৌঁছانے ঠিকানারそうそう রেখে দিন — `send()` ফলস রিটার্ন করবে এবং অ্যাকাউন্টিংে কোনো প্রভাব পড়বে না।

### ৩. প্যাকেজ ইন্সটলেশন

```bash
# রেপো ক্লোন করুন
git clone https://github.com/arshiyaazim/fazle-payroll-engine.git
cd fazle-payroll-engine
git checkout arena/dcbbab47-fazle-payroll-engine

# ভার্চুয়াল এনভিরনমেন্ট তৈরি (শিফারিশকৃত)
python3.11 -m venv venv
source venv/bin/activate

# প্যাকেজ ইন্সটল করুন (স্ট্যান্ডঅ্যালোন মোডের শিম লেয়ারসহ)
pip install -e .

# টেস্ট ডিপেন্ডেনশি ইন্সটল করুন (আচ্ছাল্পক)
pip install pytest
```

### ৪. কনফিগার করুন

```bash
cp .env.example .env
# কমপক্ষে DATABASE_URL এবং INTERNAL_API_KEY এডিট করুন
nano .env
```

**প্রয়োজনীয় `.env` ভ্যালু:**
- `DATABASE_URL` — আপনার পোস্টগ্রესকണকশন স্ট্রিং
- `INTERNAL_API_KEY` — `X-Internal-Key` অথেন্টিকেশনের জন্য গোপন কী

**আচ্ছাল্পক `.env` ভ্যালু:**
- `OLLAMA_URL`, `OLLAMA_MODEL`
- `BRIDGE1_URL`, `BRIDGE2_URL`
- `FPE_CASH_AUTHORIZED_PHONES`, `FPE_INCOME_AUTHORIZED_PHONES`
- `FPE_SYNC_CHAT_JIDS`, `ACCOUNTANT_PHONE`
- `APP_PORT`, `LOG_LEVEL`, `DEBUG`

### ৫. চালান

```bash
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8200
```

সার্ভিসটি হবে:
1. `DATABASE_URL` দিয়ে পোস্টগ্রেসের সাথে কানেক্ট
2. স্টার্টআপে আইডিমপটেন্টマイগ্রেশন (`fpe_*` টেবিল) আটোমেটিক রান
3. ব্যাকগ্রাউন্ড ওয়ার্কার শুরু (মেসেজ প্রসেসর, অ্যাকাউন্টিং, হিস্টোরিক্যাল সিঙ্ক, গ্যাপ স্ক্যান)
4. সব `/api/fpe/*` এন্ডপয়েন্ট এক্সপোজ

### ৬. যাচাই করুন এটি কাজ করছে কিনা

```bash
# হেলথ চেক
curl http://localhost:8200/health

# টেস্ট মেসেজ ইনজেস্ট করুন (INTERNAL_API_KEY রিপ্লেস করুন)
curl -X POST http://localhost:8200/api/fpe/ingest \
  -H "X-Internal-Key: your-internal-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "wa_message_id": "test-001",
    "source": "meta",
    "source_number": "8801725494969",
    "chat_jid": "8801725494969@s.whatsapp.net",
    "sender_phone": "01725494969",
    "is_from_me": true,
    "raw_content": "Mainuddin 01933689128(B) 1500/-",
    "media_type": null,
    "timestamp_wa": "2026-11-05T10:00:00Z"
  }'
```

অপেক্ষিত রেসপন্স: `{"status": "ingested", "fpe_wa_message_id": <id>}`

### ৭. টেস্ট চালান

```bash
source venv/bin/activate
pytest tests/ -v
```

অপেক্ষিত: `69 passed`

---

## ওয়ার্কফ্লো সারসংক্ষেপ (Workflow summary)

1. **ইনজেস্ট:** WhatsApp মেসেজ `POST /api/fpe/ingest` এর মাধ্যমেinside আসে → `fpe_wa_messages` টেবিলে সংরক্ষিত → পেন্ডিং প্রসেসিং স্টেট তৈরি।
2. **পার্সিং:** ব্যাকগ্রাউন্ড ওয়ার্কার রেগুলার এক্সপ্রেশন দিয়ে মেসেজ পার্স করে (পেনমেন্ট/ব্যালান্স সামারি/ক্যাশ-ইনকম কমান্ড)। কনফিডেন্স কম হলে Ollama ঠিক করতে চেষ্টা করে।
3. **অ্যাকাউন্টিং:**Employer মামলানো হলে ট্রানজাকশন `fpe_cash_transactions`-এ তৈরি হয়, লিডGER আপডেট হয়।
4. **রিভিউ কিউ:** মেসেজ মেলাতে না পারলে `fpe_unmatched_messages`-এ চলে যায়, যেখানে এডমিন থেকে প্রমোট/ডিসমিস করা যায়।
5. **সিঙ্ক:** 歴史ical সিংক ও গ্যাপ-स्कैन ব্রিজের সিকিউলাইট থেকে মিসিং মেসেজ ব্যাকফিল করে।

সব এন্ডপয়েন্ট `X-Internal-Key` হেডার দিয়ে প্র强制 অথেনটিকেটেড।
