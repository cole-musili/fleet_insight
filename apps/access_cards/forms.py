from django import forms
from .models import AccessCard
class AccessCardForm(forms.ModelForm):
    class Meta:
        model = AccessCard
        fields = ["driver","identifier","date_from","date_until"]
        widgets = {
            "driver":forms.Select(attrs={"class":"form-select"}),
            "identifier":forms.TextInput(attrs={"class":"form-control"}),
            "date_from":forms.DateInput(attrs={"class":"form-control","type":"date"}),
            "date_until":forms.DateInput(attrs={"class":"form-control","type":"date"}),
        }
    def clean_identifier(self):
        return self.cleaned_data["identifier"].strip()
    def clean(self):
        data=super().clean()
        if data.get("date_from") and data.get("date_until") and data["date_until"] < data["date_from"]:
            self.add_error("date_until","Expiry date cannot be before the access start date.")
        return data
