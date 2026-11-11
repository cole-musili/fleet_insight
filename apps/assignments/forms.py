from django import forms
from .models import DriverTruckAssignment
class AssignmentForm(forms.ModelForm):
    class Meta:
        model = DriverTruckAssignment
        fields = ["driver","truck","date_from","date_until","notes"]
        widgets = {
            "driver":forms.Select(attrs={"class":"form-select"}),
            "truck":forms.Select(attrs={"class":"form-select"}),
            "date_from":forms.DateInput(attrs={"class":"form-control","type":"date"}),
            "date_until":forms.DateInput(attrs={"class":"form-control","type":"date"}),
            "notes":forms.Textarea(attrs={"class":"form-control","rows":2}),
        }
