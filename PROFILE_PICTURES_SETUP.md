# Profile pictures and names

Users can edit their first/last name, upload or replace their photo, and remove
their current photo from `/profile/`. The saved name and avatar appear on the
profile page, site navigation, and dashboard header. Accounts without photos
show an initial.

## Cloudinary credentials

Create a Cloudinary account and copy the Cloud name, API key, and API secret
from its product environment/API credentials settings. Add these to local `.env`
and to the environment settings of both Vercel and Render if both run Django:

```env
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
```

Keep the API secret on the server. This integration uses signed server uploads;
no unsigned upload preset or browser credentials are required. Photos are stored
in Cloudinary and their URL/asset ID in PostgreSQL.

Install the updated Python requirements, apply migrations, and redeploy:

```sh
python -m pip install -r requirements.txt
python manage.py migrate --noinput
```

The migration adds two optional fields to existing profiles. Name edits continue
to work when Cloudinary is unconfigured; photo uploads become available after
credentials are added and the app restarts.

## Validation

Uploads accept real JPG, PNG, and WebP files up to 5 MB and 16 megapixels. Images
are oriented, cropped to 512x512, and re-encoded as JPEG without original metadata.
Replacing/removing a photo attempts to delete the old Cloudinary asset after the
database update commits. Failed uploads leave profile data unchanged.

The session-authenticated profile API also accepts multipart PATCH requests with
`avatar` or `remove_avatar`, and returns `avatar_url`. Omitted name fields are
preserved. Clients cannot submit another user's ID to change their photo.

Automated tests mock Cloudinary. A real upload needs your Cloudinary credentials;
after deploying, save a photo on `/profile/`, refresh, and check the dashboard.
