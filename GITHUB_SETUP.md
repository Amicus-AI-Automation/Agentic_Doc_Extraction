# GitHub Push Steps

## Pre-Push Verification

1. **Check what will be committed:**
   ```bash
   git status
   ```
   You should see:
   - ✅ `.env.example` (tracked)
   - ✅ `.gitignore` (updated)
   - ✅ `README.md` (updated)
   - ✅ All source code in `agent/` and `preprocessing/`
   - ✅ `main.py`, `config.py`, `requirements.txt`
   - ❌ `.env` (git-ignored — secrets safe!)
   - ❌ `.venv/` (git-ignored)
   - ❌ `output/` (git-ignored)
   - ❌ `input/` PDFs (git-ignored)
   - ❌ `__pycache__/` (git-ignored)

2. **Verify nothing sensitive is being committed:**
   ```bash
   git diff --cached
   ```
   Should NOT contain any API keys, credentials, or large binary files.

---

## Initial GitHub Setup (First Time Only)

### Option A: Create a new repository on GitHub

1. Go to [github.com/new](https://github.com/new)
2. Create a new repository:
   - Name: `ADE-AGENTold` (or similar)
   - Description: "Agentic Document Extraction pipeline using Docling and Groq VLM"
   - **Visibility:** Public or Private (your choice)
   - **Skip** "Initialize with README" (we already have one)
   - Click **Create repository**

3. You'll see instructions like:
   ```bash
   # Push an existing repository from the command line
   git remote add origin https://github.com/username/ADE-AGENTold.git
   git branch -M main
   git push -u origin main
   ```

### Option B: You already have a repo created

Just navigate to it in your terminal.

---

## Push to GitHub

### Step 1: Initialize Git (if not already done)

```bash
cd d:\customapps\test1\ADE_AGENTold
git init
```

### Step 2: Add all files

```bash
git add .
```

This will respect `.gitignore` and only stage:
- Source code
- `.gitkeep` files (for folder structure)
- `.env.example` (template)
- `README.md`, `requirements.txt`

### Step 3: Verify staged files

```bash
git status
```

### Step 4: Create first commit

```bash
git commit -m "Initial commit: ADE Agent document extraction pipeline with Docling and Groq VLM

- Document parsing with Docling (PDFs, images, office formats)
- Automatic input type detection and preprocessing
- Image asset extraction with OCR enrichment
- Groq VLM visual descriptions for cropped images
- JSON and Markdown output formats
- Bounding-box visualizations (optional)
- Supports native and scanned PDFs, images, DOCX, PPTX, etc."
```

### Step 5: Add remote repository

Replace `USERNAME` and `REPO_NAME` with your GitHub username and repository name:

```bash
git remote add origin https://github.com/USERNAME/REPO_NAME.git
```

Verify:
```bash
git remote -v
```

### Step 6: Push to GitHub

```bash
git branch -M main
git push -u origin main
```

This pushes your `main` branch to GitHub and sets it as the default upstream.

---

## Post-Push Verification

1. Visit your repository on GitHub: `https://github.com/USERNAME/REPO_NAME`
2. Verify:
   - ✅ Files are visible (agent/, main.py, README.md, etc.)
   - ✅ No `.env` file (git-ignored)
   - ✅ `.gitkeep` files in `input/` and `output/` (folder structure preserved)
   - ✅ `.env.example` is visible (template for users)
   - ❌ `__pycache__/`, `.venv/` not visible (git-ignored)

---

## Workflow for Future Updates

After making code changes:

```bash
# See what changed
git status

# Stage changes
git add .

# Commit with a message
git commit -m "Brief description of changes"

# Push to GitHub
git push
```

---

## Important Notes

1. **`.env` is git-ignored** — Your API keys are safe. Users must set their own `.env` from `.env.example`.
2. **Large files are git-ignored** — Test PDFs in `input/` won't be committed (they're binary and large).
3. **Generated outputs** — `output/` folder is git-ignored so pull requests don't include generated files.
4. **`__pycache__`** — Compiled Python is git-ignored to keep the repo clean.

---

## Clone Instructions for Others

Once your repo is on GitHub, anyone can set it up:

```bash
# Clone
git clone https://github.com/USERNAME/REPO_NAME.git
cd REPO_NAME

# Create environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/macOS

# Install
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env and add your GROQ_API_KEY

# Run
python main.py test.pdf
```

---

## Troubleshooting

### "fatal: not a git repository"
```bash
git init
```

### "nothing to commit"
Your changes are already committed. Verify with `git log --oneline`.

### "rejected ... master -> main"
The remote branch name differs. Fix with:
```bash
git pull origin main
git push origin main
```

### "fatal: Authentication failed"
GitHub now requires personal access tokens or SSH keys. See [GitHub Docs](https://docs.github.com/en/authentication).
