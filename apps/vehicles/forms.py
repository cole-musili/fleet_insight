from django import forms
from .models import Vehicle
class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ["company","registration_number","make","model"]
        widgets = {
            "company":forms.Select(attrs={"class":"form-select"}),
            "registration_number":forms.TextInput(attrs={"class":"form-control"}),
            "make":forms.TextInput(attrs={"class":"form-control"}),
            "model":forms.TextInput(attrs={"class":"form-control"}),
        }
    def clean_registration_number(self):
        return self.cleaned_data["registration_number"].strip().upper().replace(" ","")
