import re
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import UserProfile


def normalize_phone(value):
    value = re.sub(r"[\s()-]", "", value)
    if not re.fullmatch(r"\+?[0-9]{10,15}", value):
        raise forms.ValidationError("Enter 10–15 digits, optionally starting with +.")
    return value


class RegisterForm(UserCreationForm):
    email = forms.EmailField()
    phone = forms.CharField(max_length=20)

    class Meta:
        model = User
        fields = ['username', 'email', 'phone', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account already uses this email.")
        return email

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data['phone'])
        if UserProfile.objects.filter(phone=phone).exists():
            raise forms.ValidationError("An account already uses this phone number.")
        return phone


class ProfileForm(forms.ModelForm):
    phone=forms.CharField(max_length=20)
    email=forms.EmailField()
    class Meta:
        model=User
        fields=['first_name','last_name','email']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        profile=UserProfile.objects.filter(user=self.instance).first()
        self.initial['phone']=profile.phone if profile else ''
        for field in self.fields.values():field.widget.attrs['class']='form-control'
    def clean_email(self):
        email=self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():raise forms.ValidationError('Email is already used.')
        return email
    def clean_phone(self):
        phone=normalize_phone(self.cleaned_data['phone'])
        if UserProfile.objects.filter(phone=phone).exclude(user=self.instance).exists():raise forms.ValidationError('Phone number is already used.')
        return phone
