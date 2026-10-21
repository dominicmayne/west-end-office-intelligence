# Switching RideWorld from demo to live

Until these steps are done, every page stays in demo mode exactly as it is now.

1. Go to supabase.com, sign in with GitHub, and click **New project**. Name it `qrworlds` and pick the London region. Save the database password in your password manager. You won't need it here.
2. In the project, open **SQL Editor**, then **New query**. Paste in everything from `schema.sql` and press **Run**. It should say "Success".
3. Add the pilot rides. Open **Table Editor**, then `rides`, then **Insert row**, once per ride. Use Craig's ride number as the `id` (for example `RO-0001`), plus the name, centre and where the ride sits.
4. Open **Authentication**, then **URL Configuration**:
   - Set **Site URL** to `https://www.qrworlds.co.uk`.
   - Add `https://www.qrworlds.co.uk/engineers` under **Redirect URLs**.
5. Open **Authentication**, then **Users**, then **Add user**, then **Send invitation**. Do this once for each person allowed into the engineer log (you, Craig, his engineers). Nobody else can sign in.
6. Open **Project Settings**, then **API**. Copy the **Project URL** and the **anon public** key into `qrworlds/live.js`, between the quotes for `url` and `key`.
   - Do this yourself in GitHub, by pressing the pencil icon on the file.
   - The anon key is designed to be public. Never paste the **service_role** key anywhere.
7. Commit. Vercel redeploys, and the stickers for rides in the table go live.

What then happens:
- **Scanning a sticker** for a ride in the table counts a scan, and **Ride not working?** sends a real report.
- **Rides not in the table**, like the demo `RO-0412`, stay in demo mode.
- **Engineer log:** `qrworlds.co.uk/engineers` is the private log. Staff sign in with an emailed link and press **Mark fixed** to close a fault.
- **Sample log:** `/rideworld/log` stays the sample log for demos.
- **Weekly numbers:** these are in the `weekly_numbers` view. They are not emailed yet.
