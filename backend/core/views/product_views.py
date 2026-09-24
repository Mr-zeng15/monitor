from rest_framework.response import Response
from rest_framework.views import APIView
from ..models import Customer, Product


class CustomerListView(APIView):
    """客户简化列表（用于规则配置下拉框）"""
    def get(self, request):
        customers = Customer.objects.all().order_by('name')
        data = [
            {
                'id': c.id,
                'name': c.name,
                'code': c.code,
            }
            for c in customers
        ]
        return Response({'success': True, 'data': data})


class ProductListView(APIView):
    """产品简化列表（用于规则配置下拉框）"""
    def get(self, request):
        customer_id = request.query_params.get('customer')
        qs = Product.objects.all().select_related('customer').order_by('code')
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        data = [
            {
                'id': p.id,
                'code': p.code,
                'name': p.name,
                'material_code_52': p.material_code_52,
                'finished_product_code': p.finished_product_code,
                'customer_id': p.customer_id,
                'customer_name': p.customer.name if p.customer else '',
                'fab': p.fab,
                'bu': p.bu,
                'mode': p.mode,
            }
            for p in qs
        ]
        return Response({'success': True, 'data': data})
