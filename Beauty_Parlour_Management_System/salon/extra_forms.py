from decimal import Decimal
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from .models import Package,Product,ScheduleBlock,SalonSettings,WaitlistEntry,Review
from .forms import StyledForm

class StyledModelForm(StyledForm,forms.ModelForm):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.style()
        for field in self.fields.values():
            if isinstance(field.widget,forms.CheckboxInput): field.widget.attrs['class']='form-check-input'

class PackageForm(StyledModelForm):
    class Meta:
        model=Package
        fields=['name','services','discount','active','valid_until']
        widgets={'valid_until':forms.DateInput(attrs={'type':'date'})}
    def clean(self):
        d=super().clean();services=d.get('services',[]);discount=d.get('discount',0)
        if discount<0 or discount>sum(x.price for x in services): self.add_error('discount','Discount must be between zero and the selected services’ total price.')
        return d

class ProductForm(StyledModelForm):
    class Meta:
        model=Product
        fields=['name','unit','low_stock','active']
    def clean_low_stock(self):
        value=self.cleaned_data['low_stock']
        if value<0: raise forms.ValidationError('Threshold cannot be negative.')
        return value

class StockForm(StyledForm,forms.Form):
    quantity=forms.DecimalField(max_digits=10,decimal_places=2,help_text='Positive to receive stock; negative to record usage or a correction.')
    reason=forms.CharField(max_length=200)
    token=forms.UUIDField(widget=forms.HiddenInput)
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.style()
    def clean_quantity(self):
        value=self.cleaned_data['quantity']
        if not value: raise forms.ValidationError('Enter a non-zero quantity.')
        return value

class AdjustmentForm(StyledForm,forms.Form):
    kind=forms.ChoiceField(choices=[('Correction','Correct an incorrect payment record'),('Refund','Record money refunded and credit the bill')])
    amount=forms.DecimalField(max_digits=8,decimal_places=2,min_value=Decimal('0.01'))
    reason=forms.CharField(max_length=300)
    token=forms.UUIDField(widget=forms.HiddenInput)
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.style()

class BlockForm(StyledModelForm):
    class Meta:
        model=ScheduleBlock
        fields=['staff','date','start_time','end_time','reason']
        widgets={'date':forms.DateInput(attrs={'type':'date'}),'start_time':forms.TimeInput(attrs={'type':'time'}),'end_time':forms.TimeInput(attrs={'type':'time'})}
    def clean(self):
        d=super().clean()
        if d.get('start_time') and d.get('end_time') and d['start_time']>=d['end_time']: self.add_error('end_time','End must follow start.')
        return d

class SettingsForm(StyledModelForm):
    class Meta:
        model=SalonSettings
        exclude=[]
        widgets={name:forms.TimeInput(attrs={'type':'time'},format='%H:%M') for name in ['weekday_open','weekday_close','sunday_open','sunday_close']}
    def clean(self):
        d=super().clean()
        for prefix in ['weekday','sunday']:
            if d.get(prefix+'_open') and d.get(prefix+'_close') and d[prefix+'_open']>=d[prefix+'_close']:
                self.add_error(prefix+'_close','Closing time must follow opening time.')
        if not 1<=d.get('booking_horizon_days',1)<=730:self.add_error('booking_horizon_days','Choose between 1 and 730 days.')
        return d

class WaitlistForm(StyledModelForm):
    class Meta:
        model=WaitlistEntry
        fields=['service','date','notes']
        widgets={'date':forms.DateInput(attrs={'type':'date'})}
    def clean_date(self):
        day=self.cleaned_data['date']
        from datetime import timedelta
        if not timezone.localdate()<=day<=timezone.localdate()+timedelta(days=SalonSettings.current().booking_horizon_days):raise forms.ValidationError('Choose a date within the booking window.')
        return day

class ReviewForm(StyledModelForm):
    rating=forms.TypedChoiceField(choices=[(x,str(x)+' / 5') for x in range(1,6)],coerce=int)
    class Meta:
        model=Review
        fields=['rating','comment']

class StaffAccountForm(StyledForm,forms.Form):
    username=forms.CharField(max_length=150)
    email=forms.EmailField()
    password=forms.CharField(widget=forms.PasswordInput)
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.style()
    def clean_username(self):
        value=self.cleaned_data['username']
        User._meta.get_field('username').run_validators(value)
        if User.objects.filter(username=value).exists():raise forms.ValidationError('Username is already used.')
        return value
    def clean_email(self):
        value=self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=value).exists():raise forms.ValidationError('Email is already used.')
        return value
    def clean(self):
        d=super().clean()
        if d.get('password'):
            validate_password(d['password'],User(username=d.get('username',''),email=d.get('email','')))
        return d
