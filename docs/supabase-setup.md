# Setting up sign-in and saved games (Supabase)

The web app keeps each signed-in player's game in a Supabase project (R11.6,
NFR6). Until `web/account.json` names a project, the page has no sign-in and
everyone plays as a guest, with games saved on their device (R11.7a).

These steps are done once, by the owner, in the Supabase and Google
dashboards. Only the project's address and its **publishable** (public) key
go in the repository; the Google client secret stays in Supabase.

## 1. Create the Supabase project

1. Sign in at <https://supabase.com/dashboard> and create a new project
   (the free plan is enough). Note: a free project pauses after about a week
   with no visits; resume it from the dashboard.
2. Open **SQL Editor**, paste all of [`supabase/schema.sql`](../supabase/schema.sql),
   and run it. It creates the `saves` table, the rules that let each player
   read and change only their own save (R11.9), and `delete_account` (R11.11).
3. Open **Project Settings → API Keys** and copy the project URL
   (`https://<ref>.supabase.co`) and the publishable key (`sb_publishable_…`;
   the older `anon` key also works). Never use the `secret` or
   `service_role` key in the app.

## 2. Allowed return addresses (R11.15)

In **Authentication → URL Configuration**:

- **Site URL:** `https://issy16.github.io/meowdoku/`
- **Redirect URLs:** `https://issy16.github.io/meowdoku/` and
  `http://localhost:8000/meowdoku/` (and nothing else)

## 3. Google sign-in

1. In <https://console.cloud.google.com/>, create a project (or pick one),
   then open **APIs & Services → OAuth consent screen** and fill in the app
   name (Meowdoku), your support email, and publish it as **External**.
   The scopes needed are only `email`, `profile`, and `openid`.
2. Open **APIs & Services → Credentials → Create credentials → OAuth client
   ID**, type **Web application**:
   - **Authorized JavaScript origins:** `https://issy16.github.io` and
     `http://localhost:8000`
   - **Authorized redirect URIs:** `https://<ref>.supabase.co/auth/v1/callback`
3. Copy the client ID and client secret into Supabase under
   **Authentication → Sign In / Providers → Google**, and enable it.

## 4. Email sign-in links

**Authentication → Sign In / Providers → Email** is on by default. Players
type their email and get a link that signs them in. Supabase's built-in
mail sender only sends a few emails an hour, which is fine for testing; for
more players, add your own SMTP server under **Authentication → Emails →
SMTP Settings**.

The link signs the player in on the browser where they asked for it, so
they should open it on the same device.

## 5. Tell the app about the project

Put the URL and publishable key in `web/account.json`:

```json
{
  "url": "https://<ref>.supabase.co",
  "key": "sb_publishable_..."
}
```

Then check locally at <http://localhost:8000/meowdoku/> (`python web/assemble.py --serve`),
commit, and push; GitHub Pages publishes it.

## Later: Sign in with Apple

Needs a paid Apple Developer account (R10.3, R11.6). Once there is one,
create a Services ID and key in Apple's developer site, enable **Apple**
under Supabase's providers, and add an Apple button next to Google.
