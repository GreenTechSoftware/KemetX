import re

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction

from .models import Job, Product, Profile, Proposal


def normalize_egyptian_phone(value):
    phone = re.sub(r"[\s()-]", "", value)
    if not re.fullmatch(r"(?:(?:\+?20)|0)?1[0125]\d{8}", phone):
        raise forms.ValidationError(
            "Enter a valid Egyptian mobile number, such as 01012345678."
        )
    digits = phone.removeprefix("+")
    if digits.startswith("20"):
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = digits[1:]
    return f"+20{digits}"


class RegistrationForm(UserCreationForm):
    email = forms.EmailField()
    role = forms.ChoiceField(
        choices=Profile.Role.choices,
        widget=forms.RadioSelect,
        initial=Profile.Role.FREELANCER,
    )
    city = forms.CharField(max_length=80, required=False)
    phone = forms.CharField(
        max_length=20,
        help_text="Egyptian mobile number for marketplace checkout.",
    )

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "role",
            "city",
            "phone",
            "password1",
            "password2",
        )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_phone(self):
        return normalize_egyptian_phone(self.cleaned_data["phone"])

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            Profile.objects.create(
                user=user,
                role=self.cleaned_data["role"],
                city=self.cleaned_data["city"].strip(),
                phone=self.cleaned_data["phone"],
            )
        return user


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ("title", "description", "category", "price_egp", "city", "symbol")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "price_egp": forms.NumberInput(attrs={"min": "1", "step": "0.01"}),
            "symbol": forms.TextInput(attrs={"maxlength": "8"}),
        }

    def clean_price_egp(self):
        price = self.cleaned_data["price_egp"]
        if price <= 0:
            raise forms.ValidationError("Price must be greater than zero.")
        return price


class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = ("title", "description", "category", "budget_egp", "city")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "budget_egp": forms.NumberInput(attrs={"min": "1", "step": "0.01"}),
        }


class ProposalForm(forms.ModelForm):
    class Meta:
        model = Proposal
        fields = ("cover_letter", "bid_egp")
        widgets = {
            "cover_letter": forms.Textarea(attrs={"rows": 3}),
            "bid_egp": forms.NumberInput(attrs={"min": "1", "step": "0.01"}),
        }


class ProfileSettingsForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("city", "phone")
        labels = {"city": "City", "phone": "Egyptian mobile number"}

    def clean_phone(self):
        return normalize_egyptian_phone(self.cleaned_data["phone"])
