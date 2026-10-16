"""Store avatars remotely; only their delivery URL and asset ID live in Postgres."""
from io import BytesIO
import logging
import uuid

import cloudinary.uploader
from PIL import Image, ImageOps
from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)


class AvatarUploadError(Exception):
    pass


def cloudinary_options():
    return {
        'cloud_name': settings.CLOUDINARY_CLOUD_NAME,
        'api_key': settings.CLOUDINARY_API_KEY,
        'api_secret': settings.CLOUDINARY_API_SECRET,
        'secure': True,
        'timeout': 20,
    }


def cloudinary_ready():
    return all(cloudinary_options()[name] for name in ('cloud_name', 'api_key', 'api_secret'))


def delete_avatar(public_id):
    if not public_id or not cloudinary_ready():
        return
    try:
        cloudinary.uploader.destroy(public_id, invalidate=True, **cloudinary_options())
    except Exception:
        # A CDN cleanup failure must not undo an already saved profile.
        logger.warning('Could not remove an old avatar from image storage.')


def save_profile(form):
    avatar = form.cleaned_data.get('avatar')
    remove = form.cleaned_data.get('remove_avatar', False)
    asset = None
    if avatar:
        try:
            avatar.seek(0)
            with Image.open(avatar) as image:
                image = ImageOps.exif_transpose(image).convert('RGB')
                image = ImageOps.fit(image, (512, 512), method=Image.Resampling.LANCZOS)
                content = BytesIO()
                image.save(content, format='JPEG', quality=85)
            content.seek(0)
            asset = cloudinary.uploader.upload(
                content, public_id=f'linkify/avatars/{form.instance.pk}/{uuid.uuid4().hex}',
                resource_type='image', overwrite=False, **cloudinary_options(),
            )
            if not asset.get('secure_url', '').startswith('https://') or not asset.get('public_id'):
                raise ValueError('Invalid avatar storage response')
        except Exception as exc:
            logger.warning('Avatar upload failed (%s).', type(exc).__name__)
            raise AvatarUploadError('Your photo could not be uploaded. Please try again.') from exc

    try:
        with transaction.atomic():
            user = form.save()
            if asset or remove:
                from .models import Profile
                profile = Profile.objects.select_for_update().get(user=user)
                old_id = profile.avatar_public_id
                profile.avatar_url = asset['secure_url'] if asset else ''
                profile.avatar_public_id = asset['public_id'] if asset else ''
                profile.save(update_fields=['avatar_url', 'avatar_public_id'])
                user.profile = profile
                if old_id:
                    transaction.on_commit(lambda: delete_avatar(old_id))
    except Exception:
        if asset:
            delete_avatar(asset['public_id'])
        raise
    return user
