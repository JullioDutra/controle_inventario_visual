from django import forms

from .models import Equipamento


class EquipamentoForm(forms.ModelForm):
    class Meta:
        model = Equipamento
        fields = ["asset_id", "tipo", "status", "responsavel", "serial", "fornecedor", "setor", "pavimento", "obs"]
        widgets = {"obs": forms.Textarea(attrs={"rows": 2})}

    def save(self, commit=True):
        obj = super().save(commit=False)
        if "pavimento" in self.changed_data:  # mudou de andar: a posição antiga deixa de valer
            obj.pos_x = obj.pos_y = None
        if commit:
            obj.save()
        return obj


class LoteForm(forms.Form):
    setor = forms.CharField(required=False)
    pavimento = forms.IntegerField(required=False)


class ImportacaoForm(forms.Form):
    arquivo = forms.FileField(label="Exportação do TopDesk (.xlsx ou .csv)")

    def clean_arquivo(self):
        f = self.cleaned_data["arquivo"]
        if not f.name.lower().endswith((".xlsx", ".xlsm", ".csv")):
            raise forms.ValidationError("Envie um arquivo .xlsx ou .csv.")
        return f
