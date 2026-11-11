from django import forms
from .models import Driver
class DriverForm(forms.ModelForm):
    class Meta:
        model = Driver
        fields = ["name","mobile_number","organization","occupation"]
        widgets = {
            "name":forms.TextInput(attrs={"class":"form-control"}),
            "mobile_number":forms.TextInput(attrs={"class":"form-control"}),
            "organization":forms.Select(attrs={"class":"form-select"}),
            "occupation":forms.TextInput(attrs={"class":"form-control"}),
        }
    def clean_mobile_number(self):
        return self.cleaned_data["mobile_number"].strip().replace(" ","")
