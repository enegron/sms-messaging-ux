# Setup & Configuration Checklist

This document walks you through every step to configure all third-party services and prepare for deploying the backend to Railway.

---

## Phase 1: Twilio Setup

### 1.1 Verify Twilio Account

- [ ] You have a Twilio account created
- [ ] You chose "Code" path in Twilio onboarding
- [ ] You can log into Twilio console: https://www.twilio.com/console

### 1.2 Get Twilio Credentials

In Twilio Console (https://www.twilio.com/console):

1. [ ] Note your **Account SID**
   - Dashboard shows `Account SID` at top
   - Looks like: `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
   - Save this to a secure file (password manager, etc.)

2. [ ] Note your **Auth Token**
   - Dashboard shows `Auth Token` next to Account SID
   - Click eye icon to reveal
   - Looks like: `xxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
   - Save this securely (treat like password)

3. [ ] Generate an API Key (optional, more secure than Auth Token)
   - Go to: Account → Keys & Credentials → API Keys
   - Click "Create API Key"
   - Download the key file
   - You'll see: `AKIA...` and a secret
   - Save this securely
   - **For MVP**, Auth Token is fine; API Key is for production

**Save credentials to a file like `.env.local` (DO NOT COMMIT to git):**
```
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_API_KEY=AKIA... (optional)
TWILIO_API_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx (optional)
```

### 1.3 Get or Create Twilio Phone Number

In Twilio Console:

1. [ ] Go to: Phone Numbers → Manage Numbers
2. [ ] If you already have a number from free trial setup, note it
   - Should be a number like `+1 (202) 555-1234`
   - In E.164 format: `+12025551234`
3. [ ] If you don't have one yet:
   - Click "Buy a Number"
   - Choose country (US, etc.)
   - Twilio assigns a number
   - Click "Buy"
   - Note the number in E.164 format

**Save this:**
```
TWILIO_PHONE_NUMBER=+12025551234
```

### 1.4 Configure Incoming SMS Webhook (via Messaging Service)

In Twilio Console:

1. [ ] Go to: Messaging → Services
2. [ ] Click on your Messaging Service
3. [ ] Go to the "Integration" tab
4. [ ] Under "Incoming Messages", select "Receive"
5. [ ] In the "Callback URL" field, enter your webhook URL:
   - For now, use a placeholder: `https://your-railway-app.railway.app/twilio/incoming`
   - You'll update this after Railway deployment
   - For local testing: use ngrok (see section below)
6. [ ] Method: POST (default)
7. [ ] Click "Save"

**You'll update this URL after Railway deployment.**

### 1.5 Add Verified Phone Numbers (for free trial)

Free trial requires verifying numbers you want to send/receive:

1. [ ] Go to: Phone Numbers → Verified Caller IDs
2. [ ] Click "Add New"
3. [ ] Enter a phone number you want to test with (the ones you mentioned you have)
4. [ ] Twilio sends a verification code to that number
5. [ ] Enter code in Twilio console to verify
6. [ ] Repeat for each test number (up to 5 for free trial)

**Verified numbers:**
```
+1 (202) 555-XXXX
+1 (310) 555-XXXX
[add your test numbers]
```

---

## Phase 2: Firebase Setup (Already Done)

### 2.1 Verify Firebase Project

- [ ] You created project: "prototypes"
- [ ] You created app: "Messaging UX"
- [ ] Firestore database is created (test mode)
- [ ] You downloaded service account key JSON file

### 2.2 Store Service Account Key

1. [ ] Save the JSON file somewhere safe locally (not in git)
2. [ ] Name it: `firebase-service-account-key.json`
3. [ ] This contains credentials like:
```json
{
  "type": "service_account",
  "project_id": "prototypes",
  "private_key_id": "xxxxxxxxxxxxx",
  "private_key": "-----BEGIN PRIVATE KEY-----...",
  "client_email": "firebase-adminsdk-xxxxx@prototypes.iam.gserviceaccount.com",
  "client_id": "xxxxxxxxxxxxxxxxxxxxx",
  ...
}
```

### 2.3 Initialize Firestore Collections (Optional)

You can initialize the collections in Firebase console or let the backend create them on first use.

**To initialize manually:**

1. [ ] Go to Firebase Console → Firestore Database
2. [ ] Click "Start Collection"
3. [ ] Create collection: `users`
   - Add first document (optional, can be empty)
4. [ ] Create collection: `incomingMessages`
   - Leave empty initially
5. [ ] Create collection: `outgoingMessages`
   - Leave empty initially

Or just start with empty Firestore and let backend create collections on first write.

### 2.4 Upload Initial User Data

You have a couple test phone numbers. Add them to Firebase:

**Option A: Manual (Firebase Console)**
1. [ ] Go to: Firestore → `users` collection
2. [ ] Click "Add Document"
3. [ ] Document ID: `+12025551234` (your first test number)
4. [ ] Add fields:
   - `phoneNumber`: `"+12025551234"` (string)
   - `status`: `"active"` (string)
   - `name`: `"Test User 1"` (string, optional)
   - `createdAt`: Now (timestamp)
   - `updatedAt`: Now (timestamp)
   - `metadata`: `{}` (empty map)
   - `notes`: `""` (empty string)
5. [ ] Click "Save"
6. [ ] Repeat for second test number

**Option B: Python script (you'll write this later, or Claude Code will)**
```python
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# Initialize Firebase (you'll do this in the backend too)
cred = credentials.Certificate('firebase-service-account-key.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# Add users
users = [
    {
        "phoneNumber": "+12025551234",
        "name": "Test User 1",
        "status": "active",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
        "metadata": {},
        "notes": ""
    },
    {
        "phoneNumber": "+13105554567",
        "name": "Test User 2",
        "status": "active",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
        "metadata": {},
        "notes": ""
    }
]

for user in users:
    db.collection('users').document(user['phoneNumber']).set(user)
    print(f"Added user: {user['phoneNumber']}")
```

**Do this:**
- [ ] Manually add test users to Firebase console

### 2.5 Update Firestore Security Rules

For MVP (test mode), you can skip this. But for production readiness:

1. [ ] Go to: Firestore → Rules tab
2. [ ] Replace rules with (or use the rules from document `02_Firestore_Data_Model.md`):

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    function isAuthenticated() {
      return request.auth != null;
    }
    
    match /users/{phoneNumber} {
      allow read: if isAuthenticated();
      allow write: if false;
    }
    
    match /incomingMessages/{document=**} {
      allow read: if isAuthenticated();
      allow write: if false;
    }
    
    match /outgoingMessages/{document=**} {
      allow read: if isAuthenticated();
      allow write: if isAuthenticated();
    }
  }
}
```

3. [ ] For MVP: Keep in "Test Mode" (allows all reads/writes)
4. [ ] Click "Publish"

---

## Phase 3: Railway Setup

### 3.1 Create Railway Account

1. [ ] Go to: https://railway.app
2. [ ] Sign up (GitHub recommended)
3. [ ] Create new project

### 3.2 Create Python Project

1. [ ] In Railway dashboard: "Create New"
2. [ ] Select: "From GitHub repo" (or "Empty project" if no repo yet)
3. [ ] If from GitHub:
   - Connect GitHub account
   - Select your repo (or create one)
4. [ ] Railway auto-detects Python
5. [ ] Add environment variables (next section)

### 3.3 Add Environment Variables to Railway

In Railway project settings → Variables:

Add these environment variables (Railway keeps them secure):

```
# Twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_PHONE_NUMBER=+12025551234

# Firebase
FIREBASE_PROJECT_ID=prototypes
FIREBASE_CLIENT_EMAIL=firebase-adminsdk-xxxxx@prototypes.iam.gserviceaccount.com
FIREBASE_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...
FIREBASE_PRIVATE_KEY_ID=xxxxxxxxxxxxx

# App
FLASK_ENV=production
PORT=8000
OPERATOR_PASSWORD=changeme (for simple auth)
```

**For Firebase credentials, you can either:**
- Set individual environment variables (listed above)
- Or upload the full `firebase-service-account-key.json` as a secret file

### 3.4 Deploy Placeholder Backend

Before Claude Code writes the full backend, you should test Railway deployment:

1. [ ] Create a simple `app.py`:
```python
from flask import Flask

app = Flask(__name__)

@app.route('/health')
def health():
    return {'status': 'healthy'}, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
```

2. [ ] Create `requirements.txt`:
```
Flask==2.3.0
twilio==8.10.0
firebase-admin==6.0.0
python-dotenv==1.0.0
gunicorn==21.0.0
```

3. [ ] Create `Procfile`:
```
web: gunicorn app:app
```

4. [ ] Push to GitHub
5. [ ] Railway auto-deploys
6. [ ] Get your Railway URL: `https://your-railway-app.railway.app`
7. [ ] Test: `curl https://your-railway-app.railway.app/health`

---

## Phase 4: Update Twilio Webhook URL

After Railway deployment:

1. [ ] Copy your Railway URL: `https://your-railway-app.railway.app`
2. [ ] Go to Twilio Console → Messaging → Services → Your Service
3. [ ] Go to the "Integration" tab
4. [ ] Under "Incoming Messages" (Receive section), update the "Callback URL" to:
   ```
   https://your-railway-app.railway.app/twilio/incoming
   ```
5. [ ] Method: POST
6. [ ] Click "Save"

Now Twilio will route incoming messages to your Railway backend.

---

## Phase 5: Testing & Verification

### 5.1 Test Incoming Message from Registered User

1. [ ] Send SMS from one of your verified test numbers to your Twilio number
   - From: `+12025551234` (registered user)
   - To: Your Twilio number
   - Content: `Hello testing`

2. [ ] Expected behavior:
   - You should receive SMS response: `"Your number is recognized. Message received."`
   - Within 5 seconds

3. [ ] Check Firebase:
   - Go to Firestore → `incomingMessages` collection
   - Should see new document with:
     - `phoneNumber`: `+12025551234`
     - `messageContent`: `Hello testing`
     - `isRegistered`: true
     - `responseSent`: true

### 5.2 Test Incoming Message from Unknown Number

1. [ ] Ask a friend or use another phone to send SMS to your Twilio number
   - From: Unknown number (not verified)
   - Content: Any text

2. [ ] Expected behavior:
   - NO response should be sent to unknown number
   - No acknowledgment, no error

3. [ ] Check Firebase:
   - Go to Firestore → `incomingMessages` collection
   - Should see new document with:
     - `phoneNumber`: The unknown number
     - `isRegistered`: false
     - `responseSent`: false

### 5.3 Test Outgoing Message

1. [ ] Call endpoint:
```bash
curl -X POST https://your-railway-app.railway.app/api/send-message \
  -H "Content-Type: application/json" \
  -d '{
    "phoneNumber": "+12025551234",
    "messageContent": "Test message from backend",
    "operatorId": "test_operator"
  }'
```

2. [ ] Expected behavior:
   - Get JSON response with status = "sent"
   - Your test phone receives SMS: `Test message from backend`

3. [ ] Check Firebase:
   - Go to Firestore → `outgoingMessages` collection
   - Should see new document with:
     - `phoneNumber`: `+12025551234`
     - `messageContent`: `Test message from backend`
     - `status`: `"sent"`

### 5.4 Test Operator Dashboard

1. [ ] Open dashboard URL: `https://your-railway-app.railway.app/`
2. [ ] Expected:
   - Login page (if auth implemented)
   - Or dashboard if no auth
3. [ ] Navigate to "Incoming Messages"
   - Should see all messages received
   - Timestamps, phone numbers, content
4. [ ] Navigate to "Outgoing Messages"
   - Should see all messages sent
   - Timestamps, recipient numbers, content
5. [ ] Try sending a message:
   - Click "Send Message"
   - Select user from dropdown
   - Enter message text
   - Click "Send"
   - Should appear in outgoing messages immediately

---

## Phase 5.5: SSH Passphrase Caching (Important)

If you set a passphrase on your SSH key, you'll be prompted for it on each git operation. To cache it:

**On Mac:**
```bash
ssh-add ~/.ssh/id_ed25519_enegron
# Enter passphrase once, it's cached for the session
```

**Add to ~/.ssh/config to persist across sessions:**
```
Host github.com-enegron
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_enegron
    IdentitiesOnly yes
    AddKeysToAgent yes
    UseKeychain yes
```

---

## Phase 6: Local Development Setup (Optional)

For testing before Railway deployment:

### 6.1 Setup Local Environment

1. [ ] Clone git repo locally
2. [ ] Create `.env.local` file (don't commit):
```
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=...
FIREBASE_PROJECT_ID=...
(etc.)
```

3. [ ] Create Python virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 6.2 Run Locally with ngrok (for Twilio webhook testing)

Twilio needs to send webhooks to a public URL. For local testing, use ngrok:

1. [ ] Download ngrok: https://ngrok.com
2. [ ] Start ngrok:
```bash
ngrok http 5000
```
3. [ ] You get a public URL like: `https://abc123def456.ngrok.io`
4. [ ] Update Twilio webhook to: `https://abc123def456.ngrok.io/twilio/incoming`
5. [ ] Run Flask locally:
```bash
python app.py
```
6. [ ] Send test SMS and see requests hit local server

---

## Phase 7: Pre-Launch Checklist

Before handoff to Claude Code:

- [x] Twilio account with phone number (via Messaging Service)
- [x] All Twilio credentials saved securely
- [x] Firebase project "messaging-ux" with Firestore database
- [x] Service account key downloaded
- [x] Test users added to Firebase
- [x] Railway project created and connected to GitHub
- [x] Environment variables set in Railway (Twilio + Firebase)
- [x] Railway URL generated: `https://sms-messaging-ux-production.up.railway.app`
- [x] Twilio webhook updated to point to Railway URL
- [ ] Send test SMS and verify acknowledgment (after Claude Code deploys backend)
- [ ] Verify logs appear in Firebase (after Claude Code deploys backend)
- [ ] All four documents reviewed and updated:
  - `01_MVP_Requirements.md` ✓
  - `02_Firestore_Data_Model.md` ✓ (updated Firebase project ID)
  - `03_Architecture_System_Design.md` ✓
  - `04_API_Webhook_Specifications.md` ✓
  - `05_Setup_Configuration_Checklist.md` ✓ (updated with Messaging Service details)
  - `06_Product_Roadmap.md` ✓

---

## Troubleshooting

### Issue: Twilio webhook not being called

**Symptoms:** Send SMS but no log entry in Firebase

**Fix:**
1. Check Twilio webhook URL is correct (go to console and verify)
2. Check Railway logs for errors
3. Verify Twilio can reach your Railway URL (check Twilio webhook logs)
4. Test with ngrok locally

### Issue: Acknowledgment not being sent to registered user

**Symptoms:** User sends SMS, doesn't receive response

**Fix:**
1. Check user exists in Firebase with status = "active"
2. Check Firebase rules allow backend to write
3. Check Twilio credentials are correct
4. Check Twilio account has credit
5. Review Railway logs for Twilio API errors

### Issue: Firebase writes failing

**Symptoms:** Messages don't appear in Firestore, backend returns errors

**Fix:**
1. Check Firebase credentials are correct
2. Check service account key is valid
3. Check Firestore is in test mode (not locked down)
4. Check Firebase rules if in production mode
5. Check project ID matches

### Issue: Rails deployment fails

**Symptoms:** Railway shows error, can't deploy

**Fix:**
1. Check `requirements.txt` has all dependencies
2. Check `Procfile` is correct
3. Check environment variables are set
4. Check Python version (should be 3.9+)
5. Review Railway build logs for specific error

---

## Security Reminders

⚠️ **DO NOT:**
- Commit `.env` files to git
- Share Twilio Auth Token or API keys
- Share Firebase service account key
- Hardcode credentials in code

✅ **DO:**
- Use environment variables (Railway manages these securely)
- Use `.gitignore` to exclude `.env` and credential files
- Rotate credentials if compromised
- Use strong operator passwords

---

## Next Steps

Once everything is working:

1. Review all four documents with Claude Code team
2. Provide Claude Code with:
   - This checklist (completed sections)
   - All configuration details
   - Firebase credentials (via secure environment variables)
   - Twilio credentials (via secure environment variables)
3. Claude Code builds full backend with:
   - Flask app with all endpoints
   - Firebase integration
   - Twilio integration
   - Dashboard UI
   - Authentication
   - Error handling
4. Deploy to Railway
5. End-to-end testing
6. Production launch

