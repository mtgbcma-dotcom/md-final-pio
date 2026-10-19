from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Post, Follow, Like, Comment

@admin.register(User)
class PioUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (('Perfil Pio', {'fields': ('name', 'bio', 'avatar')}),)

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['author', 'content', 'created_at']
    search_fields = ['content', 'author__username']

admin.site.register([Follow, Like, Comment])
admin.site.site_header = 'Pio · Administração'
