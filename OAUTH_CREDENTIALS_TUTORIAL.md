# Google aur GitHub OAuth Credentials Tutorial

Ye tutorial aapko in chaar values ko hasil karne aur project ke `.env` file mein add karne ka exact tareeqa batata hai:

```env
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
```

**Important:** `CLIENT_SECRET` ko kabhi GitHub, screenshot, chat, WhatsApp, ya frontend JavaScript mein share na karein. Google ke mutabiq client secret create hone ke waqt full form mein dikh sakta hai, is liye usay turant secure jagah save karna chahiye. [1] [2]

## 1. Pehle local app ka exact URL decide karein

Agar aap app Docker ke saath `localhost` par chala rahe hain, to browser mein ye URL use karein:

```text
http://localhost:8000
```

Is tutorial ke local callback URLs ye hain:

```text
Google:  http://localhost:8000/accounts/google/login/callback/
GitHub: http://localhost:8000/accounts/github/login/callback/
```

**`localhost` aur `127.0.0.1` ko mix na karein.** OAuth provider ke callback URL mein jo host likhenge, browser mein bhi wahi host use karein. Google redirect URI ko exact match karta hai; scheme (`http`/`https`), host, path aur trailing slash match honi chahiye. [1]

## 2. Google Client ID aur Client Secret hasil karna

### Step 2.1 — Google Cloud Console kholen

Official Google Auth Platform Clients page open karein:

[Google Auth Platform Clients](https://console.developers.google.com/auth/clients)

Agar Google login maange to apne Google account se sign in karein.

### Step 2.2 — Naya project banayein

Agar project pehle se nahi hai:

1. **Create project** par click karein.
2. Project name rakhein, misal ke taur par `Linkify Media Login`.
3. **Create** par click karein.
4. Upar project selector se isi project ko select kar lein.

Google ke current flow mein pehle project aur application registration complete karni hoti hai, us ke baad OAuth client create hota hai. [2]

### Step 2.3 — OAuth consent / branding configure karein

Google Cloud Console mein:

1. **Google Auth Platform** ya **APIs & Services** section open karein.
2. **Branding**, **OAuth consent screen**, ya jo equivalent setup option nazar aaye usay open karein.
3. App name mein `Linkify Media` likhein.
4. User support email select karein.
5. Developer contact email add karein.
6. Agar app **External** hai to testing ke liye apna Google account **Test users** mein add karein.
7. Scopes mein is project ke liye basic identity/email scopes hi rakhein: `profile` aur `email`.
8. Save/continue karte hue setup complete karein.

Aapko Drive, Calendar ya doosri unnecessary permissions add karne ki zaroorat nahi. Is project ka Google provider `profile` aur `email` scopes use karta hai. django-allauth ke provider instructions bhi consent screen par product name aur email provide karne ko kehte hain. [4]

### Step 2.4 — Web OAuth client banayein

Google Cloud Console mein:

1. **Google Auth Platform → Clients** open karein, ya **APIs & Services → Credentials** par jayein.
2. **Create Client** / **Create credentials** par click karein.
3. Application type mein **Web application** select karein.
4. Name rakhein: `Linkify Media Web`.
5. **Authorized JavaScript origins** mein ye add karein:

```text
http://localhost:8000
```

6. **Authorized redirect URIs** mein ye exact URL add karein:

```text
http://localhost:8000/accounts/google/login/callback/
```

7. **Create** par click karein.
8. Google aapko **Client ID** aur **Client Secret** dikhayega.
9. Dono ko copy karke temporary secure password manager ya encrypted notes mein rakh lein.

Google ki official guidance ke mutabiq Web application OAuth client mein authorized redirect URI dena zaroori hai, aur client secret ko public source tree mein store nahi karna chahiye. [1] [2]

### Step 2.5 — Production callback baad mein add karein

Jab real HTTPS domain ready ho, Google client ke Authorized redirect URIs mein production callback add karein:

```text
https://your-domain.com/accounts/google/login/callback/
```

Production mein `http://` nahi, **`https://`** use karein. Local aur production dono callback URLs ek hi OAuth client mein add kiye ja sakte hain.

## 3. GitHub Client ID aur Client Secret hasil karna

### Step 3.1 — GitHub Developer Settings kholen

GitHub mein login karke ye page open karein:

[GitHub Developer Settings](https://github.com/settings/developers)

Phir:

1. **OAuth Apps** par click karein.
2. **New OAuth App** par click karein.

GitHub ke official steps mein profile picture → **Settings** → **Developer settings** → **OAuth Apps** → **New OAuth App** ka flow diya gaya hai. [3]

### Step 3.2 — GitHub OAuth App form fill karein

Form mein ye values use karein:

| GitHub field | Local value |
|---|---|
| Application name | `Linkify Media` |
| Homepage URL | `http://localhost:8000` |
| Application description | `Linkify Media developer login` |
| Authorization callback URL | `http://localhost:8000/accounts/github/login/callback/` |

Phir **Register application** par click karein.

GitHub ke official documentation ke mutabiq Authorization callback URL woh URL hota hai jahan successful authorization ke baad GitHub user ko wapas bhejta hai. [3]

### Step 3.3 — Client ID aur secret generate karein

App banne ke baad GitHub application page par:

1. **Client ID** copy karein.
2. **Generate a new client secret** par click karein.
3. Jo secret foran show ho usay copy karke secure jagah save karein.
4. Secret ko dobara public text, screenshot, ya repository mein na daalein.

Agar secret leak ho jaye to GitHub par purana secret revoke karke naya generate karein.

### Step 3.4 — Production callback baad mein add karein

GitHub OAuth app ke callback field mein production URL set karein:

```text
https://your-domain.com/accounts/github/login/callback/
```

Agar local aur production dono test karne hain, GitHub OAuth app ke current form mein additional callback URLs ka option available ho sakta hai. Agar aapka setup sirf ek callback allow kare, to testing ke waqt local URL aur deployment ke waqt production URL replace karein. [3]

## 4. `.env` file mein values add karna

Project ke root folder mein `.env` file honi chahiye. Agar nahi hai:

```bash
cp .env.example .env
```

Phir `.env` mein placeholders replace karein:

```env
ACCOUNT_EMAIL_VERIFICATION=mandatory

GOOGLE_CLIENT_ID=1234567890-abcdefg.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-google-secret

GITHUB_CLIENT_ID=Iv1.xxxxxxxxxxxxxxxx
GITHUB_CLIENT_SECRET=your-github-secret

RESEND_API_KEY=re_xxxxxxxxxxxxxxxxx
DEFAULT_FROM_EMAIL=support@your-verified-domain.com
```

**Actual secrets yahan example ki tarah paste na karein.** Upar wali values sirf format samjhane ke liye hain.

Project ki current `core/settings.py` file Google aur GitHub credentials ko in environment variables se load karti hai, is liye credentials Python files mein hardcode karne ki zaroorat nahi.

## 5. Resend email verification setup

Email verification ke liye:

1. [Resend](https://resend.com/) par account banayein ya login karein.
2. API key create karein.
3. Jo sending domain aap `DEFAULT_FROM_EMAIL` mein use karna chahte hain, usay Resend mein verify karein.
4. API key `.env` mein `RESEND_API_KEY` ke saamne add karein.
5. `DEFAULT_FROM_EMAIL` ko verified domain ke email par set karein.

Example:

```env
RESEND_API_KEY=re_xxxxxxxxx
DEFAULT_FROM_EMAIL=support@linkifymedia.com
```

Agar `RESEND_API_KEY` empty ho to local development mein emails console output mein print honge. Is case mein verification URL Docker logs ya terminal output mein milega.

## 6. App restart karna

`.env` change karne ke baad containers recreate karein:

```bash
docker compose down
docker compose up --build -d
```

Logs dekhne ke liye:

```bash
docker compose logs -f web
```

Local app open karein:

```text
http://localhost:8000/accounts/login/
```

Aapko login page par **Continue with Google** aur **Continue with GitHub** buttons nazar aayenge.

## 7. Test karne ka tareeqa

### Google test

1. Login page open karein.
2. **Continue with Google** click karein.
3. Google consent screen par apna test account select karein.
4. Allow/Continue karein.
5. App ko `/dashboard/` par redirect hona chahiye.

### GitHub test

1. Login page open karein.
2. **Continue with GitHub** click karein.
3. GitHub authorization approve karein.
4. App ko `/dashboard/` par redirect hona chahiye.

### Email/password test

1. Signup page open karein.
2. Email/password se account create karein.
3. Verification email open karein.
4. Verify link par click karein.
5. Profile page se password change, verification status, aur account deletion options check karein.

## 8. Common errors aur fixes

| Error | Common reason | Fix |
|---|---|---|
| `redirect_uri_mismatch` | Callback URL exact match nahi kar raha | Provider console mein trailing slash, host, port aur scheme check karein |
| `SocialApp matching query does not exist` | Provider credentials load nahi ho rahe ya allauth SocialApp required hai | `.env` values verify karke container restart karein; agar version admin SocialApp maange to `/admin/socialaccount/socialapp/` mein provider add karein |
| `invalid_client` | Client ID ya secret wrong hai | Secret ko dobara copy karein; quotes/extra spaces remove karein |
| Google `access blocked` | OAuth consent screen/test user incomplete | Google Auth Platform mein test user add karein aur app branding complete karein |
| GitHub callback error | Wrong callback URL ya app credentials mismatch | GitHub OAuth app mein exact `/accounts/github/login/callback/` URL set karein |
| Verification email nahi aa rahi | Resend key/domain/from email issue | Resend domain verify karein, logs check karein, `DEFAULT_FROM_EMAIL` verified domain ka rakhein |
| `localhost` vs `127.0.0.1` issue | Browser aur provider callback host different | Dono jagah same host use karein |

## 9. Final security checklist

- `.env` ko Git mein commit na karein.
- Client secrets ko frontend JavaScript mein kabhi na daalein.
- Production mein HTTPS callbacks use karein.
- Agar koi secret leak ho jaye to Google/GitHub par immediately rotate/revoke karein.
- OAuth app mein sirf required scopes rakhein.
- Testing ke baad Google test users aur GitHub authorization ko review karein.

## References

[1]: https://developers.google.com/identity/protocols/oauth2/web-server "Google: Using OAuth 2.0 for Web Server Applications"
[2]: https://support.google.com/cloud/answer/15549257?hl=en "Google Cloud: Manage OAuth Clients"
[3]: https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app "GitHub: Creating an OAuth app"
[4]: https://docs.allauth.org/en/dev/socialaccount/providers/google.html "django-allauth: Google provider"
