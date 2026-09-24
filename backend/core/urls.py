from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WarningRuleViewSet,
    production_plan_months,
    daily_production_list,
    daily_production_grouped,
    seed_demo_data,
    check_warning,
    check_all_warnings,
    ensure_warning_record,
    get_warning_summary,
    test_company_db,
    get_warning_records,
    update_warning_record,
    simulate_realtime_production,
    reset_production,
    detect_unplanned_products,
)
from .views.product_views import CustomerListView, ProductListView
from .views.byfab_views import abl_cloud_data, dppm_cloud_data
from .views.qcai_views import (
    qc_bootstrap,
    qc_next_seq,
    qc_project_save,
    qc_project_status,
    qc_project_delete,
    qc_cat_add,
    qc_cat_remove,
    qc_export,
    qc_import,
)
from .views.excel_flow_views import (
    excel_flow_upload,
    excel_flow_status,
    excel_flow_download,
)
from .views.preplan_views import (
    import_preplan,
    import_preplan_a,
    import_preplan_b,
    preplan_rows,
    preplan_update,
    preplan_set_inserted,
    preplan_insert_all_external,
    preplan_clear,
    preplan_export,
    preplan_months,
    preplan_refresh_entry,
    preplan_export_decision,
    preplan_clear_decision,
    preplan_clear_archive,
    preplan_sync_mtd,
    preplan_batches,
    preplan_archive,
    preplan_unarchive,
    preplan_export_archive_excel,
    preplan_delete,
    preplan_export_decision_excel,
    preplan_recompute_judge,
    preplan_import_cancel,
    EntryTableViewSet,
    OrtRuleViewSet,
)

router = DefaultRouter()
router.register(r'warning-rules', WarningRuleViewSet, basename='warning-rule')
router.register(r'entry-table', EntryTableViewSet, basename='entry-table')
router.register(r'ort-rules', OrtRuleViewSet, basename='ort-rule')

urlpatterns = [
    path('', include(router.urls)),

    # 预警检查 API
    path('warning/check/', check_warning, name='warning-check'),
    path('warning/check-all/', check_all_warnings, name='warning-check-all'),
    path('warning/ensure-record/', ensure_warning_record, name='warning-ensure-record'),
    path('warning/summary/', get_warning_summary, name='warning-summary'),
    path('warning/test-db/', test_company_db, name='warning-test-db'),
    path('warning/simulate/', simulate_realtime_production, name='warning-simulate'),
    path('warning/seed-demo/', seed_demo_data, name='warning-seed-demo'),
    path('warning/reset/', reset_production, name='warning-reset'),
    # ★ 计划外产品自动检测
    path('warning/detect-unplanned/', detect_unplanned_products, name='warning-detect-unplanned'),
    path('warnings/', get_warning_records, name='warning-records'),
    path('warnings/<int:pk>/', update_warning_record, name='warning-record-update'),

    # 客户/产品 API（用于规则配置下拉框）
    path('customers/', CustomerListView.as_view(), name='customer-list'),
    path('products/', ProductListView.as_view(), name='product-list'),


    # 预排筛选 API（S13_DPS + Monthly input target）
    path('preplan/import/', import_preplan, name='preplan-import'),
    path('preplan/import-a/', import_preplan_a, name='preplan-import-a'),
    path('preplan/import-b/', import_preplan_b, name='preplan-import-b'),
    path('preplan/rows/', preplan_rows, name='preplan-rows'),
    path('preplan/update/<int:pk>/', preplan_update, name='preplan-update'),
    path('preplan/set-inserted/<int:pk>/', preplan_set_inserted, name='preplan-set-inserted'),
    path('preplan/insert-all-external/', preplan_insert_all_external, name='preplan-insert-all-external'),
    path('preplan/clear/', preplan_clear, name='preplan-clear'),
    path('preplan/export/', preplan_export, name='preplan-export'),
    path('preplan/months/', preplan_months, name='preplan-months'),
    path('preplan/refresh-entry/', preplan_refresh_entry, name='preplan-refresh-entry'),
    path('preplan/export-decision/', preplan_export_decision, name='preplan-export-decision'),
    path('preplan/clear-decision/', preplan_clear_decision, name='preplan-clear-decision'),
    path('preplan/clear-archive/', preplan_clear_archive, name='preplan-clear-archive'),
    path('preplan/sync-mtd/', preplan_sync_mtd, name='preplan-sync-mtd'),
    path('preplan/batches/', preplan_batches, name='preplan-batches'),
    path('preplan/archive/', preplan_archive, name='preplan-archive'),
    path('preplan/unarchive/<int:pk>/', preplan_unarchive, name='preplan-unarchive'),
    path('preplan/export-archive-excel/', preplan_export_archive_excel, name='preplan-export-archive-excel'),
    path('preplan/delete/<int:pk>/', preplan_delete, name='preplan-delete'),
    path('preplan/export-decision-excel/', preplan_export_decision_excel, name='preplan-export-decision-excel'),
    path('preplan/recompute-judge/', preplan_recompute_judge, name='preplan-recompute-judge'),
    path('preplan/import-cancel/', preplan_import_cancel, name='preplan-import-cancel'),

    # 生产计划月份 API（用于预警监控日期选择器）
    path('production-plan/months/', production_plan_months, name='production-plan-months'),

    # 按日产量 API
    path('daily-production/list/', daily_production_list, name='daily-production-list'),
    path('daily-production/grouped/', daily_production_grouped, name='daily-production-grouped'),

    # ABL 触发 · 云端数据代理（GET 直连云端 JSON）
    path('byfab/abl/', abl_cloud_data, name='abl-cloud-data'),
    # DPPM 云端（2A / 2B）· 云端数据代理（GET 直连云端 JSON）
    path('byfab/dppm/', dppm_cloud_data, name='dppm-cloud-data'),

    # ★ 2026-09-16：QC_AI_TEAM · AI Agent 专案登记（由纯前端 localStorage 版迁移到服务端）
    path('qc-ai/bootstrap/', qc_bootstrap, name='qc-ai-bootstrap'),
    path('qc-ai/next-seq/', qc_next_seq, name='qc-ai-next-seq'),
    path('qc-ai/projects/save/', qc_project_save, name='qc-ai-project-save'),
    path('qc-ai/projects/status/', qc_project_status, name='qc-ai-project-status'),
    path('qc-ai/projects/delete/', qc_project_delete, name='qc-ai-project-delete'),
    path('qc-ai/cats/add/', qc_cat_add, name='qc-ai-cat-add'),
    path('qc-ai/cats/remove/', qc_cat_remove, name='qc-ai-cat-remove'),
    path('qc-ai/export/', qc_export, name='qc-ai-export'),
    path('qc-ai/import/', qc_import, name='qc-ai-import'),

    # ★ 2026-09-24：Excel 处理测试（Dify workflow 文件中继，单任务内存态）
    path('excel-flow/upload/', excel_flow_upload, name='excel-flow-upload'),
    path('excel-flow/status/', excel_flow_status, name='excel-flow-status'),
    path('excel-flow/download/', excel_flow_download, name='excel-flow-download'),
]
