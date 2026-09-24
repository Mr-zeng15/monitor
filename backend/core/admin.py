from django.contrib import admin

# Register your models here.

from .models import EntryTable, OrtRule, PreplanRow


@admin.register(EntryTable)
class EntryTableAdmin(admin.ModelAdmin):
    list_display = ('model', 'material_code_52', 'box_quantity', 'customer', 'updated_at')
    search_fields = ('model', 'material_code_52', 'customer')


@admin.register(OrtRule)
class OrtRuleAdmin(admin.ModelAdmin):
    list_display = ('type_name', 'source', 'operator', 'threshold', 'is_active')
    list_filter = ('source', 'is_active')


@admin.register(PreplanRow)
class PreplanRowAdmin(admin.ModelAdmin):
    list_display = ('plan_year', 'serial_number', 'pn', 'model', 'status', 'ort_ok', 'source')
    list_filter = ('plan_year', 'status', 'source')
    search_fields = ('pn', 'model', 'material_code_52')