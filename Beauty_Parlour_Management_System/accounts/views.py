from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from .forms import RegisterForm, normalize_phone
from .models import UserProfile
from salon.models import Appointment
from django.core.exceptions import ValidationError


def register(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = form.save()
            UserProfile.objects.create(user=user, phone=form.cleaned_data['phone'])
        login(request, user)
        messages.success(request, 'Your account is ready. Welcome!')
        return redirect('profile')
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        identifier = request.POST.get('login', '').strip()
        username = identifier
        # Exact usernames take priority; ambiguous legacy emails are not guessed.
        if not User.objects.filter(username=identifier).exists():
            candidates = User.objects.filter(email__iexact=identifier)
            if candidates.count() == 1:
                username = candidates.first().username
            else:
                try:
                    profile = UserProfile.objects.filter(phone=normalize_phone(identifier)).first()
                    if profile:
                        username = profile.user.username
                except ValidationError:
                    pass
        user = authenticate(request, username=username, password=request.POST.get('password', ''))
        if user is not None:
            login(request, user)
            target = request.POST.get('next') or request.GET.get('next', '')
            if target and url_has_allowed_host_and_scheme(target, {request.get_host()}, require_https=request.is_secure()):
                return redirect(target)
            from salon.access import manager, employee
            return redirect('dashboard' if manager(user) or employee(user) else 'profile')
        messages.error(request, 'Invalid login details. Please try again.')
    return render(request, 'accounts/login.html')


@login_required
def profile(request):
    user_profile = UserProfile.objects.filter(user=request.user).first()
    return render(request, 'accounts/profile.html', {
        'phone': user_profile.phone if user_profile else '',
        'appointments': Appointment.objects.filter(user=request.user).select_related('service','staff','invoice').order_by('-date', '-time'),
    })


@require_POST
@login_required
def logout_user(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('home')


@login_required
def edit_profile(request):
    from .forms import ProfileForm
    from salon.events import audit
    form=ProfileForm(request.POST if request.method=='POST' else None,instance=request.user)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            form.save()
            UserProfile.objects.update_or_create(user=request.user,defaults={'phone':form.cleaned_data['phone']})
            audit(request.user,'Profile updated','Customer updated contact details')
        messages.success(request,'Your profile has been updated.')
        return redirect('profile')
    return render(request,'customer_form.html',{'form':form,'title':'Edit profile'})
