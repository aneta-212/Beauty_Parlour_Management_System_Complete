from datetime import date
from decimal import Decimal
from django import forms
from .models import Appointment, Staff, StaffLeave, Service, Invoice, Payment, Package
from .scheduling import slots
from accounts.forms import normalize_phone

class StyledForm:
    def style(self):
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

class AppointmentForm(StyledForm, forms.ModelForm):
    time = forms.TimeField(widget=forms.Select())
    extras = forms.ModelMultipleChoiceField(queryset=Service.objects.all(), required=False, label='Additional services')
    package = forms.ModelChoiceField(queryset=Package.objects.filter(active=True),required=False)
    class Meta:
        model=Appointment
        fields=['name','email','phone','service','extras','package','staff','date','time','notes']
        widgets={'date':forms.DateInput(attrs={'type':'date'},format='%Y-%m-%d'),'notes':forms.Textarea(attrs={'rows':3})}
    def __init__(self,*args,user=None,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['service'].required=False
        self.fields['staff'].required=True
        self.fields['staff'].queryset=Staff.objects.filter(active=True)
        if self.instance.pk:
            from django.db.models import Q
            self.fields['package'].queryset=Package.objects.filter(Q(active=True)|Q(pk=self.instance.package_id))
            for name in ['service','extras','package']: self.fields[name].disabled=True
            self.initial['extras']=list(self.instance.items.exclude(service=self.instance.service).values_list('service_id',flat=True))
        self.style()
        self.fields['time'].widget.choices=[('','Choose a time')]
    def clean_phone(self): return normalize_phone(self.cleaned_data['phone'])
    def clean(self):
        from .selection import selection
        data=super().clean()
        if self.instance.pk:
            data['service']=self.instance.service
        else:
            try:
                services,_,_,_=selection(data['service'].pk if data.get('service') else None,[x.pk for x in data.get('extras',[])],data['package'].pk if data.get('package') else None,data.get('date'))
                data['service']=services[0]
            except forms.ValidationError as exc: self.add_error(None,exc)
        return data

class StaffForm(StyledForm, forms.ModelForm):
    weekdays = forms.MultipleChoiceField(choices=list(enumerate(['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'])), widget=forms.CheckboxSelectMultiple)
    class Meta:
        model = Staff
        fields = ['name','services','active','start_time','end_time','weekdays']
        widgets = {'start_time':forms.TimeInput(attrs={'type':'time'},format='%H:%M'), 'end_time':forms.TimeInput(attrs={'type':'time'},format='%H:%M')}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.initial['weekdays'] = self.instance.weekdays.split(',')
        self.style()
        self.fields['active'].widget.attrs['class']='form-check-input'
        self.fields['weekdays'].widget.attrs['class']=''
    def clean_weekdays(self):
        return ','.join(self.cleaned_data['weekdays'])
    def clean(self):
        d=super().clean()
        if d.get('start_time') and d.get('end_time') and d['start_time'] >= d['end_time']:
            self.add_error('end_time','End time must be after start time.')
        return d

class LeaveForm(StyledForm,forms.ModelForm):
    class Meta:
        model=StaffLeave
        fields=['staff','date','reason']
        widgets={'date':forms.DateInput(attrs={'type':'date'})}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.style()

class ServiceForm(StyledForm,forms.ModelForm):
    class Meta:
        model=Service
        fields=['name','description','price','duration','image']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.style()
    def clean_price(self):
        v=self.cleaned_data['price']
        if v < 0: raise forms.ValidationError('Price cannot be negative.')
        return v
    def clean_duration(self):
        v=self.cleaned_data['duration']
        if not 1 <= v <= 660: raise forms.ValidationError('Duration must be between 1 and 660 minutes.')
        return v

class InvoiceForm(StyledForm,forms.Form):
    discount=forms.DecimalField(max_digits=8,decimal_places=2,min_value=0,initial=0)
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.style()

class PaymentForm(StyledForm,forms.Form):
    amount=forms.DecimalField(max_digits=8,decimal_places=2,min_value=Decimal('0.01'))
    method=forms.ChoiceField(choices=Payment._meta.get_field('method').choices)
    reference=forms.CharField(max_length=100,required=False)
    token=forms.UUIDField(widget=forms.HiddenInput)
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.style()

from .models import ContactMessage

class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'phone', 'message']
        widgets = {'message': forms.Textarea(attrs={'rows': 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def clean_phone(self):
        from accounts.forms import normalize_phone
        phone = self.cleaned_data.get('phone')
        return normalize_phone(phone) if phone else ''
