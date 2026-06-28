from django import forms
from .models import IdentityVerification

class IdentityVerificationForm(forms.ModelForm):
    class Meta:
        model = IdentityVerification
        fields = ['national_id_image', 'selfie_with_id_image']
        labels = {
            'national_id_image': 'تصویر کارت ملی',
            'selfie_with_id_image': 'سلفی با کارت ملی',
        }
        widgets = {
            'national_id_image': forms.FileInput(attrs={'accept': 'image/*'}),
            'selfie_with_id_image': forms.FileInput(attrs={'accept': 'image/*'}),
        }

    def clean_national_id_image(self):
        image = self.cleaned_data.get('national_id_image')
        if image:
            if not image.name.lower().endswith(('.png', '.jpg', '.jpeg')):
                raise forms.ValidationError('فقط فایل‌های PNG، JPG یا JPEG مجاز هستند.')
            if image.size > 5 * 1024 * 1024:  # 5MB limit
                raise forms.ValidationError('حجم فایل باید کمتر از ۵ مگابایت باشد.')
        return image

    def clean_selfie_with_id_image(self):
        image = self.cleaned_data.get('selfie_with_id_image')
        if image:
            if not image.name.lower().endswith(('.png', '.jpg', '.jpeg')):
                raise forms.ValidationError('فقط فایل‌های PNG، JPG یا JPEG مجاز هستند.')
            if image.size > 5 * 1024 * 1024:  # 5MB limit
                raise forms.ValidationError('حجم فایل باید کمتر از ۵ مگابایت باشد.')
        return image