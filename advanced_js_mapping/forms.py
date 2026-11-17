from django import forms


class CityAttributesForm(forms.Form):
    name = forms.CharField(max_length=100)
    country = forms.CharField(max_length=100)
    population = forms.IntegerField(min_value=0, max_value=9223372036854775807)


class CityCreateForm(CityAttributesForm):
    latitude = forms.FloatField(min_value=-90, max_value=90)
    longitude = forms.FloatField(min_value=-180, max_value=180)
