# 🧪 Data Science Copilot — Project Guide

**An AI-powered web application for interactive data analysis, visualization, and transformation**

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Technology Stack](#technology-stack)
4. [Project Structure](#project-structure)
5. [Installation & Setup](#installation--setup)
6. [User Guide](#user-guide)
7. [Developer Guide](#developer-guide)
8. [Database Schema](#database-schema)
9. [API Reference](#api-reference)
10. [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

Data Science Copilot is a full-stack web application that allows users to interact with their CSV datasets using natural language. The application leverages AI to understand user intent and automatically generate Python code for data operations, visualizations, and transformations.

**Key Capabilities:**
- 📊 **Display**: Query and view data using natural language
- 📈 **Visualize**: Generate charts and plots by describing them
- ✏️ **Modify**: Transform datasets with automatic code generation
- 💬 **Chat**: Ask questions about your data
- ↩️ **Undo**: Revert changes with backup system

---

## ✨ Features

### Authentication & User Management
- ✅ Secure user registration and login
- ✅ JWT token-based authentication
- ✅ Password hashing with bcrypt
- ✅ Per-user data isolation

### Data Operations
- ✅ CSV file upload (up to 50 MB)
- ✅ Automatic dataset analysis and metadata extraction
- ✅ Natural language query processing
- ✅ Intelligent intent classification (keyword-based + AI fallback)

### Visualization Engine
- ✅ 3-tier visualization system:
  1. **JSON Spec** → AI returns chart specification, Python builds it
  2. **Code Generation** → AI generates matplotlib code
  3. **Auto-fallback** → Automatic histogram if both fail
- ✅ Supported chart types: histogram, bar, line, scatter, pie, box, heatmap, area
- ✅ Dark-themed charts matching the UI

### Chat & History
- ✅ Persistent chat sessions stored in database
- ✅ Message history with results (tables, charts, text)
- ✅ Session switching with automatic history restore
- ✅ Activity logging for all user actions

### User Interface
- ✅ Modern dark theme (GitHub-inspired)
- ✅ Split-panel layout: chat (left) + results (right)
- ✅ Responsive design
- ✅ Real-time typing indicators
- ✅ Smooth animations and transitions

---

## 🛠️ Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | Flask 3.0 | Web framework, routing, API |
| **Database** | SQLite + SQLAlchemy | Data persistence, ORM |
| **Authentication** | JWT + bcrypt | Stateless auth, password security |
| **Frontend** | HTML5 + CSS3 + Vanilla JS | Custom UI, no framework dependencies |
| **AI Engine** | OpenRouter API | Natural language processing, code generation |
| **Data Processing** | Pandas | DataFrame operations |
| **Visualization** | Matplotlib + Seaborn | Chart generation |

---

## 📁 Project Structure

```
v4.3 Upgraded UI and Facilities/
│
├── 🐍 Backend Core
│   ├── run.py                  # Application entry point
│   ├── app.py                  # Flask app factory, routes, auth
│   ├── config.py               # Configuration (DB, uploads, JWT)
│   ├── api_config.py           # OpenRouter API configuration
│   └── engines.py              # AI engines (intent, display, visualize, modify, chat)
│
├── 💾 Database Layer
│   └── database/
│       ├── __init__.py         # SQLAlchemy instance
│       ├── models.py           # ORM models (User, ChatSession, Message, Activity)
│       └── copilot.db          # SQLite database (auto-created)
│
├── 🎨 Frontend
│   ├── templates/
│   │   ├── base.html           # Base layout template
│   │   ├── login.html          # Login page
│   │   ├── register.html       # Registration page
│   │   └── dashboard.html      # Main application interface
│   │
│   └── static/
│       ├── css/
│       │   └── style.css       # Complete dark theme stylesheet
│       └── js/
│           └── app.js          # Frontend logic (chat, upload, sessions)
│
├── 📂 Data Storage
│   ├── uploads/                # User-uploaded CSV files (per-user subdirectories)
│   └── modified_files/
│       └── backups/            # Automatic backups for undo functionality
│
└── 📄 Configuration
    └── requirements.txt        # Python dependencies
```

---

## 🚀 Installation & Setup

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Step 1: Clone/Navigate to Project
```bash
cd "e:\Projects\Copilot-For-Data-Science\Copilote for data science\Phase 4 HCI + Deployment\v4.3 Upgraded UI and Facilities"
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

**Dependencies installed:**
- `flask` — Web framework
- `flask-sqlalchemy` — Database ORM
- `flask-cors` — CORS support
- `pyjwt` — JWT token handling
- `bcrypt` — Password hashing
- `pandas` — Data manipulation
- `matplotlib` — Chart generation
- `seaborn` — Statistical visualizations
- `openai` — OpenRouter API client

### Step 3: Configure API Key
Edit `api_config.py` and add your OpenRouter API key:
```python
api_key="your-openrouter-api-key-here"
```

### Step 4: Run the Application
```bash
python run.py
```

The server will start on `http://localhost:5000`

---

## 👤 User Guide

### Getting Started

#### 1. Create an Account
- Navigate to `http://localhost:5000`
- Click **"Create one"** on the login page
- Fill in:
  - Username (unique)
  - Email (unique)
  - Password (minimum 6 characters)
- Click **"Create Account"**

#### 2. Login
- Enter your username or email
- Enter your password
- Click **"Sign In"**

#### 3. Upload a Dataset
- Click the **upload zone** in the sidebar
- Select a CSV file (max 50 MB)
- The dataset info will appear automatically:
  - Number of rows and columns
  - Missing values count
  - Numeric columns count
  - List of all columns with types

### Using the Application

#### Display Operations
Ask questions to view your data:
- `"Show first 10 rows"`
- `"Display summary statistics"`
- `"What are the column names?"`
- `"Show rows where price > 100"`
- `"Display the last 5 entries"`

**Result:** Tables appear in the **Results Panel** (right side)

#### Visualization Operations
Request charts using natural language:
- `"Plot a histogram of CLOSE"`
- `"Create a scatter plot of x vs y"`
- `"Visualize the distribution of prices"`
- `"Show a bar chart of categories"`
- `"Generate a correlation heatmap"`

**Result:** Charts appear in the **Results Panel** (right side)

**Supported Chart Types:**
- Histogram
- Bar chart
- Line chart
- Scatter plot
- Pie chart
- Box plot
- Heatmap
- Area chart

#### Modify Operations
Transform your data:
- `"Add a column 'ID' with row numbers"`
- `"Remove the 'unused' column"`
- `"Fill missing values with 0"`
- `"Rename column 'old_name' to 'new_name'"`
- `"Sort by date descending"`

**Result:** 
- Changes are saved to the CSV file
- Preview appears in the Results Panel
- Automatic backup created for undo

#### Undo Operation
Revert the last change:
- `"Undo"`
- `"Revert last change"`
- `"Go back"`

#### General Chat
Ask questions about your data:
- `"What insights can you give me?"`
- `"Explain this dataset"`
- `"What should I analyze first?"`

### Managing Sessions

#### View Past Sessions
- The **Sessions** section in the sidebar shows all your chat sessions
- Click any session to restore it
- Chat history and results are automatically loaded

#### Switch Between Sessions
- Upload a new CSV to create a new session
- Click on previous sessions to switch back
- Each session maintains its own:
  - Chat history
  - Results
  - Dataset reference

---

## 💻 Developer Guide

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     User Browser                        │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Login/     │  │  Dashboard   │  │  JavaScript  │  │
│  │  Register   │  │  (Split UI)  │  │  (app.js)    │  │
│  └─────────────┘  └──────────────┘  └──────────────┘  │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP/JSON
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    Flask Backend                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │  app.py (Routes & Auth)                          │  │
│  │  • /api/register, /api/login, /api/logout        │  │
│  │  • /api/upload, /api/chat                        │  │
│  │  • /api/sessions, /api/activities                │  │
│  └──────────────────────────────────────────────────┘  │
│                         │                               │
│  ┌──────────────────────┼──────────────────────────┐  │
│  │  engines.py          │                          │  │
│  │  • classify_intent() │  • generate_display_code()│  │
│  │  • build_chart()     │  • generate_visualize_code()│
│  │  • generate_chat_response()                      │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
    ┌─────────┐   ┌──────────┐   ┌──────────┐
    │ SQLite  │   │ OpenRouter│   │ Pandas   │
    │ Database│   │ API       │   │ + Matplotlib│
    └─────────┘   └──────────┘   └──────────┘
```

### Key Components

#### 1. Authentication Flow (`app.py`)
```python
# Registration
POST /api/register → Create User → Hash password → Generate JWT → Set cookie

# Login
POST /api/login → Verify credentials → Generate JWT → Set cookie

# Protected Routes
@login_required decorator → Verify JWT → Attach user to request
```

#### 2. Intent Classification (`engines.py`)
```python
classify_intent(user_input):
    1. Check keyword lists (visualize, display, modify, undo)
    2. If no match → Call AI for classification
    3. Return: "visualize" | "display" | "modify" | "undo" | "chat"
```

#### 3. Visualization Pipeline (`engines.py`)
```python
Tier 1: generate_chart_spec() → AI returns JSON → build_chart()
        ↓ (if fails)
Tier 2: generate_visualize_code() → AI returns matplotlib code → exec()
        ↓ (if fails)
Tier 3: build_auto_chart() → Automatic histogram of first numeric column
```

#### 4. Database Models (`database/models.py`)

**User**
- `id`, `username`, `email`, `password_hash`, `created_at`
- Relationships: `sessions`, `activities`

**ChatSession**
- `id`, `user_id`, `filename`, `file_path`, `title`, `created_at`
- Relationships: `messages`

**Message**
- `id`, `session_id`, `role`, `content`, `result_type`, `result_data`, `result_title`, `created_at`

**Activity**
- `id`, `user_id`, `action`, `details`, `created_at`

### Adding New Features

#### Add a New Operation Type
1. Add keywords to `engines.py`:
   ```python
   _NEW_OPERATION_KW = ["keyword1", "keyword2"]
   ```

2. Update `classify_intent()` to check new keywords

3. Create code generation function:
   ```python
   def generate_new_operation_code(user_input, file_path, ctx):
       # Your implementation
   ```

4. Add handler in `app.py`:
   ```python
   def _handle_new_operation(user_input, df, file_path, ctx):
       # Your implementation
   ```

#### Customize UI Theme
Edit `static/css/style.css`:
```css
:root {
    --accent-blue: #58a6ff;    /* Change primary color */
    --bg-primary: #0d1117;     /* Change background */
    /* ... other variables */
}
```

---

## 🗄️ Database Schema

```sql
-- Users table
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Chat sessions table
CREATE TABLE chat_sessions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    filename VARCHAR(255),
    file_path VARCHAR(512),
    title VARCHAR(255) DEFAULT 'New Session',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Messages table
CREATE TABLE messages (
    id INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL,
    role VARCHAR(20) NOT NULL,  -- 'user' or 'assistant'
    content TEXT NOT NULL,
    result_type VARCHAR(20),    -- 'dataframe', 'chart', 'text', or NULL
    result_data TEXT,           -- JSON or base64
    result_title VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
);

-- Activity log table
CREATE TABLE activities (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    action VARCHAR(50) NOT NULL,  -- 'login', 'upload', 'display', etc.
    details TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

---

## 🔌 API Reference

### Authentication Endpoints

#### `POST /api/register`
Register a new user.

**Request Body:**
```json
{
    "username": "john_doe",
    "email": "john@example.com",
    "password": "secure123"
}
```

**Response (201):**
```json
{
    "message": "Registration successful",
    "user": {
        "id": 1,
        "username": "john_doe",
        "email": "john@example.com",
        "created_at": "2026-02-17T14:30:00Z"
    }
}
```

#### `POST /api/login`
Authenticate a user.

**Request Body:**
```json
{
    "login_id": "john_doe",  // username or email
    "password": "secure123"
}
```

**Response (200):**
```json
{
    "message": "Login successful",
    "user": { /* user object */ }
}
```

#### `POST /api/logout`
Logout current user (clears JWT cookie).

**Response (200):**
```json
{
    "message": "Logged out"
}
```

#### `GET /api/me`
Get current user info (requires authentication).

**Response (200):**
```json
{
    "user": {
        "id": 1,
        "username": "john_doe",
        "email": "john@example.com",
        "created_at": "2026-02-17T14:30:00Z"
    }
}
```

### Data Endpoints

#### `POST /api/upload`
Upload a CSV file (requires authentication).

**Request:** `multipart/form-data` with `file` field

**Response (200):**
```json
{
    "message": "File uploaded",
    "dataset": {
        "filename": "data.csv",
        "rows": 1000,
        "columns": 5,
        "column_names": ["col1", "col2", "col3", "col4", "col5"],
        "dtypes": {"col1": "int64", "col2": "float64", ...},
        "missing": 10,
        "numeric_count": 3,
        "session_id": 42
    }
}
```

#### `POST /api/chat`
Process a chat message (requires authentication).

**Request Body:**
```json
{
    "message": "show first 10 rows",
    "session_id": 42
}
```

**Response (200):**
```json
{
    "user_msg": {
        "id": 100,
        "role": "user",
        "content": "show first 10 rows",
        "created_at": "2026-02-17T14:35:00Z"
    },
    "assistant_msg": {
        "id": 101,
        "role": "assistant",
        "content": "📊 Displayed results for: show first 10 rows — see the results panel →",
        "result_type": "dataframe",
        "result_data": "{\"columns\":[...],\"data\":[...]}",
        "result_title": "📊 show first 10 rows",
        "created_at": "2026-02-17T14:35:01Z"
    }
}
```

### Session Endpoints

#### `GET /api/sessions`
Get all chat sessions for current user (requires authentication).

**Response (200):**
```json
{
    "sessions": [
        {
            "id": 42,
            "filename": "data.csv",
            "title": "Chat: data.csv",
            "created_at": "2026-02-17T14:30:00Z",
            "message_count": 15
        },
        // ... more sessions
    ]
}
```

#### `GET /api/sessions/<session_id>/messages`
Get all messages for a specific session (requires authentication).

**Response (200):**
```json
{
    "messages": [
        {
            "id": 100,
            "role": "user",
            "content": "show first 10 rows",
            "result_type": null,
            "result_data": null,
            "result_title": null,
            "created_at": "2026-02-17T14:35:00Z"
        },
        // ... more messages
    ],
    "dataset": {
        "filename": "data.csv",
        "rows": 1000,
        // ... dataset info
    }
}
```

#### `GET /api/activities`
Get activity log for current user (requires authentication).

**Response (200):**
```json
{
    "activities": [
        {
            "id": 1,
            "action": "login",
            "details": null,
            "created_at": "2026-02-17T14:30:00Z"
        },
        {
            "id": 2,
            "action": "upload",
            "details": "Uploaded data.csv",
            "created_at": "2026-02-17T14:31:00Z"
        },
        // ... more activities
    ]
}
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. Server won't start
**Error:** `ModuleNotFoundError: No module named 'flask'`

**Solution:**
```bash
pip install -r requirements.txt
```

#### 2. Database errors
**Error:** `OperationalError: no such table: users`

**Solution:** Delete the database and restart (it will be recreated):
```bash
rm database/copilot.db
python run.py
```

#### 3. Login/Registration fails
**Error:** `401 Unauthorized` or `409 Conflict`

**Possible causes:**
- Username/email already exists (409)
- Invalid credentials (401)
- Password too short (400)

**Solution:** Check the error message in the browser console or network tab

#### 4. File upload fails
**Error:** `413 Request Entity Too Large`

**Solution:** File exceeds 50 MB limit. Reduce file size or increase `MAX_CONTENT_LENGTH` in `config.py`

#### 5. Visualizations not working
**Possible causes:**
- AI returned invalid code
- Dataset has no numeric columns
- Column names don't match

**Solution:** Try simpler queries like `"plot histogram"` or check the browser console for errors

#### 6. Chat history not loading
**Possible causes:**
- Session ID mismatch
- Database corruption

**Solution:** 
1. Check browser console for errors
2. Try creating a new session
3. If persistent, delete and recreate database

### Debug Mode

Enable Flask debug mode in `run.py`:
```python
app.run(host="0.0.0.0", port=5000, debug=True)
```

This provides:
- Detailed error messages
- Auto-reload on code changes
- Interactive debugger in browser

### Logs

Check terminal output for:
- Request logs
- Error tracebacks
- Database queries (if SQLAlchemy echo enabled)

---

## 📝 Configuration

### Environment Variables

You can override default settings using environment variables:

```bash
# Set secret key (recommended for production)
export SECRET_KEY="your-super-secret-key-here"

# Run the app
python run.py
```

### config.py Settings

```python
SECRET_KEY = "..."                    # JWT signing key
SQLALCHEMY_DATABASE_URI = "..."       # Database connection string
UPLOAD_FOLDER = "..."                 # Where to store uploaded files
MAX_CONTENT_LENGTH = 50 * 1024 * 1024 # Max upload size (50 MB)
JWT_EXPIRY_HOURS = 24                 # JWT token lifetime
```

---

## 🚀 Deployment

### Production Checklist

- [ ] Change `SECRET_KEY` to a random string
- [ ] Set `debug=False` in `run.py`
- [ ] Use a production WSGI server (gunicorn, waitress)
- [ ] Set up HTTPS
- [ ] Configure CORS properly
- [ ] Set up database backups
- [ ] Monitor logs and errors
- [ ] Set file upload limits appropriately

### Example Production Setup (Linux)

```bash
# Install gunicorn
pip install gunicorn

# Run with gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```

---

## 📄 License

This project is for educational and research purposes.

---

## 🤝 Support

For issues, questions, or contributions, please refer to the project repository or contact the development team.

---

**Built with ❤️ using Flask, SQLAlchemy, and OpenRouter AI**
