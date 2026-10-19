from django.contrib.auth import login, logout, update_session_auth_hash
from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import generics, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from .models import User, Post, Follow, Like, Comment, Bookmark
from .serializers import (PublicUserSerializer, RegisterSerializer, LoginSerializer,
                          ProfileSerializer, PasswordSerializer, PostSerializer, CommentSerializer)

def users_for(viewer):
    return User.objects.filter(is_active=True).annotate(
        followers_count=Count('follower_links', filter=Q(follower_links__follower__is_active=True), distinct=True),
        following_count=Count('following_links', filter=Q(following_links__following__is_active=True), distinct=True),
        posts_count=Count('posts', distinct=True),
        is_following=Exists(Follow.objects.filter(follower=viewer, following=OuterRef('pk')))).order_by('username')

def posts_for(viewer):
    return Post.objects.filter(author__is_active=True).select_related('author').annotate(
        likes_count=Count('likes', distinct=True), comments_count=Count('comments', distinct=True),
        is_liked=Exists(Like.objects.filter(user=viewer, post=OuterRef('pk'))),
        is_saved=Exists(Bookmark.objects.filter(user=viewer, post=OuterRef('pk')))).order_by('-created_at', '-pk')

@method_decorator(ensure_csrf_cookie, name='dispatch')
class CSRFView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return Response({'csrfToken': get_token(request)})

@method_decorator(csrf_protect, name='dispatch')
class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'register'

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user = serializer.save()
        except IntegrityError:
            raise serializers.ValidationError({'detail': 'Usuário ou e-mail já cadastrado.'})
        login(request, user)
        return Response(PublicUserSerializer(users_for(user).get(pk=user.pk), context={'request': request}).data, status=201)

@method_decorator(csrf_protect, name='dispatch')
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        login(request, serializer.validated_data['user'])
        return Response({'detail': 'Login realizado.'})

class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response(status=204)

class MeView(APIView):
    def get(self, request):
        return Response(PublicUserSerializer(users_for(request.user).get(pk=request.user.pk), context={'request': request}).data)

    def patch(self, request):
        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self.get(request)

class PasswordView(APIView):
    def post(self, request):
        serializer = PasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save(update_fields=['password'])
        update_session_auth_hash(request, request.user)
        return Response({'detail': 'Senha atualizada.'})

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PublicUserSerializer
    lookup_field = 'username'
    lookup_value_regex = '[a-z0-9_]+'

    def get_queryset(self):
        queryset = users_for(self.request.user)
        search = self.request.query_params.get('search', '').strip()[:80]
        if search:
            queryset = queryset.filter(Q(username__icontains=search) | Q(name__icontains=search))
        return queryset

    @action(detail=False)
    def suggestions(self, request):
        queryset = users_for(request.user).exclude(pk=request.user.pk).filter(is_following=False)
        return self._list(queryset)

    def _list(self, queryset):
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @action(detail=True, methods=['get'])
    def followers(self, request, username=None):
        user = self.get_object()
        return self._list(users_for(request.user).filter(following_links__following=user))

    @action(detail=True, methods=['get'])
    def following(self, request, username=None):
        user = self.get_object()
        return self._list(users_for(request.user).filter(follower_links__follower=user))

    @action(detail=True, methods=['put', 'delete'])
    def follow(self, request, username=None):
        target = self.get_object()
        if target == request.user:
            raise serializers.ValidationError({'detail': 'Você não pode seguir a si mesmo.'})
        if request.method == 'PUT':
            Follow.objects.get_or_create(follower=request.user, following=target)
        else:
            Follow.objects.filter(follower=request.user, following=target).delete()
        return Response(self.get_serializer(users_for(request.user).get(pk=target.pk)).data)

class PostViewSet(viewsets.ModelViewSet):
    serializer_class = PostSerializer
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        queryset = posts_for(self.request.user)
        if self.action == 'feed':
            return queryset.filter(author__follower_links__follower=self.request.user)
        if self.action == 'saved':
            return queryset.filter(bookmarks__user=self.request.user)
        if self.action == 'list':
            author = self.request.query_params.get('author')
            if author:
                queryset = queryset.filter(author__username=author)
            search = self.request.query_params.get('search', '').strip()[:80]
            if search:
                queryset = queryset.filter(content__icontains=search)
        return queryset

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.author_id != self.request.user.pk:
            raise PermissionDenied('Você só pode editar suas próprias publicações.')
        serializer.save()

    def perform_destroy(self, instance):
        if instance.author_id != self.request.user.pk:
            raise PermissionDenied('Você só pode excluir suas próprias publicações.')
        instance.delete()

    @action(detail=False)
    def feed(self, request):
        return self.list(request)

    @action(detail=True, methods=['put', 'delete'])
    def like(self, request, pk=None):
        post = self.get_object()
        if request.method == 'PUT':
            Like.objects.get_or_create(user=request.user, post=post)
        else:
            Like.objects.filter(user=request.user, post=post).delete()
        return Response(self.get_serializer(posts_for(request.user).get(pk=post.pk)).data)

    @action(detail=False)
    def saved(self, request):
        return self.list(request)

    @action(detail=True, methods=['put', 'delete'])
    def bookmark(self, request, pk=None):
        post = self.get_object()
        if request.method == 'PUT':
            Bookmark.objects.get_or_create(user=request.user, post=post)
        else:
            Bookmark.objects.filter(user=request.user, post=post).delete()
        return Response(self.get_serializer(posts_for(request.user).get(pk=post.pk)).data)

class CommentListCreateView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer

    def get_post(self):
        return get_object_or_404(Post, pk=self.kwargs['post_id'], author__is_active=True)

    def get_queryset(self):
        return self.get_post().comments.filter(author__is_active=True).select_related('author')

    def perform_create(self, serializer):
        serializer.save(author=self.request.user, post=self.get_post())

class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CommentSerializer
    queryset = Comment.objects.filter(author__is_active=True, post__author__is_active=True).select_related('author')

    def perform_update(self, serializer):
        if serializer.instance.author_id != self.request.user.pk:
            raise PermissionDenied('Você só pode editar seus próprios comentários.')
        serializer.save()

    def perform_destroy(self, instance):
        if instance.author_id != self.request.user.pk:
            raise PermissionDenied('Você só pode excluir seus próprios comentários.')
        instance.delete()
