from django.urls import path
from . import views
urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('profile/', views.profile, name='profile'),
    path('logout/', views.logout_user, name='logout'),
]

from django.contrib.auth import views as auth_views
urlpatterns += [
    path('profile/edit/',views.edit_profile,name='edit_profile'),
    path('password-reset/',auth_views.PasswordResetView.as_view(template_name='accounts/reset_form.html',email_template_name='accounts/reset_email.txt',subject_template_name='accounts/reset_subject.txt'),name='password_reset'),
    path('password-reset/sent/',auth_views.PasswordResetDoneView.as_view(template_name='accounts/reset_done.html'),name='password_reset_done'),
    path('reset/<uidb64>/<token>/',auth_views.PasswordResetConfirmView.as_view(template_name='accounts/reset_confirm.html'),name='password_reset_confirm'),
    path('reset/complete/',auth_views.PasswordResetCompleteView.as_view(template_name='accounts/reset_complete.html'),name='password_reset_complete'),
]
