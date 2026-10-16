from io import BytesIO
from unittest.mock import patch

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings


def photo():
    data = BytesIO()
    Image.new('RGB', (80, 100), 'blue').save(data, format='PNG')
    return SimpleUploadedFile('avatar.png', data.getvalue(), content_type='image/png')


@override_settings(
    CLOUDINARY_CLOUD_NAME='test-cloud', CLOUDINARY_API_KEY='test-key',
    CLOUDINARY_API_SECRET='test-secret', SECURE_SSL_REDIRECT=False,
)
class ProfilePhotoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='profile_owner', email='owner@example.com', password='Strong-password-748!',
        )
        self.client.force_login(self.user)
        self.data = {'username': self.user.username, 'first_name': 'Abdullah', 'last_name': 'Khan'}

    def test_name_update_works_without_photo_credentials(self):
        with override_settings(CLOUDINARY_API_SECRET=''):
            response = self.client.post('/profile/', self.data)
        self.assertRedirects(response, '/profile/')
        self.user.refresh_from_db()
        self.assertEqual(self.user.get_full_name(), 'Abdullah Khan')
        self.assertContains(self.client.get('/profile/'), 'Abdullah Khan')

    @patch('api.avatars.cloudinary.uploader.upload')
    def test_uploaded_photo_is_resized_saved_and_displayed(self, upload):
        upload.return_value = {'secure_url': 'https://res.cloudinary.com/test/avatar.jpg', 'public_id': 'new-id'}
        response = self.client.post('/profile/', {**self.data, 'avatar': photo()})
        self.assertRedirects(response, '/profile/')
        profile = self.user.profile
        profile.refresh_from_db()
        self.assertEqual(profile.avatar_public_id, 'new-id')
        self.assertContains(self.client.get('/profile/'), profile.avatar_url)
        self.assertContains(self.client.get('/dashboard/'), profile.avatar_url)
        self.assertTrue(upload.call_args.kwargs['public_id'].startswith(f'linkify/avatars/{self.user.pk}/'))
        encoded = upload.call_args.args[0]
        encoded.seek(0)
        with Image.open(encoded) as image:
            self.assertEqual(image.size, (512, 512))
            self.assertEqual(image.format, 'JPEG')

    @patch('api.avatars.cloudinary.uploader.upload')
    def test_disguised_file_is_rejected_without_changing_name(self, upload):
        file = SimpleUploadedFile('bad.png', b'<script>bad</script>', content_type='image/png')
        response = self.client.post('/profile/', {**self.data, 'avatar': file})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['profile_form'].errors.get('avatar'))
        upload.assert_not_called()
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, '')

    @patch('api.avatars.cloudinary.uploader.upload', side_effect=RuntimeError('provider secret details'))
    def test_upload_outage_preserves_profile_and_returns_friendly_error(self, upload):
        response = self.client.post('/profile/', {**self.data, 'avatar': photo()})
        self.assertContains(response, 'Your photo could not be uploaded')
        self.assertNotContains(response, 'provider secret details')
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, '')

    @patch('api.avatars.cloudinary.uploader.destroy')
    def test_removal_only_deletes_current_users_photo(self, destroy):
        profile = self.user.profile
        profile.avatar_url = 'https://res.cloudinary.com/test/old.jpg'
        profile.avatar_public_id = 'old-id'
        profile.save()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/profile/', {**self.data, 'remove_avatar': 'on'})
        self.assertRedirects(response, '/profile/')
        profile.refresh_from_db()
        self.assertEqual(profile.avatar_url, '')
        self.assertEqual(profile.avatar_public_id, '')
        self.assertEqual(destroy.call_args.args, ('old-id',))

    @patch('api.avatars.cloudinary.uploader.upload')
    def test_avatar_only_api_patch_preserves_name_and_other_users(self, upload):
        from rest_framework.test import APIClient
        other = get_user_model().objects.create_user(username='another_owner')
        upload.return_value = {'secure_url': 'https://res.cloudinary.com/test/new.jpg', 'public_id': 'api-id'}
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.patch('/api/v1/account/profile/', {'avatar': photo(), 'user_id': other.pk}, format='multipart')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['avatar_url'], upload.return_value['secure_url'])
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'profile_owner')
        self.assertEqual(other.profile.avatar_url, '')

    def test_upload_without_configuration_gives_field_error(self):
        with override_settings(CLOUDINARY_API_SECRET=''):
            response = self.client.post('/profile/', {**self.data, 'avatar': photo()})
        self.assertContains(response, 'Photo uploads are temporarily unavailable')

    @patch('api.avatars.cloudinary.uploader.upload')
    def test_oversized_file_is_rejected(self, upload):
        file = photo()
        file.size = 6 * 1024 * 1024
        from .forms import ProfileUpdateForm
        form = ProfileUpdateForm(self.data, {'avatar': file}, instance=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('smaller than 5 MB', str(form.errors['avatar']))
        upload.assert_not_called()
