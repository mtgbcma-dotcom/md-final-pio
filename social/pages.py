from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_safe

@require_safe
@ensure_csrf_cookie
def auth_page(request, register=False):
    if request.user.is_authenticated:
        return redirect('home')
    return render(request, 'auth.html', {'register': register})

@require_safe
@login_required
@ensure_csrf_cookie
def app_page(request, **kwargs):
    return render(request, 'app.html')
