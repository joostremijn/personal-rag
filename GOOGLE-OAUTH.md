# Google Drive OAuth Setup Guide

This guide walks you through setting up Google Drive access for the Personal RAG system using OAuth 2.0.

## Overview

The Personal RAG system uses Google OAuth 2.0 to access your Google Drive files. This is a one-time setup that allows the application to read your Drive files securely.

**Time required**: ~10 minutes

## Prerequisites

- A Google account
- Access to [Google Cloud Console](https://console.cloud.google.com/)

## Step-by-Step Setup

### 1. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **"Select a Project"** dropdown at the top
3. Click **"New Project"**
   - **Project name**: `Personal RAG` (or any name you prefer)
   - **Location**: Leave as default (No organization)
4. Click **"Create"**
5. Wait for the project to be created (~30 seconds)
6. Select your new project from the dropdown

### 2. Enable Google Drive API

1. In the search bar at the top, type: `Google Drive API`
2. Click on **"Google Drive API"** from the results
3. Click the blue **"Enable"** button
4. Wait for the API to be enabled

### 3. Configure OAuth Consent Screen

Before creating credentials, you need to configure the OAuth consent screen:

1. Go to **"APIs & Services"** → **"OAuth consent screen"** (left sidebar)
2. Choose **"External"** as User Type
3. Click **"Create"**

**OAuth consent screen configuration:**

- **App name**: `Personal RAG`
- **User support email**: Select your email from dropdown
- **App logo**: (optional, skip for now)
- **Application home page**: (optional, skip)
- **Authorized domains**: (skip for now)
- **Developer contact information**: Enter your email

4. Click **"Save and Continue"**

**Scopes screen:**
- Click **"Add or Remove Scopes"**
- Search for `drive.readonly`
- Check the box for `.../auth/drive.readonly` (Read-only access to Drive)
- Click **"Update"**
- Click **"Save and Continue"**

**Test users:**
- Click **"Add Users"**
- Enter your Google email address
- Click **"Add"**
- Click **"Save and Continue"**

**Summary:**
- Review the summary
- Click **"Back to Dashboard"**

### 4. Create OAuth 2.0 Credentials

1. Go to **"APIs & Services"** → **"Credentials"** (left sidebar)
2. Click **"+ Create Credentials"** at the top
3. Select **"OAuth client ID"**
4. Choose application type: **"Desktop app"**
5. **Name**: `Personal RAG Desktop`
6. Click **"Create"**

### 5. Download Credentials

1. A popup will show your Client ID and Secret
2. Click **"Download JSON"** button (or the download icon ⬇️)
3. Save the downloaded file

### 6. Install Credentials in Your Project

**Option A: Rename and move**
```bash
cd ~/Downloads
mv client_secret_*.json ~/src/personal-rag/credentials.json
```

**Option B: Copy content**
1. Open the downloaded JSON file
2. Copy all the content
3. Create `credentials.json` in your project root:
   ```bash
   cd ~/src/personal-rag
   nano credentials.json
   # Paste the JSON content
   # Press Ctrl+X, then Y, then Enter to save
   ```

### 7. Verify Installation

```bash
cd ~/src/personal-rag
ls -la credentials.json
```

You should see the file listed. The credentials.json file should look like this:

```json
{
  "installed": {
    "client_id": "xxxxx.apps.googleusercontent.com",
    "project_id": "your-project",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "xxxxx",
    "redirect_uris": ["http://localhost"]
  }
}
```

## First Run: OAuth Authorization

When you first run the Google Drive ingestion, the OAuth flow will start:

### Test the Connection

```bash
# Activate your virtual environment
source .venv/bin/activate

# List your Google Drive folders (this will trigger OAuth)
python ingest.py --source-type gdrive --list-folders
```

### What Happens Next

1. **Browser Opens**: Your default browser will open automatically
2. **Google Sign In**: Sign in with your Google account (if not already signed in)
3. **Permission Screen**: You'll see a screen saying:
   - "Personal RAG wants to access your Google Account"
   - "See and download all your Google Drive files"
4. **Warning**: You may see "Google hasn't verified this app" warning:
   - Click **"Advanced"**
   - Click **"Go to Personal RAG (unsafe)"**
   - This is normal for personal apps - you're the developer!
5. **Grant Access**: Click **"Allow"** to grant permissions
6. **Success**: You'll see "The authentication flow has completed"
7. **Close Browser**: You can close the browser tab

### Token Storage

After successful authorization:
- A `token.json` file will be created in your project root
- This stores your access token for future use
- You won't need to re-authorize unless the token expires (rare)
- **Security**: The token.json is already in .gitignore (won't be committed)

## Testing Google Drive Integration

### 1. List Folders

```bash
python ingest.py --source-type gdrive --list-folders
```

This shows all folders in your Google Drive.

### 2. Ingest a Few Files (Test)

```bash
# Ingest just 5 files to test
python ingest.py --source-type gdrive --max-results 5
```

### 3. Ingest from Specific Folder

```bash
# First, list folders to find the ID
python ingest.py --source-type gdrive --list-folders

# Copy the folder ID you want, then:
python ingest.py --source-type gdrive --folder-id "YOUR_FOLDER_ID"
```

### 4. Ingest All Accessible Files

```bash
# Ingest up to 100 files (default)
python ingest.py --source-type gdrive --max-results 100
```

### 5. Check Ingestion Stats

```bash
python ingest.py --stats
```

## Supported Google Drive File Types

The system can ingest:

- ✅ **Google Docs** (exported as plain text)
- ✅ **Google Sheets** (exported as CSV)
- ✅ **PDFs** (text extracted)
- ✅ **Word documents** (.docx)
- ✅ **Plain text files** (.txt)
- ✅ **Markdown files** (.md)

Files are automatically converted to text for indexing.

## Troubleshooting

### Issue: "credentials.json not found"

**Solution**: Make sure credentials.json is in the project root directory:
```bash
ls -la ~/src/personal-rag/credentials.json
```

### Issue: "Access blocked: This app's request is invalid"

**Solution**:
- Make sure you configured the OAuth consent screen
- Add yourself as a test user
- Verify the Google Drive API is enabled

### Issue: "The authentication flow has completed" but script fails

**Solution**:
- Delete `token.json` and try again
- Check your internet connection
- Verify credentials.json format is correct

### Issue: "invalid_grant" error

**Solution**:
```bash
# Token expired or invalid - delete and re-authorize
rm token.json
python ingest.py --source-type gdrive --list-folders
```

### Issue: "Access denied" when trying to access files

**Solution**:
- Make sure you granted all permissions during OAuth
- Check that the scope includes `drive.readonly`
- Re-run the OAuth flow: `rm token.json` and try again

### Issue: "Rate limit exceeded"

**Solution**:
- Google Drive API has rate limits
- Reduce `--max-results` value
- Wait a few minutes and try again
- For large datasets, ingest in batches

## Security Considerations

### What You're Granting

- **Read-only access** to your Google Drive
- The app can **read** your files but **cannot modify or delete** them
- Access is limited to the account you authorize

### Credential Safety

- ✅ `credentials.json` is in .gitignore (won't be committed to git)
- ✅ `token.json` is in .gitignore (won't be committed to git)
- ⚠️ Never share these files publicly
- ⚠️ Don't commit them to version control

### Revoking Access

To revoke access at any time:

1. Go to [Google Account Permissions](https://myaccount.google.com/permissions)
2. Find "Personal RAG" in the list
3. Click "Remove Access"
4. Delete local `token.json` file

## Alternative: Service Account (Advanced)

For server deployments or team use, consider using a Service Account instead:

1. Google Cloud Console → "Create Credentials" → "Service Account"
2. Download the service account JSON key
3. Share specific Drive folders with the service account email
4. Update code to use service account credentials

See [Google Service Account Documentation](https://cloud.google.com/iam/docs/service-accounts) for details.

## Alternative: Google Drive Desktop App (Simplest)

If you prefer to avoid API setup entirely:

1. Install [Google Drive for Desktop](https://www.google.com/drive/download/)
2. Sign in and sync your files
3. Use the local file connector:
   ```bash
   python ingest.py --source "~/Google Drive/My Drive" --source-type local
   ```

This works exactly the same but requires no OAuth setup!

## Summary Checklist

- [ ] Create Google Cloud project
- [ ] Enable Google Drive API
- [ ] Configure OAuth consent screen
- [ ] Add yourself as test user
- [ ] Create OAuth 2.0 credentials (Desktop app)
- [ ] Download credentials.json
- [ ] Place credentials.json in project root
- [ ] Run first ingestion command
- [ ] Complete browser OAuth flow
- [ ] Verify token.json was created
- [ ] Test with `--list-folders` or `--max-results 5`

## Getting Help

If you encounter issues:

1. Check this troubleshooting section
2. Verify all steps were completed in order
3. Check the [Google Drive API documentation](https://developers.google.com/drive/api/guides/about-sdk)
4. Review error messages carefully - they usually indicate the specific step that failed

## Next Steps

Once Google Drive integration is working:

- Set up scheduled ingestion (cron job or similar)
- Ingest from multiple sources (Drive + local files)
- Build the query/retrieval system
- Create the web UI for chatting with your documents

Enjoy your Personal RAG system! 🚀
