from uuid import uuid4
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower

def avatar_path(instance, filename):
    return f'avatars/{instance.pk}/{uuid4().hex}.jpg'

class User(AbstractUser):
    name = models.CharField('nome', max_length=80)
    email = models.EmailField('e-mail', unique=True)
    bio = models.CharField('biografia', max_length=160, blank=True)
    avatar = models.ImageField('foto', upload_to=avatar_path, blank=True)

    class Meta:
        ordering = ['username']
        constraints = [models.UniqueConstraint(Lower('username'), name='unique_username_lower'),
                       models.UniqueConstraint(Lower('email'), name='unique_email_lower')]

    def __str__(self):
        return self.name or self.username

class Post(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posts')
    content = models.CharField('publicação', max_length=280)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-pk']

    def __str__(self):
        return self.content[:60]

class Follow(models.Model):
    follower = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='following_links')
    following = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='follower_links')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['follower', 'following'], name='unique_follow'),
                       models.CheckConstraint(condition=~models.Q(follower=models.F('following')), name='no_self_follow')]

class Like(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='likes')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'post'], name='unique_like')]

class Comment(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comments')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    content = models.CharField('comentário', max_length=280)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at', 'pk']

class Bookmark(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookmarks')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='bookmarks')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'post'], name='unique_bookmark')]
