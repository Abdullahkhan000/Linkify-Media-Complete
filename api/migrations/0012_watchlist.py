from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('api', '0011_profile_avatar'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(
        name='WatchlistItem',
        fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('tmdb_id', models.PositiveIntegerField()),
            ('media_type', models.CharField(max_length=5, choices=[('movie', 'Movie'), ('tv', 'TV show')])),
            ('title', models.CharField(max_length=300)),
            ('poster_url', models.URLField(max_length=500, blank=True, default='')),
            ('release_year', models.CharField(max_length=4, blank=True, default='')),
            ('overview', models.TextField(blank=True, default='')),
            ('favorite', models.BooleanField(default=False)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='watchlist', to=settings.AUTH_USER_MODEL)),
        ],
        options={'ordering': ['-created_at', '-id'], 'constraints': [models.UniqueConstraint(fields=('user', 'tmdb_id', 'media_type'), name='unique_user_watchlist_media')]},
    )]
