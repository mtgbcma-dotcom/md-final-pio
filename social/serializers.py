import re
from io import BytesIO
from PIL import Image, ImageOps, UnidentifiedImageError
from django.contrib.auth import authenticate, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from rest_framework import serializers
from .models import User, Post, Comment

class PublicUserSerializer(serializers.ModelSerializer):
    followers_count = serializers.IntegerField(read_only=True, default=0)
    following_count = serializers.IntegerField(read_only=True, default=0)
    posts_count = serializers.IntegerField(read_only=True, default=0)
    is_following = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = User
        fields = ['id', 'username', 'name', 'bio', 'avatar', 'date_joined',
                  'followers_count', 'following_count', 'posts_count', 'is_following']

class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=3, max_length=20)
    name = serializers.CharField(max_length=80)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirm = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_username(self, value):
        value = value.lower()
        if not re.fullmatch(r'[a-z0-9_]{3,20}', value):
            raise serializers.ValidationError('Use de 3 a 20 letras, números ou sublinhado, sem espaços.')
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('Este nome de usuário já está em uso.')
        return value

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Este e-mail já está em uso.')
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('password_confirm'):
            raise serializers.ValidationError({'password_confirm': 'As senhas precisam ser iguais.'})
        candidate = User(username=attrs['username'], name=attrs['name'], email=attrs['email'])
        try:
            password_validation.validate_password(attrs['password'], candidate)
        except DjangoValidationError as error:
            raise serializers.ValidationError({'password': error.messages})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        user = authenticate(request=self.context['request'], username=attrs['username'].lower(), password=attrs['password'])
        if not user:
            raise serializers.ValidationError('Usuário ou senha inválidos.')
        return {'user': user}

class ProfileSerializer(serializers.ModelSerializer):
    remove_avatar = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = User
        fields = ['name', 'bio', 'avatar', 'remove_avatar']
        extra_kwargs = {'name': {'required': False}, 'bio': {'required': False}, 'avatar': {'required': False}}

    def validate_avatar(self, value):
        if value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError('A foto deve ter no máximo 2 MB.')
        try:
            value.seek(0)
            with Image.open(value) as image:
                if image.format not in {'JPEG', 'PNG', 'WEBP'} or image.width * image.height > 16_000_000:
                    raise serializers.ValidationError('Use uma imagem JPG, PNG ou WebP de até 16 megapixels.')
                image.load()
                image = ImageOps.exif_transpose(image).convert('RGB')
                image = ImageOps.fit(image, (512, 512), method=Image.Resampling.LANCZOS)
                buffer = BytesIO()
                image.save(buffer, 'JPEG', quality=88)
                return ContentFile(buffer.getvalue(), name='avatar.jpg')
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            raise serializers.ValidationError('Não foi possível ler esta imagem.')

    def validate(self, attrs):
        if attrs.get('remove_avatar') and attrs.get('avatar'):
            raise serializers.ValidationError({'avatar': 'Escolha uma nova foto ou remova a atual.'})
        return attrs

    def update(self, instance, validated_data):
        remove = validated_data.pop('remove_avatar', False)
        old = instance.avatar.name
        storage = instance.avatar.storage
        if remove:
            validated_data['avatar'] = ''
        instance = super().update(instance, validated_data)
        if old and instance.avatar.name != old:
            transaction.on_commit(lambda: storage.delete(old))
        return instance

class PasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirm = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        user = self.context['request'].user
        if not user.check_password(attrs['current_password']):
            raise serializers.ValidationError({'current_password': 'A senha atual está incorreta.'})
        if attrs['new_password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'As senhas precisam ser iguais.'})
        try:
            password_validation.validate_password(attrs['new_password'], user)
        except DjangoValidationError as error:
            raise serializers.ValidationError({'new_password': error.messages})
        return attrs

class PostSerializer(serializers.ModelSerializer):
    author = PublicUserSerializer(read_only=True)
    likes_count = serializers.IntegerField(read_only=True, default=0)
    comments_count = serializers.IntegerField(read_only=True, default=0)
    is_liked = serializers.BooleanField(read_only=True, default=False)
    is_saved = serializers.BooleanField(read_only=True, default=False)
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ['id', 'author', 'content', 'created_at', 'updated_at', 'likes_count', 'comments_count', 'is_liked', 'is_saved', 'is_owner']
        read_only_fields = ['created_at', 'updated_at']

    def get_is_owner(self, obj):
        return obj.author_id == self.context['request'].user.pk

    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError('Escreva algo antes de publicar.')
        return value.strip()

class CommentSerializer(serializers.ModelSerializer):
    author = PublicUserSerializer(read_only=True)
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'post', 'author', 'content', 'created_at', 'updated_at', 'is_owner']
        read_only_fields = ['post', 'created_at', 'updated_at']

    def get_is_owner(self, obj):
        return obj.author_id == self.context['request'].user.pk

    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError('Escreva um comentário.')
        return value.strip()
